# 🎬 Cinemagic — Agentic Movie Ticket Booking Portal

Cinemagic is a premium, state-of-the-art AI-powered agentic movie ticket booking assistant. Built on **FastAPI**, **Streamlit**, and **LangGraph**, it coordinates specialized agents using custom tools to search movies, manage showtimes, process seat layouts, recommend titles, handle cancellations, and fetch policy information.

---

## 🚀 Key Features

*   **Intelligent Agentic Routing (LangGraph):** Uses a multi-agent state graph that classifies user intent and routes execution to specialized sub-agents.
*   **Interactive Ticket Booking:** Real-time searches for movies, cinemas, showtimes, and booking creation.
*   **Interactive Seat Selection:** Generates grid-based seat layouts, validates available seats, and blocks booked layouts.
*   **Contextual Movie Recommendations:** Curates personalized movie selections based on user rating history, profiling, and favorite genres.
*   **RAG-based Policy Lookup (Qdrant):** Embeds and indexes company ticket cancellation, change, and refund regulations into Qdrant for semantic search lookup.
*   **Human-In-The-Loop (HITL) Controls:** Halts critical state changes (like making bookings or initiating cancellations) to request explicit user approval before execution.
*   **Double-Tier Memory System:**
    *   *Short-term memory:* Redis checkpointer for LangGraph execution state.
    *   *Long-term memory:* PostgreSQL DB for chat histories and persistent user profiles.
*   **Langfuse Telemetry Tracking:** Full tracing integration with Langfuse to monitor agent executions, tool outputs, and LLM tokens.
*   **API Rate Limiting:** Built-in rate limiters guarding API endpoints both user-wise and route-wise.

---

## 🛠️ Technology Stack

*   **Core Logic:** Python 3.12, LangGraph, LangChain
*   **Backend API:** FastAPI, Uvicorn
*   **Frontend UI:** Streamlit (featuring custom glassmorphic styling, responsive layout, and SSE token streaming)
*   **Databases:**
    *   **PostgreSQL:** Chat history & persistent user preferences
    *   **Redis:** State checkpointing & caching
    *   **Qdrant:** High-performance Vector Database
*   **LLMs:** OpenAI (GPT-4o-mini) with Llama-3.1-70B via Hugging Face/OpenRouter as a resilient fallback layer.

---

## ⚙️ Environment Configuration

Create a `.env` file in the root directory. You can use the `.env.example` as a template:

```env
# OpenAI API Configurations
OPENAI_API_KEY=your_openai_api_key_here
LLM_MODEL=gpt-4o-mini

# Resilient Fallback LLM (Hugging Face / OpenRouter)
HF_TOKEN=your_huggingface_token_here
OPENROUTER_API_KEY=your_openrouter_key_here
FIRST_FALLBACK_LLM=meta-llama/Llama-3.1-70B-Instruct

# Short-term Memory (Redis Checkpointer)
REDIS_URL=redis://localhost:6379/0

# Vector Database (Qdrant)
QDRANT_URL=http://localhost:6333
QDRANT_POLICY_COLLECTION=policy_docs
QDRANT_MEMORY_COLLECTION=session_memory

# Long-term Storage (PostgreSQL / Supabase)
SUPABASE_DB_URL=postgresql://postgres:postgres@localhost:5432/postgres

# API Protection Security Key (For FastAPI endpoints)
API_KEY=your_custom_internal_api_key

# Langfuse Observability & Tracing (Optional)
LANGFUSE_PUBLIC_KEY=your_langfuse_public_key
LANGFUSE_SECRET_KEY=your_langfuse_secret_key
LANGFUSE_BASE_URL=https://cloud.langfuse.com
```

---

## 💻 Local Development Setup

### Prerequisites
*   Docker & Docker Desktop (for Redis, PostgreSQL, and Qdrant)
*   Python >= 3.12
*   `uv` (recommended for fast package installation)

