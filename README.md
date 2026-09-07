# ⚖️ AI Contract Reviewer - Full-Stack Enterprise Platform

[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python)](https://www.python.org/)
[![Google Gemini](https://img.shields.io/badge/Google%20Gemini-4285F4?style=for-the-badge&logo=google&logoColor=white)](https://ai.google.dev/)
[![LangGraph](https://img.shields.io/badge/LangGraph-121013?style=for-the-badge&logo=chainlink&logoColor=white)](https://www.langchain.com/)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-FF6F61?style=for-the-badge)](https://www.trychroma.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Redis](https://img.shields.io/badge/Redis-DC382D?style=for-the-badge&logo=redis&logoColor=white)](https://redis.io/)
[![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)

An enterprise-grade, full-stack AI platform for automated legal contract ingestion, risk detection, indemnification exposure scoring, real-time streaming RAG Q&A (ChatGPT/Gemini style), high-performance Redis caching, and complete platform administration with visual system monitoring.

---

## 🌟 Key Features

- 📄 **Asynchronous Contract Analysis Pipeline**:
  - Ingestion of PDF legal documents with text extraction and image-rendering fallback (**Gemini Vision OCR** for scanned photo/image PDFs).
  - Sentence-transformer embeddings (`BAAI/bge-small-en-v1.5`) stored in a persistent **ChromaDB** vector database.
  - Multi-node stateful workflow orchestrated via **LangGraph**.
  - Risk exposure scoring (0–100), clause summarization, and key risk findings via **Google Gemini API**.

- ⚡ **Real-Time Token Streaming RAG Q&A**:
  - Real-time token streaming Q&A endpoint (`POST /contracts/{id}/ask`).
  - Streams answers token-by-token using FastAPI `StreamingResponse` (Server-Sent Events / SSE) and frontend `ReadableStream` reader without blocking or page freezes.

- 🚀 **Redis Cache & Security Store**:
  - High-performance **Redis 7** integration for storing email verification OTPs with automated TTL expiration, sliding-window API rate limiting, and subsystem ping latency tracking.

- 🎨 **College Showcase Glassmorphic UI**:
  - Ultra-premium midnight dark cyber theme with frosted glassmorphism (`backdrop-filter: blur`), Google Fonts (`Outfit` & `Inter`), glowing neon accents, drag-and-drop dropzone, crisp SVG vector icons, and interactive radial SVG risk gauges.

- 🛡️ **Security, User Preferences & Email Notifications**:
  - **OTP-Verified Sensitive Actions**: Email change requests (`POST /users/me/email/request` & `/confirm`) and Password resets (`POST /users/me/password/request` & `/confirm`).
  - **Automated Security Notifications**: Instant email alerts dispatched for username updates, email updates (sent to both old and new addresses), and password changes.
  - **Prompt Hardening**: Multi-layered input sanitization neutralizing zero-width spaces, bidirectional text overrides (`\u202a-\u202e`), model control tokens (`<|im_start|>`), adversarial instructions, and markdown image exfiltration.

- 📊 **System Telemetry & Visual GUI Monitoring Dashboard**:
  - Interactive HTML dashboard (`/admin/monitoring/dashboard`) built with live telemetry, **Auto-Refresh Controls (ON/OFF Toggle, 5s–30s interval selection)**, and manual refresh options.
  - Live system resource profiling (CPU, RAM, Disk), process execution metrics (PID, RSS memory, active threads), service health checks (PostgreSQL, Redis), and API telemetry (latencies, LLM API tracking, vector search speeds).

- ⚡ **Performance Benchmark Suite**:
  - On-demand system benchmarking (`POST /admin/benchmarks/run` & `GET /admin/benchmarks/report`).
  - Measures AI Engine chunking throughput, sentence-transformers embedding latency, ChromaDB search speed, JWT encoding/decoding ops/sec, and API throughput.

- 🛡️ **Role-Based Authentication & Admin Management Portal**:
  - Secure JWT authentication with HttpOnly session cookies and Bearer tokens (with URL query token fallback support for embedded views).
  - Admin panel for user management, contract overview, role promotion/demotion, status toggles, and PDF audit report generation.

- 🐳 **Containerized Microservices Architecture**:
  - Fully containerized microservices architecture orchestrated via Docker Compose (**PostgreSQL**, **Redis**, **FastAPI Backend**, **Nginx Frontend**).

---

## 🏗️ System Architecture

```mermaid
graph TD
    User([User / Browser]) -->|HTTP/HTTPS Ports 80/443| Frontend[Frontend: Nginx Reverse Proxy]
    Frontend -->|REST API & SSE Stream Port 8000| Backend[Backend: FastAPI REST API]
    
    subgraph Infrastructure Services
        Backend --> DB[(PostgreSQL Database)]
        Backend --> Redis[(Redis Cache & OTP Store)]
    end

    subgraph Backend Service
        Backend --> LangGraph[LangGraph AI Pipeline]
        Backend --> SSE[Real-Time Token SSE Stream]
        Backend --> Telemetry[System Health & Telemetry Engine]
    end
    
    subgraph AI Engine & RAG
        LangGraph --> Extractor[PyMuPDF / Gemini Vision OCR]
        LangGraph --> Embeddings[SentenceTransformers Embeddings]
        Embeddings --> Chroma[(ChromaDB Vector Store)]
        LangGraph --> Gemini[Google Gemini LLM Inference]
    end
```

---

## 📁 Repository Directory Structure

```text
ai-contract-reviewer/
├── Backend/                         # FastAPI REST API, Redis Cache & Neural AI Engine
│   ├── ai_engine/                   # LangGraph DAG workflow, RAG pipeline & ChromaDB
│   │   ├── graph/                   # LangGraph state & node execution graph
│   │   ├── services/                # Text extraction, chunking, embeddings, LLM streaming & vector store
│   │   └── vector_store/            # Persistent ChromaDB vector index storage
│   ├── app/                         # FastAPI Application Core
│   │   ├── api/                     # Routers (Auth, Users, Contracts, Admin)
│   │   ├── core/                    # Settings, Redis setup, email setup & rate limiters
│   │   ├── database/                # SQLAlchemy session provider & models
│   │   ├── templates/               # HTML email templates & visual monitoring dashboard GUI
│   │   └── services/                # Business logic controllers (user_service, email_service, admin_service)
│   ├── benchmarks/                  # System performance benchmark suite
│   ├── alembic/                     # Database migration scripts
│   ├── Dockerfile                   # Python 3.10 backend container definition
│   ├── requirements.txt             # Python package dependencies
│   └── README.md                    # Backend API documentation
│
├── Frontend/                        # Client Web Application
│   ├── css/                         # Custom styling & glassmorphism UI theme
│   ├── js/                          # Unified API service layer, streaming reader & interaction scripts
│   ├── index.html                   # Landing page & Authentication (Login/Register)
│   ├── dashboard.html               # User contracts dashboard & preferences panel
│   ├── contract-detail.html         # Contract analysis report & real-time RAG Q&A stream
│   ├── admin.html                   # Administrator management control panel & monitoring iframe
│   ├── nginx.conf                   # Nginx reverse proxy & security headers configuration
│   └── Dockerfile                   # Nginx alpine web server container definition
│
├── certs/                           # SSL/TLS certificates directory
├── docker-compose.yml               # Multi-container orchestration (Postgres, Redis, Backend, Frontend)
└── README.md                        # Root project documentation
```

---

## 🚀 Setup & Installation Instructions

### Prerequisites

- **For Docker Compose Setup**:
  - [Docker Desktop](https://www.docker.com/products/docker-desktop/) (v20.10+) and Docker Compose.
- **For Local Python Setup**:
  - Python 3.10+ installed.
  - PostgreSQL 15+ & Redis 7+ running locally (or via Docker).
- **Google Gemini API Key**:
  - Obtain a Gemini API Key from [Google AI Studio](https://aistudio.google.com/app/apikey).

---

### Option 1: Quick Start with Docker Compose (Recommended)

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/parth123965-wq/AI-Contract-Reviewer.git
   cd AI-Contract-Reviewer
   ```

2. **Setup Environment Variables**:
   Copy the `.env.example` file to `.env` in the `Backend/` directory:
   ```bash
   # Windows PowerShell / Command Prompt
   copy Backend\.env.example Backend\.env

   # Linux / macOS
   cp Backend/.env.example Backend/.env
   ```

3. **Configure Environment Keys**:
   Edit `Backend/.env` to insert your actual Gemini API key and optional production credentials:
   ```env
   GEMINI_API_KEY="your_actual_gemini_api_key_here"
   GOOGLE_API_KEY="your_actual_google_api_key_here"
   SECRET_KEY="your_custom_secret_key_here"
   ```

4. **Launch Application Containers**:
   ```bash
   docker-compose up -d --build
   # OR use the automatic Python runner
   python Backend/start.py
   ```

5. **Access Application**:
   - 🌐 **Frontend Web App**: `https://localhost` (or `http://localhost`)
   - ⚡ **Backend REST API**: `http://localhost:8000`
   - 📚 **Interactive Swagger API Docs**: `http://localhost:8000/docs`
   - 📊 **Visual Monitoring Dashboard**: `http://localhost:8000/admin/monitoring/dashboard`

---

### Option 2: Local Python Development Setup

1. **Clone & Navigate**:
   ```bash
   git clone https://github.com/parth123965-wq/AI-Contract-Reviewer.git
   cd AI-Contract-Reviewer/Backend
   ```

2. **Create & Activate Virtual Environment**:
   ```bash
   # Windows PowerShell
   python -m venv .venv
   .\.venv\Scripts\activate

   # Linux / macOS
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Setup Environment Configuration**:
   ```bash
   # Copy template environment file
   copy .env.example .env    # Windows
   cp .env.example .env      # Linux/macOS
   ```
   *Edit `Backend/.env` to supply `GEMINI_API_KEY`, local `DATABASE_URL`, and `REDIS_URL`.*

5. **Run Application via `start.py`**:
   ```bash
   # Option A: Automatic startup script (spins up background DB/Redis containers, runs Alembic migrations & launches Uvicorn)
   python start.py --local

   # Option B: Direct Uvicorn runner
   uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
   ```

---

## 🔑 Environment Configuration (`Backend/.env`)

Below is a reference of all environment variables supported by the backend service:

### 1. General & Security Settings
| Variable | Type | Default / Example | Description |
| :--- | :--- | :--- | :--- |
| `APP_NAME` | `string` | `AI Contract Reviewer` | Application title |
| `APP_VERSION` | `string` | `1.0.0` | Application version string |
| `DEBUG` | `boolean` | `True` | Enable FastAPI debug mode & dev CORS configuration |
| `SECRET_KEY` | `string` | `your_secret_key_here` | Secret key used for signing JWT authentication tokens |
| `ALGORITHM` | `string` | `HS256` | JWT encoding algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `integer` | `30` | JWT token lifetime in minutes |
| `UPLOAD_DIR` | `string` | `uploads/contracts` | Directory path for persistent contract file storage |
| `LOG_LEVEL` | `string` | `INFO` | Logging severity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `ALLOWED_ORIGINS` | `list[str]` | `["http://localhost:3000","http://localhost:5173"]` | Allowed production CORS origins |

### 2. Database & Redis Cache Connections
| Variable | Type | Default / Example | Description |
| :--- | :--- | :--- | :--- |
| `DATABASE_URL` | `string` | `postgresql+asyncpg://postgres:your_password@localhost:5432/contract_reviewers` | Async PostgreSQL connection URL |
| `REDIS_URL` | `string` | `redis://localhost:6379/0` | Redis connection URL for caching, rate limiting & OTP storage |

### 3. AI Engine & LLM Configuration
| Variable | Type | Default / Example | Description |
| :--- | :--- | :--- | :--- |
| `GEMINI_API_KEY` | `string` | `your_gemini_api_key_here` | Google Gemini API Key for contract risk analysis & RAG Q&A |
| `GOOGLE_API_KEY` | `string` | `your_google_api_key_here` | Fallback Google API Key |
| `AI_MODEL_NAME` | `string` | `gemini-1.5-flash` | Gemini model variant used for inference |
| `MODEL_NAME` | `string` | `BAAI/bge-small-en-v1.5` | HuggingFace embedding model for vector search |
| `COLLECTION_NAME` | `string` | `contracts` | ChromaDB vector store collection name |
| `CHROMA_DB_PATH` | `string` | `ai_engine/vector_store` | Persistent directory path for ChromaDB storage |

### 4. SMTP Email & OTP Registration Settings
| Variable | Type | Default / Example | Description |
| :--- | :--- | :--- | :--- |
| `MAIL_USERNAME` | `string` | `your_email@gmail.com` | SMTP email account username |
| `MAIL_PASSWORD` | `string` | `your_app_password` | SMTP email app password |
| `MAIL_FROM` | `string` | `noreply@ai-contract-reviewer.com` | Sender email address for OTP notifications |
| `MAIL_PORT` | `integer` | `587` | SMTP server port |
| `MAIL_SERVER` | `string` | `smtp.gmail.com` | SMTP server host |
| `MAIL_FROM_NAME` | `string` | `AI Contract Reviewer` | Sender name shown in user inbox |
| `MAIL_STARTTLS` | `boolean` | `True` | Enable STARTTLS connection security |
| `MAIL_SSL_TLS` | `boolean` | `False` | Enable SSL/TLS connection security |
| `OTP_LENGTH` | `integer` | `6` | Number of digits in generated verification OTP |
| `OTP_EXPIRE_SECONDS` | `integer` | `300` | Expiration time for generated OTP (5 mins) |
| `OTP_COOLDOWN_SECONDS` | `integer` | `60` | Cooldown period before resending OTP (60s) |
| `OTP_MAX_ATTEMPTS` | `integer` | `5` | Maximum failed OTP attempts allowed |
