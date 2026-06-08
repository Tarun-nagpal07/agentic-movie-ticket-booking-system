import streamlit as st
import requests
import json
import os

# Set page layout and design theme
st.set_page_config(
    page_title="Cinemagic — Agentic Booking Portal",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# API endpoint configurations
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8005")

# Premium CSS styling with custom fonts, glassmorphism, and gradient banners
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif;
    }
    
    /* Main Background & Gradient Banner */
    .stApp {
        background-color: #0B0B14 !important;
        background-image: 
            radial-gradient(at 0% 0%, rgba(112, 0, 255, 0.09) 0px, transparent 55%),
            radial-gradient(at 100% 100%, rgba(255, 51, 102, 0.07) 0px, transparent 55%) !important;
        background-attachment: fixed !important;
    }
    
    .banner-title {
        background: linear-gradient(135deg, #FF3366 0%, #7000FF 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 700;
        font-size: 3rem;
        margin-bottom: 0.2rem;
    }
    
    .banner-subtitle {
        color: #8E8EA8;
        font-size: 1.1rem;
        margin-bottom: 2rem;
    }
    
    /* Glassmorphic Cards */
    .glass-card {
        background: rgba(255, 255, 255, 0.02);
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 16px;
        padding: 1.5rem;
        backdrop-filter: blur(10px);
        margin-bottom: 1.5rem;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.25);
    }
    
    .glass-header {
        font-weight: 600;
        font-size: 1.2rem;
        margin-bottom: 1rem;
        color: #E2E2E9;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    
    /* Glowing Glassmorphic Chat Messages */
    [data-testid="stChatMessage"] {
        background: rgba(255, 255, 255, 0.02) !important;
        border: 1px solid rgba(255, 255, 255, 0.05) !important;
        border-radius: 16px !important;
        padding: 1rem 1.25rem !important;
        margin-bottom: 1rem !important;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.15) !important;
        transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease !important;
    }
    [data-testid="stChatMessage"]:hover {
        border-color: rgba(112, 0, 255, 0.25) !important;
        transform: translateY(-2px) !important;
        box-shadow: 0 8px 25px rgba(112, 0, 255, 0.12) !important;
    }
    
    /* Custom style for Streamlit Chat Input */
    [data-testid="stChatInput"] {
        background: rgba(255, 255, 255, 0.03) !important;
        border-radius: 14px !important;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2) !important;
        transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
    }
    [data-testid="stChatInput"]:focus-within {
        border-color: #7000FF !important;
        box-shadow: 0 0 12px rgba(112, 0, 255, 0.25) !important;
    }
    [data-testid="stChatInput"] textarea {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        color: #FFFFFF !important;
    }
    
    /* Glassmorphic Error/Warning Alert Card */
    .glass-error-card {
        background: rgba(239, 68, 68, 0.08);
        border: 1px solid rgba(239, 68, 68, 0.25);
        border-radius: 12px;
        padding: 1rem 1.25rem;
        color: #FCA5A5;
        backdrop-filter: blur(8px);
        margin: 1.2rem 0;
        box-shadow: 0 4px 20px rgba(239, 68, 68, 0.12);
        animation: shake 0.4s ease-in-out;
    }
    
    @keyframes shake {
        0%, 100% { transform: translateX(0); }
        25% { transform: translateX(-4px); }
        75% { transform: translateX(4px); }
    }
    
    /* Custom Badges */
    .status-badge {
        display: inline-block;
        padding: 0.25rem 0.6rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
    }
    .status-confirmed {
        background-color: rgba(16, 185, 129, 0.15);
        color: #10B981;
        border: 1px solid rgba(16, 185, 129, 0.3);
    }
    .status-cancelled {
        background-color: rgba(239, 68, 68, 0.15);
        color: #EF4444;
        border: 1px solid rgba(239, 68, 68, 0.3);
    }
    .status-pending {
        background-color: rgba(245, 158, 11, 0.15);
        color: #F59E0B;
        border: 1px solid rgba(245, 158, 11, 0.3);
    }
    
    /* Movie Showcase Card */
    .movie-card {
        padding: 0.8rem;
        border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    }
    
    .movie-title {
        font-weight: 600;
        color: #FFFFFF;
        font-size: 1rem;
    }
    
    .movie-meta {
        font-size: 0.8rem;
        color: #8E8EA8;
        margin-top: 0.2rem;
    }
 
    /* Interactive Draft confirmation banner */
    .confirmation-box {
        background: linear-gradient(135deg, rgba(112, 0, 255, 0.1) 0%, rgba(255, 51, 102, 0.1) 100%);
        border: 1.5px solid rgba(112, 0, 255, 0.3);
        border-radius: 16px;
        padding: 1.5rem;
        margin: 1.5rem 0;
        box-shadow: 0 10px 40px rgba(112, 0, 255, 0.15);
    }
