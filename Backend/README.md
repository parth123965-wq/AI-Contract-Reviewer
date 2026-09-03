# ⚖️ AI Contract Reviewer - Backend REST API & AI Engine

[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python)](https://www.python.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![LangChain](https://img.shields.io/badge/LangChain-121013?style=for-the-badge&logo=chainlink&logoColor=white)](https://www.langchain.com/)
[![Google Gemini](https://img.shields.io/badge/Google%20Gemini-4285F4?style=for-the-badge&logo=google&logoColor=white)](https://ai.google.dev/)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-FF6F61?style=for-the-badge)](https://www.trychroma.com/)

An enterprise-grade, asynchronous backend service and neural AI pipeline designed for automated legal contract ingestion, risk detection, indemnification exposure scoring, interactive RAG Q&A, and complete Admin Panel management.

---

## 🌟 Key Features

- 🔐 **Authentication & Role-Based Access Control**:
  - Secure JWT authentication via HttpOnly cookies (`ai_contract_session`) and `Authorization: Bearer <token>` headers.
  - Role-based authorization distinguishing regular users from platform Administrators (`is_admin`).
  - Dedicated Admin authentication (`/admin/auth/login`).

- 🛠️ **Admin Control Panel & Management APIs**:
  - **User Management**: Paginated search, status activation/deactivation, admin role promotion/demotion, and user deletion.
  - **Contract Management**: View, filter by status, search across filenames/users, update processing status, and delete contracts across all platform users.
  - **Analytics Dashboard**: Real-time stats on user counts, contract processing status queues, and risk level breakdowns.

- 📄 **Asynchronous Contract Upload & OCR**:
  - Ingestion of contract documents with validation and file storage management.
  - **Multimodal Gemini Vision OCR Fallback**: Automatic image-rendering and OCR text extraction for scanned photo/image-based PDFs.

- ⚡ **Neural LangGraph Pipeline**:
  - Stateful multi-node RAG (Retrieval-Augmented Generation) graph workflow built using `langgraph`.
  - Sentence-transformer embeddings (`BAAI/bge-small-en-v1.5`) stored in a persistent ChromaDB vector store.
  - Google Gemini API (`gemini-flash-latest` / `gemini-pro-latest`) for risk scoring (0-100), legal recommendations, and clause summaries.

- 💬 **Interactive Contract RAG Q&A**:
  - Endpoint `POST /contracts/{contract_id}/ask` allowing users to ask specific questions about any contract document.
  - Context retrieval via vector search with fallback keyword sentence ranking.

---

## 🏗️ Architecture & Technology Stack

| Layer | Technology | Purpose |
| :--- | :--- | :--- |
| **Framework** | FastAPI | High-performance ASGI Web Framework |
| **Database** | PostgreSQL | Relational Database Engine |
| **ORM & Migrations**| SQLAlchemy 2.0 & Alembic | Database Modeling & Schema Migration Scripts |
| **Authentication** | PyJWT & Passlib (Bcrypt) | Password Hashing, JWT Tokens & Role Protection |
| **Graph Orchestration**| LangGraph (`StateGraph`) | Directed Acyclic Graph (DAG) for AI Processing Nodes |
| **Vector Database** | ChromaDB | Persistent Local Vector Embeddings Index |
| **Embedding Model** | `SentenceTransformer` | Local Semantic Embeddings (`BAAI/bge-small-en-v1.5`) |
| **LLM Reasoning & OCR**| Google GenAI SDK (`google.genai`) | Gemini Vision OCR, Contract Risk Analysis & Interactive Q&A |
| **PDF Extraction** | PyMuPDF (`fitz`) | PDF Vector Text & Image Rendering |

---

## 🔄 AI Engine Analysis Pipeline (LangGraph Workflow)

```mermaid
graph TD
    A[Upload Contract PDF] --> B[extract_node: Parse Text / Gemini Vision OCR]
    B --> C[chunk_node: Filter Noise & Split Text]
    C --> D[embedding_node: Generate Sentence Embeddings]
    D --> E[vector_store_node: Store Embeddings in ChromaDB]
    E --> F[retrieve_context_node: Query Relevant Context Chunks]
    F --> G[prompt_node: Construct Legal Prompt Context]
    G --> H[llm_node: Google Gemini Model Inference]
    H --> I[parser_node: Validate & Parse Structured JSON Result]
    I --> J[save_analysis_node: Persist Analysis to PostgreSQL]
    J --> K[Update Status to COMPLETED]
```

---

## 📁 Repository Directory Structure

```text
ai-contract-reviewer/
├── ai_engine/                    # Neural AI Engine & Graph Pipeline
│   ├── graph/                    # LangGraph State & Node Definitions
│   │   ├── graph.py              # StateGraph Builder & Edge Assembler
│   │   ├── nodes.py              # Node Execution Functions
│   │   └── state.py              # TypedDict ContractState Schema
│   ├── schemas/                  # Analysis Result Pydantic Schemas
│   ├── services/                 # AI Engine Services
│   │   ├── chunk_service.py      # Noise Filtering & Recursive Chunking
│   │   ├── embedding_service.py  # SentenceTransformer Embeddings
│   │   ├── llm_service.py        # Gemini API, Vision OCR & Interactive Q&A
│   │   ├── parser_service.py     # Resilient JSON Parser
│   │   ├── prompt_service.py     # Legal Prompt Engineering
│   │   ├── save_analysis.py      # Analysis Result Saver
│   │   ├── text_extractor.py     # PyMuPDF & Gemini Vision OCR Extractor
│   │   └── vector_store_service.py # ChromaDB Queries & Filter Logic
│   └── vector_store/             # ChromaDB Persistent Storage
│
├── app/                          # Core FastAPI Application
│   ├── api/                      # Router Controllers
│   │   ├── admin.py              # Admin Authentication & Management APIs
│   │   ├── auth.py               # User Auth & Session Endpoints
│   │   ├── contracts.py          # Contract Upload, List & Q&A Endpoints
│   │   └── users.py              # User Profile Endpoints
│   ├── core/                     # Application Settings & Configuration
│   ├── database/                 # SQLAlchemy Engine & Session Provider
│   ├── dependencies/             # Auth & Admin Dependencies (`get_current_admin`)
│   ├── models/                   # SQLAlchemy Table Models (User, Contract, Analysis)
│   ├── repositories/             # Data Access Repositories (User, Contract, Analysis)
│   ├── schemas/                  # Request & Response Pydantic Models (Admin, User, Contract)
│   └── services/                 # Business Logic Services (Admin, Auth, Contract, AI)
│
├── alembic/                      # Database Migration Scripts
│   └── versions/                 # Migration Revision Scripts
├── tests/                        # Integration Test Suite (`test_admin.py`)
├── uploads/                      # Uploaded Contract File Storage Directory
├── .env                          # Environment Configuration File
├── alembic.ini                   # Alembic Configuration
├── requirements.txt              # Python Dependencies
└── README.md                     # Documentation
```

---

## 🔌 API Endpoints Specification

### 🔐 Authentication Router (`/auth`)

| Method | Endpoint | Description | Request Body | Response |
| :--- | :--- | :--- | :--- | :--- |
| `POST` | `/auth/register` | Register new user account | `{ email, password, username }` | `UserResponse` |
| `POST` | `/auth/login` | Login user & receive JWT token | `{ email, password }` | `{ access_token, token_type, user }` |
| `POST` | `/auth/token` | OAuth2 Password form login | `OAuth2PasswordRequestForm` | `{ access_token, token_type, user }` |
| `POST` | `/auth/logout` | Logout & clear session cookie | None | `{ message }` |

### 👤 User Router (`/users`)

| Method | Endpoint | Description | Headers | Response |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/users/me` | Fetch active user profile | `Authorization: Bearer <token>` | `UserResponse` |

### 📄 Contracts Router (`/contracts`)

| Method | Endpoint | Description | Request / Params | Response |
| :--- | :--- | :--- | :--- | :--- |
| `POST` | `/contracts/upload` | Upload contract PDF & trigger AI graph | `multipart/form-data (file)` | `ContractResponse` |
| `GET` | `/contracts` | List all contracts for active user | `Authorization: Bearer <token>` | `ContractListResponse` |
| `GET` | `/contracts/{contract_id}` | Fetch contract details & AI analysis | `Authorization: Bearer <token>` | `ContractResponse` |
| `POST` | `/contracts/{contract_id}/ask` | Ask question on contract (RAG Q&A) | `{ question }` | `{ question, answer, context_retrieved }` |
| `DELETE`| `/contracts/{id}` | Soft delete contract record | `Authorization: Bearer <token>` | `{ status: "success" }` |

### 🛡️ Admin Router (`/admin`)

| Method | Endpoint | Description | Query / Body Params | Response |
| :--- | :--- | :--- | :--- | :--- |
| `POST` | `/admin/auth/login` | Admin login | `{ email, password }` | `{ access_token, token_type, user }` |
| `GET` | `/admin/dashboard/stats` | Platform analytics dashboard | None | `AdminDashboardStats` |
| `GET` | `/admin/users` | List all users (paginated) | `page, limit, search, is_active` | `AdminUserListResponse` |
| `GET` | `/admin/users/{user_id}` | Detailed user info & contract count | None | `UserAdminDetailResponse` |
| `PATCH`| `/admin/users/{user_id}/status` | Activate / deactivate user | `{ is_active: bool }` | `UserResponse` |
| `PATCH`| `/admin/users/{user_id}/role` | Promote / demote admin role | `{ is_admin: bool }` | `UserResponse` |
| `DELETE`| `/admin/users/{user_id}` | Delete user account | None | `{ message, user_id }` |
| `GET` | `/admin/contracts` | List all user contracts | `page, limit, status, user_id, search` | `AdminContractListResponse` |
| `GET` | `/admin/contracts/{contract_id}`| Contract detail & user owner info | None | `ContractAdminDetailResponse` |
| `PATCH`| `/admin/contracts/{contract_id}/status`| Update contract status | `{ status: string }` | `ContractResponse` |
| `DELETE`| `/admin/contracts/{contract_id}`| Soft delete contract | None | `{ message, contract_id }` |

---

## 🛠️ Environment Configuration (`.env`)

Create a `.env` file in the root directory:

```ini
APP_NAME = "AI Contract Reviewer"
APP_VERSION = "1.0.0"
DEBUG = True
DATABASE_URL = "postgresql://postgres:password@localhost:5432/contract_reviewers"
SECRET_KEY = "your-secret-key-here"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
UPLOAD_DIR = "uploads/contracts"
LOG_LEVEL = "INFO"

# AI Engine Configuration
MODEL_NAME = "BAAI/bge-small-en-v1.5"
COLLECTION_NAME = "contracts"
CHROMA_DB_PATH = "ai_engine/vector_store"
AI_MODEL_NAME = "gemini-flash-latest"
GOOGLE_API_KEY = "AIzaSy..."
GEMINI_API_KEY = "AIzaSy..."
```

---

## 🚀 Local Installation & Setup

### Prerequisites

- **Python**: `v3.10` or higher
- **PostgreSQL**: Running instance on `localhost:5432`
- **Git**

### 1. Clone Repository & Setup Virtual Environment

```bash
git clone https://github.com/your-username/ai-contract-reviewer.git
cd ai-contract-reviewer

# Create virtual environment
python -m venv .venv

# Activate virtual environment (Windows)
.venv\Scripts\activate

# Activate virtual environment (Linux/macOS)
source .venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt pytest httpx
```

### 3. Setup PostgreSQL Database & Run Migrations

Ensure PostgreSQL is running and database `contract_reviewers` exists:

```bash
# Run database migrations using Alembic
alembic upgrade head
```

### 4. Run Test Suite

```bash
python -m pytest tests/test_admin.py
```

### 5. Start Application Server

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Access Interactive API Documentation (Swagger UI) at:
- **Swagger Docs**: `http://127.0.0.1:8000/docs`
- **ReDoc**: `http://127.0.0.1:8000/redoc`

---

## 🛡️ License

Distributed under the **MIT License**. See `LICENSE` for more information.
