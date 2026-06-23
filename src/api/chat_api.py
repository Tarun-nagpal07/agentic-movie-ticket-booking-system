import json
import asyncio
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from langchain_core.messages import HumanMessage
from langgraph.types import Command

from src.api.auth import get_current_user
from src.utils.rate_limiter import RateLimiter
from src.db.postgres import get_db_cursor
from src.api.chat_utils import (
    get_graph_instance,
    format_messages,
    get_active_interrupt,
    load_messages_from_postgress,
    get_langfuse_callback,
    append_new_messages_to_db,
    log_token_usage
)
from src.utils.logger import get_logger

logger = get_logger("chat_api")
router = APIRouter()


class ChatRequest(BaseModel):
    user_id: str
    thread_id: str
    message: str


class ConfirmRequest(BaseModel):
    user_id: str
    thread_id: str
    decision: str  # "Approve" or "Reject"


@router.post("/stream", dependencies=[Depends(RateLimiter(limit=5, window=10, scope="chat"))])
async def chat_stream_endpoint(request: ChatRequest, current_user: dict = Depends(get_current_user)):
    try:
        user_id = current_user["user_id"]
        graph = await get_graph_instance()
        logger.info(f"Chat stream request received: user={user_id}, thread={request.thread_id}, msg='{request.message[:40]}'")
        
        config = {
            "configurable": {
                "thread_id": request.thread_id,
                "user_id": user_id
            },
            "metadata": {
                "langfuse_user_id": user_id,
                "langfuse_session_id": request.thread_id
            }
        }
        
        # Check if Redis checkpointer has existing state
        snapshot = await graph.aget_state(config)
        if not snapshot.values.get("messages"):
            logger.info(f"Redis cache miss for thread {request.thread_id} — loading chat history from Supabase")
            db_messages = load_messages_from_postgress(user_id, request.thread_id)
            if db_messages:
                recent_msgs = db_messages[-15:]
                from src.memory.long_term import get_user_memory
                user_memory = get_user_memory(user_id)
                await graph.aupdate_state(config, {
                    "messages": recent_msgs,
                    "user_id": user_id,
                    "thread_id": request.thread_id,
                    "memory": user_memory or {}
                })
                logger.info(f"Rehydrated thread {request.thread_id} with last {len(recent_msgs)} messages from Supabase")
                snapshot = await graph.aget_state(config)
                
        interrupt_info = get_active_interrupt(snapshot)
        resume_value = request.message if interrupt_info else None

        inputs = {
            "messages": [HumanMessage(content=request.message)],
            "user_id": request.user_id,
            "thread_id": request.thread_id
        }

        # Get pre-invocation message IDs for isolating new messages later
        old_messages = snapshot.values.get("messages", [])
        old_ids = {getattr(m, "id", None) for m in old_messages if getattr(m, "id", None)}

        # Attach Langfuse callback if configured
        langfuse_cb = get_langfuse_callback(request.user_id, request.thread_id)
        if langfuse_cb:
            config["callbacks"] = [langfuse_cb]

        # Determine stream input (normal invoke vs interrupt resume)
        if resume_value is not None:
            stream_input = Command(resume=resume_value, update=inputs)
        else:
            stream_input = inputs

        async def event_generator():
            # Initial status event
            yield f"data: {json.dumps({'type': 'status', 'content': 'Initializing Cinemagic graph...'})}\n\n"

            try:
                async for event in graph.astream_events(stream_input, config, version="v2"):
                    kind = event["event"]

                    if kind == "on_chat_model_start":
                        metadata = event.get("metadata", {})
                        node = metadata.get("langgraph_node", "")
                        tags = event.get("tags", []) or metadata.get("tags", [])
                        if node == "planner" and "refusal_response" in tags:
                            yield f"data: {json.dumps({'type': 'status', 'content': 'Cinemagic assistant formulating response...'})}\n\n"
                        elif node == "planner":
                            yield f"data: {json.dumps({'type': 'status', 'content': 'Analyzing request intent...'})}\n\n"
                        else:
                            checkpoint_ns = metadata.get("checkpoint_ns", "")
                            agent_name = checkpoint_ns.split(":")[0].replace("_node", "").replace("_", " ").title() if checkpoint_ns else "assistant"
                            yield f"data: {json.dumps({'type': 'status', 'content': f'Cinemagic {agent_name} formulating response...'})}\n\n"

                    elif kind == "on_chat_model_stream":
                        metadata = event.get("metadata", {})
                        node = metadata.get("langgraph_node", "")
                        tags = event.get("tags", []) or metadata.get("tags", [])
                        # Only stream tokens from non-planner nodes (planner outputs structured JSON)
                        # OR if it's the refusal response from the planner
                        if node != "planner" or "refusal_response" in tags:
                            chunk = event["data"].get("chunk")
                            if chunk and hasattr(chunk, "content") and chunk.content:
                                yield f"data: {json.dumps({'type': 'token', 'content': chunk.content})}\n\n"

                    elif kind == "on_tool_start":
                        tool_name = event.get("name", "")
                        nice_name = tool_name.replace("_", " ").title()
                        yield f"data: {json.dumps({'type': 'status', 'content': f'Retrieving database records ({nice_name})...'})}\n\n"

                # Stream complete — get final state, persist new messages, and send complete event
                final_snapshot = await graph.aget_state(config)
                final_interrupt = get_active_interrupt(final_snapshot)

                all_messages = final_snapshot.values.get("messages", [])
                new_messages = [m for m in all_messages if getattr(m, "id", None) not in old_ids]
                append_new_messages_to_db(request.user_id, request.thread_id, new_messages)
                log_token_usage(new_messages, "/chat/stream", user_id, request.thread_id)

                full_messages = load_messages_from_postgress(request.user_id, request.thread_id)
                formatted_msgs = format_messages(full_messages)

                stream_status = "requires_confirmation" if final_interrupt else "success"
                movie_posters = final_snapshot.values.get("movie_posters") or []

                complete_event = {
                    "type": "complete",
                    "status": stream_status,
                    "messages": formatted_msgs,
                    "movie_posters": movie_posters
                }
                if final_interrupt:
                    complete_event["interrupt"] = final_interrupt

                logger.info(f"[HITL-DEBUG] stream finished. interrupt_info={'present: ' + str(final_interrupt.get('message')) if final_interrupt else 'None'}")
                yield f"data: {json.dumps(complete_event)}\n\n"

            except Exception as e:
                logger.error(f"Error during stream graph execution: {str(e)}", exc_info=True)
                yield f"data: {json.dumps({'type': 'error', 'message': f'Graph execution failed: {str(e)}'})}\n\n"

        return StreamingResponse(event_generator(), media_type="text/event-stream")
        
    except Exception as e:
        logger.error(f"Error initializing chat stream: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialize chat stream: {str(e)}"
        )