</style>
""", unsafe_allow_html=True)

# ----------------- DB READ UTILITIES (Live Sidebar Updates) -----------------
def load_bookings_db():
    path = "data/bookings.json"
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f).get("bookings", {})
        except Exception:
            return {}
    return {}

def load_movies_db():
    path = "data/movies.json"
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f).get("movies", [])
        except Exception:
            return []
    return []

# ----------------- SESSION MANAGEMENT -----------------
if "user_id" not in st.session_state:
    st.session_state.user_id = "u1"

# Helper to load user threads from backend
def fetch_user_threads(user_id: str):
    try:
        url = f"{API_BASE_URL}/chat/threads"
        res = requests.get(url, params={"user_id": user_id})
        if res.status_code == 200:
            threads = res.json().get("threads", [])
            if not threads:
                threads = ["session-101"]
            return threads
    except Exception:
        pass
    return ["session-101"]

# Sync logic: loads history from FastAPI server
def fetch_chat_history():
    try:
        url = f"{API_BASE_URL}/chat/history"
        params = {"user_id": st.session_state.user_id, "thread_id": st.session_state.thread_id}
        res = requests.get(url, params=params)
        if res.status_code == 200:
            data = res.json()
            # Always get full history from backend (PostgreSQL), not the trimmed state
            messages = data.get("messages", [])
            is_interrupted = data.get("status") == "requires_confirmation"
            interrupt = data.get("interrupt")
            return messages, is_interrupted, interrupt
    except Exception as e:
        st.error(f"Failed to load chat history: {str(e)}")
    return [], False, None

# Load threads dynamically for the active user if not initialized
if "threads" not in st.session_state:
    st.session_state.threads = fetch_user_threads(st.session_state.user_id)

if "thread_id" not in st.session_state:
    st.session_state.thread_id = st.session_state.threads[0] if st.session_state.threads else "session-101"

# Initialize or rehydrate messages/interrupt states in session state to cache results and prevent rate limits
if (
    "chat_history" not in st.session_state 
    or "last_thread_id" not in st.session_state 
    or st.session_state.last_thread_id != st.session_state.thread_id 
    or "last_user_id" not in st.session_state 
    or st.session_state.last_user_id != st.session_state.user_id
):
    messages, is_interrupted, interrupt_payload = fetch_chat_history()
    st.session_state.chat_history = messages
    st.session_state.is_interrupted = is_interrupted
    st.session_state.interrupt_payload = interrupt_payload
    st.session_state.last_thread_id = st.session_state.thread_id
    st.session_state.last_user_id = st.session_state.user_id
else:
    messages = st.session_state.chat_history
    is_interrupted = st.session_state.is_interrupted
    interrupt_payload = st.session_state.interrupt_payload

# ----------------- SIDEBAR: CONTROLS & SESSION PERSISTENCE -----------------
with st.sidebar:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.markdown('<div class="glass-header">👤 User Settings</div>', unsafe_allow_html=True)
    
    # User Switching
    user_options = ["u1", "u2", "u3", "u4"]
    current_user = st.selectbox("Select User ID", options=user_options, index=user_options.index(st.session_state.user_id) if st.session_state.user_id in user_options else 0)
    if current_user != st.session_state.user_id:
        st.session_state.user_id = current_user
        # Retrieve threads for the newly switched user
        st.session_state.threads = fetch_user_threads(current_user)
        st.session_state.thread_id = st.session_state.threads[0] if st.session_state.threads else "session-101"
        # Reset chat cache so fetch_chat_history gets triggered next run
        st.session_state.last_user_id = None 
        st.rerun()

    # Session / Thread Switcher
    st.markdown('<div class="glass-header" style="margin-top: 1rem;">🧵 Chat Threads</div>', unsafe_allow_html=True)
    
    # Keep selectbox option list synchronized with state
    if st.session_state.thread_id not in st.session_state.threads:
        st.session_state.threads.append(st.session_state.thread_id)
        
    selected_thread = st.selectbox("Active Thread ID", options=st.session_state.threads, index=st.session_state.threads.index(st.session_state.thread_id) if st.session_state.thread_id in st.session_state.threads else 0)
    if selected_thread != st.session_state.thread_id:
        st.session_state.thread_id = selected_thread
        st.rerun()

    # Create new thread
    new_thread_input = st.text_input("New Thread Name", placeholder="e.g. booking-weekend")
    if st.button("➕ Create Thread", use_container_width=True):
        if new_thread_input and new_thread_input not in st.session_state.threads:
            st.session_state.threads.append(new_thread_input)
            st.session_state.thread_id = new_thread_input
            st.rerun()
            
    st.markdown('</div>', unsafe_allow_html=True)

    # ----------------- ACTIVE BOOKINGS PANEL -----------------
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.markdown('<div class="glass-header">🎟️ My Bookings</div>', unsafe_allow_html=True)
    
    bookings = load_bookings_db()
    user_bookings = [b for b in bookings.values() if b.get("user_id") == st.session_state.user_id]
    
    if user_bookings:
        # Sort bookings by date descending
        user_bookings.sort(key=lambda x: x.get("booked_at", ""), reverse=True)
        for b in user_bookings:
            status_class = f"status-{b.get('status', 'confirmed')}"
            st.markdown(f"""
            <div style="padding: 0.6rem 0; border-bottom: 1px solid rgba(255,255,255,0.05);">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <span style="font-weight:600; color:#FFFFFF;">{b.get('movie_title')}</span>
                    <span class="status-badge {status_class}">{b.get('status')}</span>
                </div>
                <div style="font-size:0.8rem; color:#8E8EA8; margin-top:0.25rem;">
                    📍 {b.get('theater_name')} | ID: <code>{b.get('booking_id')}</code><br>
                    🗓️ {b.get('show_date')} at {b.get('show_time')}<br>
                    💺 Seats: {', '.join(b.get('seats', []))} | Total: ₹{b.get('total_price')}
                </div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.markdown('<div style="font-size:0.85rem; color:#8E8EA8; text-align:center;">No active bookings found.</div>', unsafe_allow_html=True)
        
    st.markdown('</div>', unsafe_allow_html=True)

    # ----------------- MOVIE SHOWCASE PANEL -----------------
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.markdown('<div class="glass-header">🎬 Movies Now Showing</div>', unsafe_allow_html=True)
    
    movies = load_movies_db()
    for m in movies[:4]: # Show top 4
        st.markdown(f"""
        <div class="movie-card">
            <div class="movie-title">{m.get('title')}</div>
            <div class="movie-meta">
                ⭐ {m.get('rating')} | ⏱️ {m.get('duration_min')} min | 🌐 {m.get('language')}<br>
                🎭 {', '.join(m.get('genre'))}
            </div>
        </div>
        """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)


