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
API_BASE_URL = "http://127.0.0.1:8005"

# Premium CSS styling with custom fonts, glassmorphism, and gradient banners
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif;
    }
    
    /* Main Background & Gradient Banner */
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
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 1.5rem;
        backdrop-filter: blur(10px);
        margin-bottom: 1.5rem;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.2);
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

if "thread_id" not in st.session_state:
    st.session_state.thread_id = "session-101"

if "threads" not in st.session_state:
    st.session_state.threads = ["session-101"]

# Sync logic: loads history from FastAPI server
def fetch_chat_history():
    try:
        url = f"{API_BASE_URL}/chat/history"
        params = {"user_id": st.session_state.user_id, "thread_id": st.session_state.thread_id}
        res = requests.get(url, params=params)
        if res.status_code == 200:
            data = res.json()
            return data.get("messages", []), data.get("status") == "requires_confirmation", data.get("interrupt")
    except Exception as e:
        st.error(f"Failed to load chat history: {str(e)}")
    return [], False, None

# Initialize history and state variables
messages, is_interrupted, interrupt_payload = fetch_chat_history()

# ----------------- SIDEBAR: CONTROLS & SESSION PERSISTENCE -----------------
with st.sidebar:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.markdown('<div class="glass-header">👤 User Settings</div>', unsafe_allow_html=True)
    
    # User Switching
    user_options = ["u1", "u2", "u3", "u4"]
    current_user = st.selectbox("Select User ID", options=user_options, index=user_options.index(st.session_state.user_id) if st.session_state.user_id in user_options else 0)
    if current_user != st.session_state.user_id:
        st.session_state.user_id = current_user
        st.rerun()

    # Session / Thread Switcher
    st.markdown('<div class="glass-header" style="margin-top: 1rem;">🧵 Chat Threads</div>', unsafe_allow_html=True)
    selected_thread = st.selectbox("Active Thread ID", options=st.session_state.threads)
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
                    st.success("Approved successfully!")
                    st.rerun()
                else:
                    st.error(f"Approval failed: {res.text}")
            except Exception as e:
                st.error(f"Connection error: {str(e)}")
                
    with btn_col2:
        if st.button("❌ Reject", key="hitl_reject", use_container_width=True):
            try:
                res = requests.post(f"{API_BASE_URL}/chat/confirm", json={
                    "user_id": st.session_state.user_id,
                    "thread_id": st.session_state.thread_id,
                    "decision": "Reject"
                })
                if res.status_code == 200:
                    st.warning("Rejected/Cancelled draft booking.")
                    st.rerun()
                else:
                    st.error(f"Rejection failed: {res.text}")
            except Exception as e:
                st.error(f"Connection error: {str(e)}")
                
    st.markdown('</div>', unsafe_allow_html=True)

# User Chat Input
user_input = st.chat_input("Ask Cinemagic to search, book, recommend, cancel, or look up policies...")

if user_input:
    # Append user message instantly
    with st.chat_message("user"):
        st.markdown(user_input)
        
    # Send message to FastAPI
    with st.spinner("Processing request..."):
        try:
            payload = {
                "user_id": st.session_state.user_id,
                "thread_id": st.session_state.thread_id,
                "message": user_input
            }
            res = requests.post(f"{API_BASE_URL}/chat", json=payload)
            if res.status_code == 200:
                st.rerun()
            else:
                st.error(f"Error {res.status_code}: {res.text}")
        except Exception as e:
            st.error(f"Failed to connect to assistant: {str(e)}")