@router.post("", dependencies=[Depends(RateLimiter(limit=5, window=10, scope="chat"))])
async def chat_endpoint(request: ChatRequest, current_user: dict = Depends(get_current_user)):
    try:
        user_id = current_user["user_id"]
        graph = await get_graph_instance()
        logger.info(f"Chat request received: user={user_id}, thread={request.thread_id}, msg='{request.message[:40]}'")

        config = {
            "configurable": {
                "thread_id": request.thread_id,
                "user_id": user_id
            },
            "metadata": {
                "langfuse_user_id": user_id,
                "langfuse_session_id": request.thread_id
            }
        }

        snapshot = await graph.aget_state(config)
        if not snapshot.values.get("messages"):
            logger.info(f"Redis cache miss for thread {request.thread_id} — loading chat history from Supabase")
            db_messages = load_messages_from_postgress(user_id, request.thread_id)
            if db_messages:
                recent_msgs = db_messages[-15:]
                from src.memory.long_term import get_user_memory
                user_memory = get_user_memory(user_id)
                await graph.aupdate_state(config, {
                    "messages": recent_msgs,
                    "user_id": user_id,
                    "thread_id": request.thread_id,
                    "memory": user_memory or {}
                })
                logger.info(f"Rehydrated thread {request.thread_id} with last {len(recent_msgs)} messages from Supabase")
                snapshot = await graph.aget_state(config)

        interrupt_info = get_active_interrupt(snapshot)

        langfuse_cb = get_langfuse_callback(request.user_id, request.thread_id)
        if langfuse_cb:
            config["callbacks"] = [langfuse_cb]

        inputs = {
            "messages": [HumanMessage(content=request.message)],
            "user_id": request.user_id,
            "thread_id": request.thread_id
        }

        # Isolate new messages by getting pre-invocation IDs
        old_messages = snapshot.values.get("messages", [])
        old_ids = {getattr(m, "id", None) for m in old_messages if getattr(m, "id", None)}

        # Invoke the graph asynchronously (resume if interrupted)
        if interrupt_info:
            logger.info(f"Resuming active interrupt on chat endpoint with: {request.message}")
            await graph.ainvoke(Command(resume=request.message, update=inputs), config)
        else:
            await graph.ainvoke(inputs, config)

        new_snapshot = await graph.aget_state(config)
        interrupt_info = get_active_interrupt(new_snapshot)

        all_messages = new_snapshot.values.get("messages", [])
        new_msgs = [m for m in all_messages if getattr(m, "id", None) not in old_ids]
        append_new_messages_to_db(request.user_id, request.thread_id, new_msgs)
        log_token_usage(new_msgs, "/chat", user_id, request.thread_id)
        
        full_messages = load_messages_from_postgress(request.user_id, request.thread_id)
        formatted_msgs = format_messages(full_messages)

        movie_posters = new_snapshot.values.get("movie_posters") or []
        if interrupt_info:
            logger.info(f"Graph paused at interrupt: {interrupt_info.get('message')}")
            return {
                "status": "requires_confirmation",
                "interrupt": interrupt_info,
                "messages": formatted_msgs,
                "movie_posters": movie_posters
            }

        logger.info("Graph execution completed successfully")
        return {
            "status": "success",
            "messages": formatted_msgs,
            "movie_posters": movie_posters
        }

    except Exception as e:
        logger.error(f"Error during chat processing: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error executing chat turn: {str(e)}"
        )


