# ⚖️ AI Contract Reviewer - Full-Stack Enterprise Platform

[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python)](https://www.python.org/)
[![Google Gemini](https://img.shields.io/badge/Google%20Gemini-4285F4?style=for-the-badge&logo=google&logoColor=white)](https://ai.google.dev/)
[![LangGraph](https://img.shields.io/badge/LangGraph-121013?style=for-the-badge&logo=chainlink&logoColor=white)](https://www.langchain.com/)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-FF6F61?style=for-the-badge)](https://www.trychroma.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)

An enterprise-grade, full-stack AI platform for automated legal contract ingestion, risk detection, indemnification exposure scoring, real-time streaming RAG Q&A (ChatGPT/Gemini style), and complete platform administration.

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

- 🎨 **College Showcase Glassmorphic UI**:
  - Ultra-premium midnight dark cyber theme with frosted glassmorphism (`backdrop-filter: blur`), Google Fonts (`Outfit` & `Inter`), glowing neon accents, drag-and-drop dropzone, and interactive radial SVG risk gauges.

- 🛡️ **Template-Based Prompt Engineering & Injection Hardening**:
  - `PromptService` template-based prompt engineering (`string.Template` structures) isolating untrusted document context and questions from core security directives.
  - Multi-layered input sanitization neutralizing zero-width spaces, bidirectional text overrides (`\u202a-\u202e`), model control tokens (`<|im_start|>`), adversarial instructions, and image exfiltration URLs.

- 📊 **Real-Time System Telemetry & Monitoring Dashboard**:
  - Interactive HTML dashboard (`/admin/monitoring/dashboard`) built with glassmorphic dark theme and live 5-second polling.
  - Monitors system resources (CPU, RAM, Disk), process execution metrics (PID, RSS, active threads), service connection health (PostgreSQL, Redis), and performance telemetry (HTTP latency histograms, P95 response times, LLM API call tracking, vector search speeds).

- 🛡️ **Role-Based Authentication & Admin Management Portal**:
  - Secure JWT authentication with HttpOnly session cookies and Bearer tokens.
  - Admin dashboard for user role promotion/demotion, contract status updates, search pagination, and system analytics.

- 🐳 **Containerized Architecture**:
  - Fully dockerized application orchestrated with Docker Compose (PostgreSQL, FastAPI Backend, Nginx Frontend).

---

## 🏗️ System Architecture

```mermaid
graph TD
    User([User / Browser]) -->|HTTP Port 80| Frontend[Frontend: Nginx]
    Frontend -->|REST API & SSE Stream Port 8000| Backend[Backend: FastAPI REST API]
    
    subgraph Backend Service
        Backend --> DB[(PostgreSQL Database)]
        Backend --> LangGraph[LangGraph AI Pipeline]
        Backend --> SSE[Real-Time Token SSE Stream]
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
├── Backend/                         # FastAPI REST API & Neural AI Engine
│   ├── ai_engine/                   # LangGraph DAG workflow, RAG pipeline & ChromaDB
│   │   ├── graph/                   # LangGraph state & node execution graph
│   │   ├── services/                # Text extraction, chunking, embeddings, LLM streaming & vector store
│   │   └── vector_store/            # Persistent ChromaDB vector index storage
│   ├── app/                         # FastAPI Application Core
│   │   ├── api/                     # Routers (Auth, Users, Contracts, Admin)
│   │   ├── core/                    # App settings & Pydantic config
│   │   ├── database/                # SQLAlchemy session provider & models
│   │   └── services/                # Business logic controllers
│   ├── alembic/                     # Database migration scripts
│   ├── Dockerfile                   # Python 3.10 backend container definition
│   ├── requirements.txt             # Python package dependencies
│   └── README.md                    # Backend API documentation
│
├── Frontend/                        # Client Web Application
│   ├── css/                         # Custom styling & glassmorphism UI theme
│   ├── js/                          # Unified API service layer, streaming reader & interaction scripts
│   ├── index.html                   # Landing page & Authentication (Login/Register)
│   ├── dashboard.html               # User contracts dashboard & file upload modal
│   ├── contract-detail.html         # Contract analysis report & real-time RAG Q&A stream
│   ├── admin.html                   # Administrator management control panel
│   └── Dockerfile                   # Nginx alpine web server container definition
│
├── docker-compose.yml               # Multi-container orchestration (Postgres, Backend, Frontend)
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
   python Backend/start.py
   ```

5. **Access Application**:
   - 🌐 **Frontend Web App**: `http://localhost`
   - ⚡ **Backend REST API**: `http://localhost:8000`
   - 📚 **Interactive Swagger API Docs**: `http://localhost:8000/docs`

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

### 2. Database & Cache Connections
| Variable | Type | Default / Example | Description |
| :--- | :--- | :--- | :--- |
| `DATABASE_URL` | `string` | `postgresql+asyncpg://postgres:your_password@localhost:5432/contract_reviewers` | Async PostgreSQL connection URL |
| `REDIS_URL` | `string` | `redis://localhost:6379/0` | Redis connection URL for caching & OTP storage |

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

