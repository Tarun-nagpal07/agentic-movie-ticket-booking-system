import streamlit as st
import requests
import json
import os
from src.utils.logger import get_logger
logger = get_logger("streamlit_app")
# Set page layout and design theme
st.set_page_config(
    page_title="Cinemagic — Agentic Booking Portal",
    page_icon="🎬",
    layout="centered",
    initial_sidebar_state="expanded"
)

# API endpoint configurations
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8005")

import re
from src.utils.seat_map import generate_seat_grid_html

@st.cache_data(ttl=5)
def fetch_and_generate_seat_html(show_id: str, selected_seats_str: str = "") -> str:
    """
    Fetches show seat status from API and returns HTML string representing seat layout.
    """
    try:
        url = f"{API_BASE_URL}/api/showtimes/{show_id}/seats"
        res = requests.get(url)
        if res.status_code == 200:
            data = res.json()
            seats_dict = data.get("seats", {})
            seat_types = data.get("seat_types", {})
            selected_seats = selected_seats_str.split(",") if selected_seats_str else None
            return generate_seat_grid_html(seats_dict, seat_types, selected_seats)
        else:
            logger.error(f"Error fetching seats for show_id {show_id}: HTTP status {res.status_code}")
            return f'<div style="color: #ef4444; padding: 10px; border: 1px dashed #ef4444; border-radius: 8px;">[Seat map unavailable (status {res.status_code}) for show {show_id}]</div>'
    except Exception as e:
        logger.error(f"Failed to fetch and generate seat HTML for show_id {show_id}: {e}", exc_info=True)
        return f'<div style="color: #ef4444; padding: 10px; border: 1px dashed #ef4444; border-radius: 8px;">[Seat map currently unavailable for show {show_id}]</div>'

def display_assistant_message(content: str):
    """
    Renders assistant message content by separating text blocks and seat map tags,
    rendering text via st.markdown and seat maps via st.html.
    """
    if not content:
        return
        
    has_cursor = content.endswith("▌")
    text_to_parse = content[:-1] if has_cursor else content
    
    pattern = r"(\[SEAT_MAP:[a-zA-Z0-9_]+(?::[a-zA-Z0-9_,]+)?\])"
    parts = re.split(pattern, text_to_parse)
    
    for i, part in enumerate(parts):
        if not part:
            continue
            
        is_last = (i == len(parts) - 1)
        suffix = "▌" if (is_last and has_cursor) else ""
        
        if part.startswith("[SEAT_MAP:") and part.endswith("]"):
            inner = part[10:-1]
            if ":" in inner:
                show_id, selected_seats_str = inner.split(":", 1)
            else:
                show_id, selected_seats_str = inner, ""
                
            try:
                html_layout = fetch_and_generate_seat_html(show_id, selected_seats_str)
                st.html(html_layout)
            except Exception as e:
                logger.error(f"Error rendering seat map HTML: {e}")
                st.error(f"[Seat map unavailable for show {show_id}]")
                
            if suffix:
                st.markdown(suffix)
        else:
            st.markdown(part + suffix)