# ----------------- MAIN LAYOUT: CHAT INTERFACE -----------------
st.markdown('<div class="banner-title">Cinemagic Assistant</div>', unsafe_allow_html=True)
st.markdown('<div class="banner-subtitle">Book tickets, reserve premium seats, query refund policies, or manage cancellations.</div>', unsafe_allow_html=True)

# Render Chat History
chat_container = st.container()

with chat_container:
    # Filter out empty or raw tool message payloads from the frontend rendering
    rendered_messages = [m for m in messages if m.get("role") in ("user", "assistant")]
    
    for msg in rendered_messages:
        role = msg.get("role")
        content = msg.get("content")
        
        # Display nicely in Streamlit
        with st.chat_message(role):
            st.markdown(content)

# Render Interrupt Block if human-in-the-loop action is required
if is_interrupted and interrupt_payload:
    st.markdown('<div class="confirmation-box">', unsafe_allow_html=True)
    st.markdown(f"### 🛡️ Actions Required: {interrupt_payload.get('message')}")
    
    draft_data = interrupt_payload.get("data", {})
    
    col1, col2 = st.columns(2)
    with col1:
        if "booking_id" in draft_data and "refund_amount" not in draft_data:
            # Booking confirmation view
            st.markdown(f"""
            **📋 Booking Details:**
            - **Booking ID:** `{draft_data.get('booking_id')}`
            - **Movie Title:** {draft_data.get('movie_title', 'Unknown')}
            - **Theater:** {draft_data.get('theater_name', 'Unknown')}
            - **Showtime:** {draft_data.get('show_date')} at {draft_data.get('show_time')}
            - **Format/Screen:** {draft_data.get('format')} | {draft_data.get('screen_name', 'Standard')}
            """)
        elif "refund_amount" in draft_data:
            # Cancellation confirmation view
            st.markdown(f"""
            **📋 Cancellation Refund Details:**
            - **Booking ID to Cancel:** `{draft_data.get('booking_id')}`
            - **Refund Eligibility:** `{draft_data.get('refund_message')}`
            - **Show Date/Time:** {draft_data.get('show_date')} at {draft_data.get('show_time')}
            """)
            
    with col2:
        if "booking_id" in draft_data and "refund_amount" not in draft_data:
            st.markdown(f"""
            **💰 Summary:**
            - **Selected Seats:** {', '.join(draft_data.get('seats', []))}
            - **Total Tickets:** {draft_data.get('num_tickets')}
            - **Total Amount Payable:** **₹{draft_data.get('total_price')}**
            """)
        elif "refund_amount" in draft_data:
            st.markdown(f"""
            **💰 Refund Summary:**
            - **Original Booking Price:** ₹{draft_data.get('total_price')}
            - **Refund Percentage:** {int(draft_data.get('refund_percentage', 0) * 100)}%
            - **Refund Amount Payable:** **₹{draft_data.get('refund_amount')}**
            """)
            
    # HITL Buttons
    btn_col1, btn_col2, _ = st.columns([1, 1, 3])
    with btn_col1:
        if st.button("✅ Approve", key="hitl_approve", use_container_width=True, type="primary"):
            try:
                res = requests.post(f"{API_BASE_URL}/chat/confirm", json={
                    "user_id": st.session_state.user_id,
                    "thread_id": st.session_state.thread_id,
                    "decision": "Approve"
                })
                if res.status_code == 200:
                    data = res.json()
                    st.session_state.chat_history = data.get("messages", [])
                    st.session_state.is_interrupted = data.get("status") == "requires_confirmation"
                    st.session_state.interrupt_payload = data.get("interrupt")
                    st.success("Approved successfully!")
                    st.rerun()
                elif res.status_code == 429:
                    st.markdown(f"""
                    <div class="glass-error-card">
                        <div style="font-weight: 600; font-size: 1.1rem; display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem;">
                            ⚠️ Rate Limit Exceeded
                        </div>
                        <div style="font-size: 0.9rem;">
                            Too many requests. Please wait a few seconds before trying again.
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div class="glass-error-card">
                        <div style="font-weight: 600; font-size: 1.1rem; display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem;">
                            ⚠️ Approval Failed
                        </div>
                        <div style="font-size: 0.9rem;">
                            {res.text}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            except Exception as e:
                st.markdown(f"""
                <div class="glass-error-card">
                    <div style="font-weight: 600; font-size: 1.1rem; display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem;">
                        ⚠️ Connection Error
                    </div>
                    <div style="font-size: 0.9rem;">
                        Could not connect to the backend server: {str(e)}
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
    with btn_col2:
        if st.button("❌ Reject", key="hitl_reject", use_container_width=True):
            try:
                res = requests.post(f"{API_BASE_URL}/chat/confirm", json={
                    "user_id": st.session_state.user_id,
                    "thread_id": st.session_state.thread_id,
                    "decision": "Reject"
                })
                if res.status_code == 200:
                    data = res.json()
                    st.session_state.chat_history = data.get("messages", [])
                    st.session_state.is_interrupted = data.get("status") == "requires_confirmation"
                    st.session_state.interrupt_payload = data.get("interrupt")
                    st.warning("Rejected/Cancelled draft booking.")
                    st.rerun()
                elif res.status_code == 429:
                    st.markdown(f"""
                    <div class="glass-error-card">
                        <div style="font-weight: 600; font-size: 1.1rem; display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem;">
                            ⚠️ Rate Limit Exceeded
                        </div>
                        <div style="font-size: 0.9rem;">
                            Too many requests. Please wait a few seconds before trying again.
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div class="glass-error-card">
                        <div style="font-weight: 600; font-size: 1.1rem; display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem;">
                            ⚠️ Rejection Failed
                        </div>
                        <div style="font-size: 0.9rem;">
                            {res.text}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            except Exception as e:
                st.markdown(f"""
                <div class="glass-error-card">
                    <div style="font-weight: 600; font-size: 1.1rem; display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem;">
                        ⚠️ Connection Error
                    </div>
                    <div style="font-size: 0.9rem;">
                        Could not connect to the backend server: {str(e)}
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
    st.markdown('</div>', unsafe_allow_html=True)

# User Chat Input
user_input = st.chat_input("Ask Cinemagic to search, book, recommend, cancel, or look up policies...")

if user_input:
    # Append user message and stream assistant reply inside the chat container
    with chat_container:
        with st.chat_message("user"):
            st.markdown(user_input)
            
        with st.chat_message("assistant"):
            status_placeholder = st.empty()
            response_placeholder = st.empty()
            full_response = ""
            complete_payload = None
            error_msg = None
            
            try:
                payload = {
                    "user_id": st.session_state.user_id,
                    "thread_id": st.session_state.thread_id,
                    "message": user_input
                }
                # Make a streaming POST request
                res = requests.post(f"{API_BASE_URL}/chat/stream", json=payload, stream=True)
                
                if res.status_code == 200:
                    for line in res.iter_lines():
                        if line:
                            decoded_line = line.decode('utf-8')
                            if decoded_line.startswith("data: "):
                                data = json.loads(decoded_line[6:])
                                event_type = data.get("type")
                                
                                if event_type == "status":
                                    status_placeholder.markdown(f"⏳ *{data.get('content')}*")
                                elif event_type == "token":
                                    # Clear status loading message on the first token arrival
                                    status_placeholder.empty()
                                    full_response += data.get("content", "")
                                    response_placeholder.markdown(full_response + "▌")
                                elif event_type == "complete":
                                    complete_payload = data
                                elif event_type == "error":
                                    error_msg = data.get("message")
                                    
                    # Clean up the cursor and status
                    status_placeholder.empty()
                    response_placeholder.markdown(full_response)
                    
                    if error_msg:
                        st.markdown(f"""
                        <div class="glass-error-card">
                            <div style="font-weight: 600; font-size: 1.1rem; display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem;">
                                ⚠️ System Alert
                            </div>
                            <div style="font-size: 0.9rem;">
                                {error_msg}
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                    elif complete_payload:
                        # Always merge streamed AI message with full history from PostgreSQL.
                        # Middleware may have trimmed the state, but we preserve everything here.
                        server_msgs = complete_payload.get("messages", []) or []
                        
                        # Always append the streamed AI message if it was successfully generated
                        if full_response:
                            # Build final history: server messages + streamed AI response
                            final_history = list(server_msgs)
                            # Only add if not already in server response (avoid duplicates)
                            if not final_history or final_history[-1].get("role") != "assistant":
                                final_history.append({"role": "assistant", "content": full_response})
                            st.session_state.chat_history = final_history
                        else:
                            st.session_state.chat_history = server_msgs

                        st.session_state.is_interrupted = complete_payload.get("status") == "requires_confirmation"
                        st.session_state.interrupt_payload = complete_payload.get("interrupt")
                        st.rerun()
                elif res.status_code == 429:
                    status_placeholder.empty()
                    try:
                        detail = res.json().get("detail", "Too many requests.")
                    except Exception:
                        detail = res.text
                    st.markdown(f"""
                    <div class="glass-error-card">
                        <div style="font-weight: 600; font-size: 1.1rem; display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem;">
                            ⚠️ Rate Limit Exceeded
                        </div>
                        <div style="font-size: 0.9rem;">
                            {detail} Please wait a few seconds before trying again.
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    status_placeholder.empty()
                    # Handle non-200 responses gracefully
                    st.markdown(f"""
                    <div class="glass-error-card">
                        <div style="font-weight: 600; font-size: 1.1rem; display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem;">
                            ⚠️ System Alert
                        </div>
                        <div style="font-size: 0.9rem;">
                            The backend assistant service returned an error (HTTP {res.status_code}): {res.text}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            except Exception as e:
                status_placeholder.empty()
                # Handle connection or other client-side exceptions gracefully
                st.markdown(f"""
                <div class="glass-error-card">
                    <div style="font-weight: 600; font-size: 1.1rem; display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem;">
                        ⚠️ Connection Failed
                    </div>
                    <div style="font-size: 0.9rem;">
                        Could not establish a connection to the Cinemagic assistant. Please make sure the backend is running. (Error: {str(e)})
                    </div>
                </div>
                """, unsafe_allow_html=True)
