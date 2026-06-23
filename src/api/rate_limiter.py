import json
import redis
from fastapi import Request, HTTPException, status
from src.config.settings import settings
from src.utils.logger import get_logger

logger = get_logger("rate_limiter")

# Initialize Redis client for rate limiting
redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)

class RateLimiter:
    def __init__(self, limit: int, window: int, scope: str):
        """
        limit: Number of requests allowed
        window: Time window in seconds
        scope: Name of the route/scope (e.g. "chat", "movies")
        """
        self.limit = limit
        self.window = window
        self.scope = scope

    async def __call__(self, request: Request):
        user_id = None
        
        # 1. Check POST JSON body for user_id
        if request.method == "POST" and "application/json" in request.headers.get("content-type", "").lower():
            try:
                body_bytes = await request.body()
                
                # Re-inject body bytes so subsequent route handlers can read the stream
                async def receive():
                    return {
                        "type": "http.request",
                        "body": body_bytes,
                        "more_body": False
                    }
                request._receive = receive
                
                if body_bytes:
                    data = json.loads(body_bytes)
                    user_id = data.get("user_id")
            except Exception as e:
                logger.warning(f"Failed to read user_id from request body: {e}")
                
        # 2. Check query params if not found in body
        if not user_id:
            user_id = request.query_params.get("user_id")
            
        # 3. Fallback to client IP address
        if not user_id:
            user_id = request.client.host if request.client else "unknown_ip"
            
        # Construct unique Redis rate limiting key
        redis_key = f"rate_limit:{self.scope}:{user_id}"
        
        try:
            # Increment request counter in Redis
            current_count = redis_client.incr(redis_key)
            
            # Set TTL window on first request in block
            if current_count == 1:
                redis_client.expire(redis_key, self.window)
                
            if current_count > self.limit:
                ttl = redis_client.ttl(redis_key)
                logger.warning(f"Rate limit exceeded for {redis_key}. Count={current_count}, Limit={self.limit}, TTL={ttl}s")
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded. Please try again in {ttl if ttl > 0 else self.window} seconds."
                )
        except HTTPException as he:
            raise he
        except Exception as e:
            # Fail-open: log Redis errors but do not crash the request
            logger.error(f"Redis rate limiter exception occurred (failing open): {e}", exc_info=True)
            return
