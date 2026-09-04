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

## 🚀 Quick Start with Docker Compose

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (v20.10+) & Docker Compose installed.
- A **Google Gemini API Key** ([Get your API key here](https://aistudio.google.com/app/apikey)).

### 1. Clone Repository & Setup Environment

```bash
git clone https://github.com/parth123965-wq/AI-Contract-Reviewer.git
cd AI-Contract-Reviewer
```

Set your Gemini API key:
```bash
# Windows PowerShell
$env:GEMINI_API_KEY="your_actual_gemini_api_key_here"

# Linux / macOS
export GEMINI_API_KEY="your_actual_gemini_api_key_here"
```

### 2. Launch Docker Services

```bash
docker-compose up -d --build
```

Access the application in your browser:
- 🌐 **Frontend Web App**: `http://localhost`
- ⚡ **Backend REST API**: `http://localhost:8000`
- 📚 **Interactive Swagger API Docs**: `http://localhost:8000/docs`

---

## 🔑 Environment Configuration (`Backend/.env`)

The backend service relies on environment configuration variables defined in `Backend/.env`. Below is a reference of all available keys and sensitive credentials required:

### 1. General & Security Config
| Variable | Example / Default | Description |
| :--- | :--- | :--- |
| `APP_NAME` | `AI Contract Reviewer` | Application title |
| `APP_VERSION` | `1.0.0` | API version string |
| `DEBUG` | `True` | Enable FastAPI debug mode |
| `SECRET_KEY` | `kwomdg` | Secret key used for signing JWT authentication tokens |
| `ALGORITHM` | `HS256` | JWT encoding algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | JWT token lifetime in minutes |
| `UPLOAD_DIR` | `uploads/contracts` | Directory for persistent contract file storage |
| `LOG_LEVEL` | `INFO` | Application log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

### 2. Database & Redis Connections
| Variable | Example / Default | Description |
| :--- | :--- | :--- |
| `DATABASE_URL` | `postgresql+asyncpg://postgres:parth@localhost:5432/contract_reviewers` | PostgreSQL async database connection URL (using `asyncpg`) |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL for caching & OTP storage |

### 3. AI Engine & LLM Configuration
| Variable | Example / Default | Description |
| :--- | :--- | :--- |
| `GEMINI_API_KEY` | `your_gemini_api_key_here` | Google Gemini API Key for LLM contract risk analysis & Q&A |
| `GOOGLE_API_KEY` | `your_google_api_key_here` | Fallback Google API Key |
| `AI_MODEL_NAME` | `gemini-1.5-flash` | Gemini model variant used for inference |
| `MODEL_NAME` | `BAAI/bge-small-en-v1.5` | HuggingFace embedding model for vector search |
| `COLLECTION_NAME` | `contracts` | ChromaDB vector store collection name |
| `CHROMA_DB_PATH` | `ai_engine/vector_store` | Persistent directory path for ChromaDB storage |

### 4. SMTP Email & Registration OTP Settings
| Variable | Example / Default | Description |
| :--- | :--- | :--- |
| `MAIL_USERNAME` | `your_email@gmail.com` | SMTP email account username |
| `MAIL_PASSWORD` | `your_app_password` | SMTP email app password |
| `MAIL_FROM` | `noreply@ai-contract-reviewer.com` | Sender email address for OTP notifications |
| `MAIL_PORT` | `587` | SMTP server port |
| `MAIL_SERVER` | `smtp.gmail.com` | SMTP server host |
| `MAIL_FROM_NAME` | `AI Contract Reviewer` | Sender name shown in user inbox |
| `MAIL_STARTTLS` | `True` | Enable STARTTLS connection security |
| `MAIL_SSL_TLS` | `False` | Enable SSL/TLS connection security |
| `OTP_LENGTH` | `6` | Length of verification OTP digits |
| `OTP_EXPIRE_SECONDS` | `300` | Expiration time for generated OTP (5 mins) |
| `OTP_COOLDOWN_SECONDS` | `60` | Cooldown period before resending OTP (60s) |
| `OTP_MAX_ATTEMPTS` | `5` | Maximum failed OTP attempts allowed |

---

### Sample `.env` File Template

Copy the template below into your `Backend/.env` file:

```env
APP_NAME='AI Contract Reviewer'
APP_VERSION='1.0.0'
DEBUG=True

# Database & Cache Connections
DATABASE_URL='postgresql+asyncpg://postgres:parth@localhost:5432/contract_reviewers'
REDIS_URL='redis://localhost:6379/0'

# Security & JWT Tokens
SECRET_KEY='kwomdg_secret_key_change_me'
ALGORITHM='HS256'
ACCESS_TOKEN_EXPIRE_MINUTES=30
UPLOAD_DIR='uploads/contracts'
LOG_LEVEL='INFO'

# AI Engine & Vector Store
MODEL_NAME="BAAI/bge-small-en-v1.5"
COLLECTION_NAME="contracts"
CHROMA_DB_PATH="ai_engine/vector_store"
AI_MODEL_NAME="gemini-1.5-flash"
GEMINI_API_KEY="your_actual_gemini_api_key"
GOOGLE_API_KEY="your_actual_google_api_key"

# Email SMTP Setup
MAIL_USERNAME=""
MAIL_PASSWORD=""
MAIL_FROM="noreply@ai-contract-reviewer.com"
MAIL_PORT=587
MAIL_SERVER="smtp.gmail.com"
MAIL_FROM_NAME="AI Contract Reviewer"
MAIL_STARTTLS=True
MAIL_SSL_TLS=False

# Registration & Profile OTP Parameters
OTP_LENGTH=6
OTP_EXPIRE_SECONDS=300
OTP_COOLDOWN_SECONDS=60
OTP_MAX_ATTEMPTS=5
```