### 1. Manual Setup
1.  **Clone the repository and enter the directory:**
    ```bash
    git clone <repository_url>
    cd agentic-movie-ticket-booking-system
    ```
2.  **Initialize Virtual Environment & Install dependencies:**
    ```bash
    python -m venv .venv
    source .venv/bin/activate
    pip install -e .
    ```
3.  **Launch Docker databases (Postgres, Redis, Qdrant):**
    ```bash
    docker compose up -d postgres redis qdrant
    ```
4.  **Ingest Policies and Seed Databases:**
    ```bash
    python ingestion.py
    ```
5.  **Run FastAPI Backend:**
    ```bash
    uvicorn main:app --port 8005 --reload
    ```
6.  **Run Streamlit Frontend:**
    ```bash
    streamlit run app.py --server.port 8501
    ```

### 2. Auto-Startup Script (One-Click)
We provide clean scripts to start and stop the local environment with a single command:

*   **Start everything:**
    ```bash
    ./start.sh
    ```
    *(This automatically launches Docker containers, verifies health, runs ingestion/seeding, and starts FastAPI and Streamlit.)*

*   **Stop everything:**
    ```bash
    ./stop.sh
    ```
    *(Shuts down backend and frontend processes cleanly.)*

---

## 🐳 Docker Containerization & Orchestration

We provide a **Unified Dockerfile** that builds a single image representing the application. This image can launch the Backend API, the Streamlit UI, or run the Data Ingestion script based on command overrides.

### 📋 The Deployment Script (`docker_deploy.sh`)

We provide a helper script (`docker_deploy.sh`) to automate Docker actions.

#### 1. Build Image Locally
Builds the unified Docker image tagged as `movie-booking-app:latest`:
```bash
./docker_deploy.sh build
```

#### 2. Upload (Push) to Container Registry
Tags the local image and uploads it to a remote container registry (e.g., Docker Hub, AWS ECR, or GitHub Packages):
```bash
./docker_deploy.sh push <registry_username>/movie-booking-app
```

#### 3. Pull from Container Registry
Pulls the container image from a remote registry and tags it locally:
```bash
./docker_deploy.sh pull <registry_username>/movie-booking-app
```

#### 4. Run the Full Orchestrated Stack
Launches Redis, Postgres, Qdrant, Backend, and Frontend containers simultaneously:
```bash
./docker_deploy.sh run
```
*   FastAPI backend will run at: `http://localhost:8005/`
*   Streamlit frontend will run at: `http://localhost:8501/`

#### 5. Stop the Orchestrated Stack
Stops and removes all containers in the stack:
```bash
./docker_deploy.sh stop
```

---

## 🔌 API Documentation

All API requests require the `Authorization: Bearer <API_KEY>` header (matching your configured `API_KEY` in `.env`).

### 1. `POST /chat/stream`
Initiates a SSE (Server-Sent Events) chat connection.
*   **Request Body:**
    ```json
    {
      "user_id": "u123",
      "thread_id": "session-456",
      "message": "Can you recommend a movie and book a ticket?"
    }
    ```
*   **Yields SSE events:**
    *   `data: {"type": "status", "content": "Checking seat layouts..."}`
    *   `data: {"type": "token", "content": "I "}`
    *   `data: {"type": "complete", "status": "success", "messages": [...]}`

### 2. `POST /chat`
Blocking synchronous chat turn execution.
*   **Request Body:** Same as `/chat/stream`.
*   **Response:**
    ```json
    {
      "status": "success",
      "messages": [...]
    }
    ```

### 3. `POST /chat/confirm`
Resumes execution after a Human-In-The-Loop interrupt.
*   **Request Body:**
    ```json
    {
      "user_id": "u123",
      "thread_id": "session-456",
      "decision": "Approve" // or "Reject"
    }
    ```

### 4. `GET /chat/history`
Retrieves chat log.
*   **Query Params:** `user_id=u123&thread_id=session-456`

### 5. `GET /movies`
Retrieves list of movies currently playing.