# Clean solid dark theme CSS styling
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif;
    }
    
    /* Main Background & Clean Solid Black Theme */
    .stApp {
        background-color: #000000 !important;
        background-image: none !important;
        background-attachment: scroll !important;
    }
    
    /* Sidebar Background styling */
    [data-testid="stSidebar"] {
        background-color: #121212 !important;
    }
    
    .banner-title {
        color: #F8FAFC !important;
        font-weight: 700;
        font-size: 2.5rem;
        margin-bottom: 0.2rem;
    }
    
    .banner-subtitle {
        color: #94A3B8;
        font-size: 1rem;
        margin-bottom: 2rem;
    }
    
    /* Simple Cards */
    .glass-card {
        background: #1E293B;
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 1.2rem;
        margin-bottom: 1.2rem;
    }
    
    .glass-header {
        font-weight: 600;
        font-size: 1.1rem;
        margin-bottom: 0.75rem;
        color: #F1F5F9;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    
    /* Simple Dark Chat Messages */
    [data-testid="stChatMessage"] {
        background: #1E293B !important;
        border: 1px solid #334155 !important;
        border-radius: 12px !important;
        padding: 1rem 1.25rem !important;
        margin-bottom: 1rem !important;
        box-shadow: none !important;
        transition: border-color 0.15s ease !important;
    }
    [data-testid="stChatMessage"]:hover {
        border-color: #475569 !important;
    }
    
    /* Custom style for Streamlit Chat Input */
    [data-testid="stChatInput"] {
        background: #1E293B !important;
        border: 1px solid #334155 !important;
        border-radius: 12px !important;
    }
    [data-testid="stChatInput"]:focus-within {
        border-color: #334155 !important;
        box-shadow: none !important;
    }
    [data-testid="stChatInput"] textarea {
        color: #F8FAFC !important;
    }
    
    /* Hide top primary colored decoration line */
    [data-testid="stDecoration"] {
        background: transparent !important;
        background-image: none !important;
        display: none !important;
    }
    
    /* Simple Error/Warning Alert Card */
    .glass-error-card {
        background: rgba(239, 68, 68, 0.1);
        border: 1px solid rgba(239, 68, 68, 0.3);
        border-radius: 8px;
        padding: 0.8rem 1.2rem;
        color: #FCA3A3;
        margin: 1rem 0;
    }
    
    /* Custom Badges */
    .status-badge {
        display: inline-block;
        padding: 0.2rem 0.5rem;
        border-radius: 4px;
        font-size: 0.7rem;
        font-weight: 600;
        text-transform: uppercase;
    }
    .status-confirmed {
        background-color: rgba(16, 185, 129, 0.15);
        color: #34D399;
        border: 1px solid rgba(16, 185, 129, 0.3);
    }
    .status-cancelled {
        background-color: rgba(239, 68, 68, 0.15);
        color: #F87171;
        border: 1px solid rgba(239, 68, 68, 0.3);
    }
    .status-pending {
        background-color: rgba(245, 158, 11, 0.15);
        color: #FBBF24;
        border: 1px solid rgba(245, 158, 11, 0.3);
    }
    
    /* Interactive confirmation box */
    .confirmation-box {
        background: #1E293B;
        border: 1.5px solid #334155;
        border-radius: 12px;
        padding: 1.5rem;
        margin: 1.5rem 0;
    }
    
    /* Thread list styling to remove internal border and padding */
    .thread-item-list [data-testid="stVerticalBlockBorderDiv"] {
        border: none !important;
        background: transparent !important;
        box-shadow: none !important;
        padding: 0 !important;
    }
    
    /* Remove borders and backgrounds from edit (✏️) and delete (🗑️) buttons in the thread list */
    .thread-item-list [data-testid="column"]:nth-child(2) button,
    .thread-item-list [data-testid="column"]:nth-child(3) button {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        padding: 0 !important;
        color: #94A3B8 !important;
        min-height: 0 !important;
        height: 38px !important;
        line-height: 38px !important;
    }
    .thread-item-list [data-testid="column"]:nth-child(2) button:hover,
    .thread-item-list [data-testid="column"]:nth-child(3) button:hover {
        color: #F8FAFC !important;
        background: transparent !important;
        border: none !important;
    }
    
    /* Hide container borders in sidebar */
    [data-testid="stSidebar"] [data-testid="stVerticalBlockBorderDiv"] {
        border: none !important;
    }

    /* Gen-AI Typing Indicator */
    .typing-indicator {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        background: rgba(255, 255, 255, 0.05);
        padding: 6px 10px;
        border-radius: 8px;
    }
    .typing-dot {
        width: 6px;
        height: 6px;
        background-color: #94A3B8;
        border-radius: 50%;
        animation: typing-pulse 1.4s infinite ease-in-out both;
    }
    .typing-dot:nth-child(1) { animation-delay: -0.32s; }
    .typing-dot:nth-child(2) { animation-delay: -0.16s; }

    @keyframes typing-pulse {
        0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
        40% { transform: scale(1.1); opacity: 1; }
    }
</style>
""", unsafe_allow_html=True)

# ----------------- SESSION MANAGEMENT -----------------
import random

def generate_random_thread_name():
    adjectives = [
        "Cosmic", "Star", "Super", "Mega", "Hyper", "Quantum", "Neon", "Cyber", 
        "Ultra", "Apex", "Sonic", "Pulse", "Aero", "Solar", "Lunar", "Vortex", 
        "Cinema", "Screen", "Ticket", "Show", "Popcorn", "Reel", "Pixel", "Vista"
    ]
    nouns = [
        "Lounge", "Portal", "Hub", "Zone", "Club", "Room", "Base", "Nexus", 
        "Sphere", "Cine", "Pass", "Seat", "Show", "Gate", "Line", "Foyer", 
        "Box", "Hall", "Row"
    ]
    adj = random.choice(adjectives)
    noun = random.choice(nouns)
    num = random.randint(100, 999)
    return f"{adj}-{noun}-{num}"

if "processing" not in st.session_state:
    st.session_state.processing = False

if "current_prompt" not in st.session_state:
    st.session_state.current_prompt = None

# If not authenticated, prompt user to Login or Sign Up
if "token" not in st.session_state:
    st.markdown('<div class="banner-title">🎬 Cinemagic Booking Portal</div>', unsafe_allow_html=True)
    st.markdown('<div class="banner-subtitle">Your AI-powered cinema booking assistant. Please log in or register to continue.</div>', unsafe_allow_html=True)

    tab_login, tab_signup = st.tabs(["🔑 Log In", "📝 Sign Up"])

    with tab_login:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        login_email = st.text_input("Email", placeholder="e.g. raj.mehta@gmail.com", key="login_email")
        login_password = st.text_input("Password", type="password", placeholder="Password", key="login_password")
        if st.button("Log In", use_container_width=True, type="primary"):
            if not login_email or not login_password:
                st.error("Please enter both email and password.")
            else:
                try:
                    res = requests.post(f"{API_BASE_URL}/api/auth/login", json={
                        "email": login_email,
                        "password": login_password
                    })
                    if res.status_code == 200:
                        data = res.json()
                        st.session_state.token = data["token"]
                        st.session_state.user_id = data["user_id"]
                        st.session_state.user_name = data["name"]
                        st.session_state.user_email = login_email
                        st.success(f"Successfully logged in as {data['name']}!")
                        st.rerun()
                    else:
                        try:
                            err_detail = res.json().get("detail", "Invalid email or password.")
                        except Exception:
                            err_detail = res.text
                        st.error(f"Login failed: {err_detail}")
                except Exception as e:
                    st.error(f"Failed to connect to backend: {e}")
        st.markdown('</div>', unsafe_allow_html=True)

    with tab_signup:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        signup_name = st.text_input("Full Name", placeholder="e.g. Tarun Nagpal", key="signup_name")
        signup_email = st.text_input("Email Address", placeholder="e.g. tarun@example.com", key="signup_email")
        signup_password = st.text_input("Password (min 6 characters)", type="password", placeholder="Password", key="signup_password")
        signup_city = st.selectbox("City", ["ahmedabad", "mumbai", "bangalore", "delhi"], key="signup_city")
        signup_phone = st.text_input("Phone Number", placeholder="e.g. 9876543210", key="signup_phone")

        if st.button("Create Account & Log In", use_container_width=True, type="primary"):
            if not signup_name or not signup_email or not signup_password or not signup_city or not signup_phone:
                st.error("Please fill in all fields.")
            elif len(signup_password) < 6:
                st.error("Password must be at least 6 characters.")
            else:
                try:
                    res = requests.post(f"{API_BASE_URL}/api/auth/signup", json={
                        "name": signup_name,
                        "email": signup_email,
                        "password": signup_password,
                        "city": signup_city,
                        "phone": signup_phone
                    })
                    if res.status_code == 200:
                        data = res.json()
                        st.session_state.token = data["token"]
                        st.session_state.user_id = data["user_id"]
                        st.session_state.user_name = signup_name
                        st.session_state.user_email = signup_email
                        st.success(f"Welcome, {signup_name}! Account created and logged in.")
                        st.rerun()
                    else:
                        try:
                            err_detail = res.json().get("detail", "Signup failed.")
                        except Exception:
                            err_detail = res.text
                        st.error(f"Signup failed: {err_detail}")
                except Exception as e:
                    st.error(f"Failed to connect to backend: {e}")
        st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# Check if we have a pending user input from a previous redirection (to clear the active interrupt)
user_input_from_state = None
if "pending_user_input" in st.session_state:
    user_input_from_state = st.session_state.pop("pending_user_input")

# Helper to load user threads from backend
def fetch_user_threads():
    token = st.session_state.get("token")
    if not token:
        return []
    try:
        url = f"{API_BASE_URL}/chat/threads"
        res = requests.get(url, headers={"Authorization": f"Bearer {token}"})
        if res.status_code == 200:
            return res.json().get("threads", [])
    except Exception:
        pass
    return []

# Sync logic: loads history from FastAPI server
def fetch_chat_history():
    token = st.session_state.get("token")
    if not token:
        return [], False, None
    try:
        url = f"{API_BASE_URL}/chat/history"
        headers = {"Authorization": f"Bearer {token}"}
        params = {"thread_id": st.session_state.thread_id}
        res = requests.get(url, params=params, headers=headers)
        if res.status_code == 200:
            data = res.json()
            # Always get full history from backend (PostgreSQL), not the trimmed state
            messages = data.get("messages", [])
            is_interrupted = data.get("status") == "requires_confirmation"
            interrupt = data.get("interrupt")
            return messages, is_interrupted, interrupt
    except Exception as e:
        logger.error(f"Failed to load chat history: {e}")
        # Return a nice initial message explaining the error gracefully
        return [
            {
                "role": "assistant",
                "content": "👋 Welcome to Cinemagic! I'm having trouble retrieving our past chat history right now, but I am ready to help you search for movies, check showtimes, and book tickets."
            }
        ], False, None

# Load threads dynamically for the active user if not initialized
if "threads" not in st.session_state:
    st.session_state.threads = fetch_user_threads()

if "thread_id" not in st.session_state:
    st.session_state.thread_id = generate_random_thread_name()

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
    st.markdown(f"**Name:** {st.session_state.user_name}")
    st.markdown(f"**Email:** {st.session_state.user_email}")
    
    if st.button("🚪 Log Out", use_container_width=True):
        try:
            token = st.session_state.get("token")
            if token:
                requests.post(f"{API_BASE_URL}/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
        except Exception:
            pass
        # Clear all state variables
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    # Session / Thread Switcher
    st.markdown('<div class="glass-header" style="margin-top: 1rem;">🧵 Chat Threads</div>', unsafe_allow_html=True)
    
    # Initialize renaming states
    if "renaming_thread" not in st.session_state:
        st.session_state.renaming_thread = None
    if "renaming_active_unsaved" not in st.session_state:
        st.session_state.renaming_active_unsaved = False

    # Update local threads cache
    st.session_state.threads = fetch_user_threads()
    db_threads = [t for t in st.session_state.threads if t]

    if st.session_state.renaming_active_unsaved:
        col_new_act, col_save_act, col_cancel_act = st.columns([6, 1.5, 1.5])
        with col_new_act:
            new_act_name = st.text_input("Active name", value=st.session_state.thread_id, key="new_active_name_input", label_visibility="collapsed")
        with col_save_act:
            if st.button("💾", key="save_active_unsaved"):
                new_act_stripped = new_act_name.strip()
                if new_act_stripped:
                    st.session_state.thread_id = new_act_stripped
                st.session_state.renaming_active_unsaved = False
                st.rerun()
        with col_cancel_act:
            if st.button("❌", key="cancel_active_unsaved"):
                st.session_state.renaming_active_unsaved = False
                st.rerun()
    else:
        col_act, col_act_edit = st.columns([5, 1])
        with col_act:
            st.markdown(f"**Active Chat:** `{st.session_state.thread_id}`")
        with col_act_edit:
            # If the current thread is not saved yet, let user rename it locally
            if st.session_state.thread_id not in db_threads:
                if st.button("✏️", key="edit_active_unsaved_btn", help="Rename active unsaved thread"):
                    st.session_state.renaming_active_unsaved = True
                    st.rerun()
    
    # Button to start a new clean chat thread
    if st.button("➕ New Chat Thread", use_container_width=True):
        st.session_state.thread_id = generate_random_thread_name()
        # Reset chat history cache
        st.session_state.chat_history = []
        st.session_state.is_interrupted = False
        st.session_state.interrupt_payload = None
        st.session_state.renaming_thread = None
        st.session_state.renaming_active_unsaved = False
        st.rerun()

    if db_threads:
        st.markdown('<div style="font-size:0.85rem; color:#8E8EA8; margin-bottom: 0.5rem;">Saved Chats:</div>', unsafe_allow_html=True)
        st.markdown('<div class="thread-item-list">', unsafe_allow_html=True)
        with st.container(height=400, border=False):
            for t in db_threads:
                if st.session_state.renaming_thread == t:
                    col_input, col_save, col_cancel = st.columns([6, 1.5, 1.5])
                    with col_input:
                        new_name = st.text_input("Rename to", value=t, key=f"rename_input_{t}", label_visibility="collapsed")
                    with col_save:
                        if st.button("💾", key=f"rename_save_{t}", use_container_width=True):
                            new_name_stripped = new_name.strip()
                            if new_name_stripped and new_name_stripped != t:
                                try:
                                    token = st.session_state.get("token")
                                    headers = {"Authorization": f"Bearer {token}"} if token else {}
                                    res = requests.put(f"{API_BASE_URL}/chat/threads", params={
                                        "old_thread_id": t,
                                        "new_thread_id": new_name_stripped
                                    }, headers=headers)
                                    if res.status_code == 200:
                                        # Update active thread ID if we renamed the active one
                                        if t == st.session_state.thread_id:
                                            st.session_state.thread_id = new_name_stripped
                                            # Reset history cache to trigger reloading
                                            st.session_state.last_thread_id = None
                                        st.session_state.renaming_thread = None
                                        st.rerun()
                                    else:
                                        st.toast(f"⚠️ Failed to rename thread: {res.text}", icon="⚠️")
                                except Exception as ex:
                                    st.toast(f"⚠️ Error: {str(ex)}", icon="⚠️")
                            else:
                                st.session_state.renaming_thread = None
                                st.rerun()
                    with col_cancel:
                        if st.button("❌", key=f"rename_cancel_{t}", use_container_width=True):
                            st.session_state.renaming_thread = None
                            st.rerun()
                else:
                    col_btn, col_edit, col_del = st.columns([6, 1.5, 1.5])
                    with col_btn:
                        is_active = (t == st.session_state.thread_id)
                        btn_type = "primary" if is_active else "secondary"
                        if st.button(t, key=f"thread_select_{t}", use_container_width=True, type=btn_type):
                            st.session_state.thread_id = t
                            st.session_state.last_thread_id = None
                            st.rerun()
                    with col_edit:
                        if st.button("✏️", key=f"thread_edit_{t}", use_container_width=True):
                            st.session_state.renaming_thread = t
                            st.rerun()
                    with col_del:
                        if st.button("🗑️", key=f"thread_del_{t}", use_container_width=True):
                            try:
                                token = st.session_state.get("token")
                                headers = {"Authorization": f"Bearer {token}"} if token else {}
                                res = requests.delete(f"{API_BASE_URL}/chat/threads", params={
                                    "thread_id": t
                                }, headers=headers)
                                if res.status_code == 200:
                                    if t in st.session_state.threads:
                                        st.session_state.threads.remove(t)
                                    if t == st.session_state.thread_id:
                                        st.session_state.thread_id = generate_random_thread_name()
                                        st.session_state.chat_history = []
                                        st.session_state.is_interrupted = False
                                        st.session_state.interrupt_payload = None
                                    st.rerun()
                                else:
                                    st.toast(f"⚠️ Failed to delete thread: {res.text}", icon="⚠️")
                            except Exception as ex:
                                st.toast(f"⚠️ Error: {str(ex)}", icon="⚠️")
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div style="font-size:0.85rem; color:#8E8EA8; text-align:center; padding: 10px 0;">No saved chats.</div>', unsafe_allow_html=True)
            
    st.markdown('</div>', unsafe_allow_html=True)




# ----------------- MAIN LAYOUT: CHAT INTERFACE -----------------
st.markdown('<div class="banner-title">Cinemagic Assistant</div>', unsafe_allow_html=True)
st.markdown('<div class="banner-subtitle">Book tickets, reserve premium seats, query refund policies, or manage cancellations.</div>', unsafe_allow_html=True)

# Render Chat History
chat_container = st.container()

with chat_container:
    # Filter out empty or raw tool message payloads from the frontend rendering
    rendered_messages = [
        m for m in messages 
        if m.get("role") in ("user", "assistant") and m.get("content", "").strip()
    ]
    
    for msg in rendered_messages:
        role = msg.get("role")
        content = msg.get("content")
        
        # Display nicely in Streamlit
        with st.chat_message(role):
            if role == "assistant":
                display_assistant_message(content)
            else:
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
                token = st.session_state.get("token")
                headers = {"Authorization": f"Bearer {token}"} if token else {}
                res = requests.post(f"{API_BASE_URL}/chat/confirm", json={
                    "user_id": st.session_state.user_id,
                    "thread_id": st.session_state.thread_id,
                    "decision": "Approve"
                }, headers=headers)
                if res.status_code == 200:
                    data = res.json()
                    st.session_state.chat_history = data.get("messages", [])
                    st.session_state.is_interrupted = data.get("status") == "requires_confirmation"
                    st.session_state.interrupt_payload = data.get("interrupt")
                    st.success("Approved successfully!")
                    st.rerun()
                elif res.status_code == 429:
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": "I'm sorry, I'm receiving too many requests right now. Please wait a few seconds and try clicking Approve again."
                    })
                    st.rerun()
                else:
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": f"I encountered an issue confirming the booking on the server: {res.text}. Please try again."
                    })
                    st.rerun()
            except Exception as e:
                st.session_state.chat_history.append({
                    "role": "assistant",
                    "content": f"I am unable to connect to the backend server to confirm your booking: {str(e)}. Please try again."
                })
                st.rerun()
                
    with btn_col2:
        if st.button("❌ Reject", key="hitl_reject", use_container_width=True):
            try:
                token = st.session_state.get("token")
                headers = {"Authorization": f"Bearer {token}"} if token else {}
                res = requests.post(f"{API_BASE_URL}/chat/confirm", json={
                    "user_id": st.session_state.user_id,
                    "thread_id": st.session_state.thread_id,
                    "decision": "Reject"
                }, headers=headers)
                if res.status_code == 200:
                    data = res.json()
                    st.session_state.chat_history = data.get("messages", [])
                    st.session_state.is_interrupted = data.get("status") == "requires_confirmation"
                    st.session_state.interrupt_payload = data.get("interrupt")
                    st.warning("Rejected/Cancelled draft booking.")
                    st.rerun()
                elif res.status_code == 429:
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": "I'm sorry, I'm receiving too many requests right now. Please wait a few seconds and try clicking Reject again."
                    })
                    st.rerun()
                else:
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": f"I encountered an issue rejecting the draft booking: {res.text}. Please try again."
                    })
                    st.rerun()
            except Exception as e:
                st.session_state.chat_history.append({
                    "role": "assistant",
                    "content": f"I am unable to connect to the backend server to reject the booking: {str(e)}. Please try again."
                })
                st.rerun()
                
    st.markdown('</div>', unsafe_allow_html=True)

def cancel_execution_callback():
    st.session_state.processing = False
    st.session_state.current_prompt = None
    st.session_state.chat_history.append({
        "role": "assistant",
        "content": "❌ Execution cancelled by user."
    })
    st.toast("Execution cancelled.", icon="🚫")

# User Chat Input
input_disabled = st.session_state.processing
user_input = st.chat_input(
    "Ask Cinemagic to search, book, recommend, cancel, or look up policies...",
    disabled=input_disabled
)

if user_input_from_state:
    user_input = user_input_from_state

if user_input and not st.session_state.processing:
    # If the user is submitting a new message while an interrupt is active,
    # immediately clear the interrupt and rerun to hide the confirmation box from the screen
    if st.session_state.is_interrupted:
        st.session_state.pending_user_input = user_input
        st.session_state.is_interrupted = False
        st.session_state.interrupt_payload = None
        st.rerun()

    st.session_state.processing = True
    st.session_state.current_prompt = user_input
    st.rerun()

if st.session_state.processing and st.session_state.current_prompt:
    # Append user message and stream assistant reply inside the chat container
    with chat_container:
        with st.chat_message("user"):
            st.markdown(st.session_state.current_prompt)
            
        with st.chat_message("assistant"):
            status_placeholder = st.empty()
            response_placeholder = st.empty()
            cancel_placeholder = st.empty()
            
            # Show Cancel button
            cancel_placeholder.button(
                "🚫 Cancel Execution",
                key="cancel_stream",
                on_click=cancel_execution_callback,
                type="secondary"
            )
            
            full_response = ""
            complete_payload = None
            error_msg = None
            
            try:
                payload = {
                    "user_id": st.session_state.user_id,
                    "thread_id": st.session_state.thread_id,
                    "message": st.session_state.current_prompt
                }
                
                # Show initial typing animation with loading status
                status_placeholder.markdown("""
                <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
                    <div class="typing-indicator">
                        <div class="typing-dot"></div>
                        <div class="typing-dot"></div>
                        <div class="typing-dot"></div>
                    </div>
                    <span style="color: #94A3B8; font-size: 0.9rem; font-style: italic;">Initializing Cinemagic assistant...</span>
                </div>
                """, unsafe_allow_html=True)
                
                # Make a streaming POST request
                token = st.session_state.get("token")
                headers = {"Authorization": f"Bearer {token}"} if token else {}
                res = requests.post(f"{API_BASE_URL}/chat/stream", json=payload, stream=True, headers=headers)
                
                if res.status_code == 200:
                    for line in res.iter_lines():
                        if line:
                            decoded_line = line.decode('utf-8')
                            if decoded_line.startswith("data: "):
                                data = json.loads(decoded_line[6:])
                                event_type = data.get("type")
                                
                                if event_type == "status":
                                    status_placeholder.markdown(f"""
                                    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
                                        <div class="typing-indicator">
                                            <div class="typing-dot"></div>
                                            <div class="typing-dot"></div>
                                            <div class="typing-dot"></div>
                                        </div>
                                        <span style="color: #94A3B8; font-size: 0.9rem; font-style: italic;">{data.get('content')}</span>
                                    </div>
                                    """, unsafe_allow_html=True)
                                elif event_type == "token":
                                    # Clear status loading message on the first token arrival
                                    status_placeholder.empty()
                                    full_response += data.get("content", "")
                                    with response_placeholder.container():
                                        display_assistant_message(full_response + "▌")
                                elif event_type == "complete":
                                    complete_payload = data
                                elif event_type == "error":
                                    error_msg = data.get("message")
                                    
                    # Clean up the cursor and status
                    status_placeholder.empty()
                    cancel_placeholder.empty()
                    with response_placeholder.container():
                        display_assistant_message(full_response)
                    
                    if error_msg:
                        st.session_state.chat_history.append({
                            "role": "assistant",
                            "content": f"I encountered an error while processing: {error_msg}."
                        })
                        st.session_state.processing = False
                        st.session_state.current_prompt = None
                        st.session_state.is_interrupted = False
                        st.session_state.interrupt_payload = None
                        st.rerun()
                    elif complete_payload:
                        logger.info(f"[HITL-DEBUG] complete_payload status={complete_payload.get('status')}, has_interrupt={complete_payload.get('interrupt') is not None}")
                        if complete_payload.get("interrupt"):
                            logger.info(f"[HITL-DEBUG] interrupt_payload keys={list(complete_payload['interrupt'].keys())}")
                        
                        # Populate state directly from complete_payload to avoid slow history downloading
                        st.session_state.chat_history = complete_payload.get("messages", [])
                        st.session_state.is_interrupted = complete_payload.get("status") == "requires_confirmation"
                        st.session_state.interrupt_payload = complete_payload.get("interrupt")
                        st.session_state.last_thread_id = st.session_state.thread_id
                        st.session_state.last_user_id = st.session_state.user_id
                        
                        st.session_state.processing = False
                        st.session_state.current_prompt = None
                        st.rerun()
                elif res.status_code == 429:
                    status_placeholder.empty()
                    cancel_placeholder.empty()
                    try:
                        detail = res.json().get("detail", "Too many requests.")
                    except Exception:
                        detail = res.text
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": f"I'm sorry, I'm receiving too many requests right now: {detail} Please wait a few seconds and try again."
                    })
                    st.session_state.processing = False
                    st.session_state.current_prompt = None
                    st.rerun()
                else:
                    status_placeholder.empty()
                    cancel_placeholder.empty()
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": f"I'm sorry, I encountered a server error (HTTP {res.status_code}): {res.text}. Please try again."
                    })
                    st.session_state.processing = False
                    st.session_state.current_prompt = None
                    st.rerun()
            except Exception as e:
                status_placeholder.empty()
                cancel_placeholder.empty()
                st.session_state.chat_history.append({
                    "role": "assistant",
                    "content": f"I am unable to connect to the backend assistant right now. Please make sure the backend server is running. (Error: {str(e)})"
                })
                st.session_state.processing = False
                st.session_state.current_prompt = None
                st.rerun()