@router.get("/threads", dependencies=[Depends(RateLimiter(limit=20, window=10, scope="threads"))])
def get_chat_threads(current_user: dict = Depends(get_current_user)):
    try:
        user_id = current_user["user_id"]
        with get_db_cursor() as cur:
            cur.execute(
                "SELECT thread_id FROM chat_messages WHERE user_id = %s ORDER BY updated_at DESC;",
                (user_id,)
            )
            rows = cur.fetchall()
            threads = [row[0] for row in rows]
            return {"threads": threads}
    except Exception as e:
        logger.error(f"Error fetching threads: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching threads: {str(e)}"
        )


@router.get("/history", dependencies=[Depends(RateLimiter(limit=10, window=10, scope="history"))])
async def get_chat_history(thread_id: str, current_user: dict = Depends(get_current_user)):
    try:
        user_id = current_user["user_id"]
        graph = await get_graph_instance()
        db_messages = load_messages_from_postgress(user_id, thread_id)
        
        config = {
            "configurable": {
                "thread_id": thread_id,
                "user_id": user_id
            }
        }
        snapshot = await graph.aget_state(config)
        interrupt_info = get_active_interrupt(snapshot)
        movie_posters = snapshot.values.get("movie_posters") or []

        formatted_msgs = format_messages(db_messages) if db_messages else []
        logger.info(f"Returning {len(formatted_msgs)} messages from PostgreSQL for user={user_id}, thread={thread_id}")
        
        return {
            "status": "requires_confirmation" if interrupt_info else "success",
            "interrupt": interrupt_info,
            "messages": formatted_msgs,
            "movie_posters": movie_posters
        }
    except Exception as e:
        logger.error(f"Error fetching history: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching history: {str(e)}"
        )


@router.delete("/threads", dependencies=[Depends(RateLimiter(limit=20, window=10, scope="threads"))])
def delete_chat_thread(thread_id: str, current_user: dict = Depends(get_current_user)):
    try:
        user_id = current_user["user_id"]
        # 1. Delete from PostgreSQL
        with get_db_cursor() as cur:
            cur.execute(
                "DELETE FROM chat_messages WHERE user_id = %s AND thread_id = %s;",
                (user_id, thread_id)
            )
        logger.info(f"Deleted thread {thread_id} messages for user {user_id} from PostgreSQL")

        # 2. Delete checkpointer keys from Redis
        try:
            import redis
            from src.config.settings import settings
            r = redis.Redis.from_url(settings.REDIS_URL)
            patterns = [
                f"checkpoint:{thread_id}:*",
                f"checkpoint_write:{thread_id}:*",
                f"write_keys_zset:{thread_id}:*"
            ]
            deleted_keys_count = 0
            for pattern in patterns:
                keys = r.keys(pattern)
                if keys:
                    r.delete(*keys)
                    deleted_keys_count += len(keys)
            logger.info(f"Cleared {deleted_keys_count} Redis checkpointer keys for thread {thread_id}")
        except Exception as re_err:
            logger.error(f"Failed to clear Redis checkpoints for thread {thread_id}: {re_err}")

        return {"status": "success", "message": f"Thread {thread_id} deleted successfully."}
    except Exception as e:
        logger.error(f"Error deleting thread {thread_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting thread: {str(e)}"
        )


@router.put("/threads", dependencies=[Depends(RateLimiter(limit=20, window=10, scope="threads"))])
def rename_chat_thread(old_thread_id: str, new_thread_id: str, current_user: dict = Depends(get_current_user)):
    if not new_thread_id or not new_thread_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New thread ID cannot be empty."
        )
    try:
        user_id = current_user["user_id"]
        # 1. Update in PostgreSQL
        with get_db_cursor() as cur:
            # Check if new thread ID already exists to avoid conflict
            cur.execute(
                "SELECT 1 FROM chat_messages WHERE user_id = %s AND thread_id = %s;",
                (user_id, new_thread_id)
            )
            if cur.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"A thread named '{new_thread_id}' already exists."
                )

            cur.execute(
                """
                UPDATE chat_messages 
                SET thread_id = %s, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = %s AND thread_id = %s;
                """,
                (new_thread_id, user_id, old_thread_id)
            )
        logger.info(f"Renamed thread {old_thread_id} to {new_thread_id} for user {user_id} in PostgreSQL")

        # 2. Delete checkpointer keys for both old and new threads from Redis to be completely clean
        try:
            import redis
            from src.config.settings import settings
            r = redis.Redis.from_url(settings.REDIS_URL)
            for tid in [old_thread_id, new_thread_id]:
                patterns = [
                    f"checkpoint:{tid}:*",
                    f"checkpoint_write:{tid}:*",
                    f"write_keys_zset:{tid}:*"
                ]
                deleted_keys_count = 0
                for pattern in patterns:
                    keys = r.keys(pattern)
                    if keys:
                        r.delete(*keys)
                        deleted_keys_count += len(keys)
                logger.info(f"Cleared {deleted_keys_count} Redis checkpointer keys for thread {tid}")
        except Exception as re_err:
            logger.error(f"Failed to clear Redis checkpoints during rename: {re_err}")

        return {"status": "success", "message": f"Thread {old_thread_id} renamed to {new_thread_id} successfully."}
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error renaming thread {old_thread_id} to {new_thread_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error renaming thread: {str(e)}"
        )


@router.post("/confirm", dependencies=[Depends(RateLimiter(limit=5, window=10, scope="confirm"))])
async def confirm_endpoint(request: ConfirmRequest, current_user: dict = Depends(get_current_user)):
    try:
        user_id = current_user["user_id"]
        request.user_id = user_id
        graph = await get_graph_instance()
        logger.info(f"Confirm request received: user={user_id}, thread={request.thread_id}, decision={request.decision}")

        config = {
            "configurable": {
                "thread_id": request.thread_id,
                "user_id": user_id
            },
            "metadata": {
                "langfuse_user_id": user_id,
                "langfuse_session_id": request.thread_id
            }
        }

        snapshot = await graph.aget_state(config)
        if not snapshot.values.get("messages"):
            logger.info(f"Redis cache miss on confirm for thread {request.thread_id} — loading chat history from Supabase")
            db_messages = load_messages_from_postgress(user_id, request.thread_id)
            if db_messages:
                await graph.aupdate_state(config, {
                    "messages": db_messages,
                    "user_id": user_id,
                    "thread_id": request.thread_id
                })
                logger.info(f"Rehydrated thread {request.thread_id} on confirm from Supabase")
                snapshot = await graph.aget_state(config)

        interrupt_info = get_active_interrupt(snapshot)

        if not interrupt_info:
            logger.warning("No active interrupt found to confirm")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="There is no active confirmation pending for this conversation thread."
            )

        if request.decision not in ["Approve", "Reject"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Decision must be either 'Approve' or 'Reject'."
            )

        langfuse_cb = get_langfuse_callback(request.user_id, request.thread_id)
        if langfuse_cb:
            config["callbacks"] = [langfuse_cb]

        # Isolate new messages by getting pre-invocation IDs
        old_messages = snapshot.values.get("messages", [])
        old_ids = {getattr(m, "id", None) for m in old_messages if getattr(m, "id", None)}

        # Resume graph execution with the decision
        await graph.ainvoke(Command(resume=request.decision), config)

        new_snapshot = await graph.aget_state(config)
        new_interrupt_info = get_active_interrupt(new_snapshot)

        all_messages = new_snapshot.values.get("messages", [])
        new_msgs = [m for m in all_messages if getattr(m, "id", None) not in old_ids]
        append_new_messages_to_db(request.user_id, request.thread_id, new_msgs)
        log_token_usage(new_msgs, "/chat/confirm", user_id, request.thread_id)
        
        full_messages = load_messages_from_postgress(request.user_id, request.thread_id)
        formatted_msgs = format_messages(full_messages)

        movie_posters = new_snapshot.values.get("movie_posters") or []
        if new_interrupt_info:
            logger.info(f"Graph paused at subsequent interrupt: {new_interrupt_info.get('message')}")
            return {
                "status": "requires_confirmation",
                "interrupt": new_interrupt_info,
                "messages": formatted_msgs,
                "movie_posters": movie_posters
            }

        logger.info("Graph execution completed successfully after confirmation")
        return {
            "status": "success",
            "messages": formatted_msgs,
            "movie_posters": movie_posters
        }

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error during confirmation processing: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error executing confirmation turn: {str(e)}"
        )
