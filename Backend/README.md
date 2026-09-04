# ⚖️ AI Contract Reviewer - Backend REST API & AI Engine

[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python)](https://www.python.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![LangChain](https://img.shields.io/badge/LangChain-121013?style=for-the-badge&logo=chainlink&logoColor=white)](https://www.langchain.com/)
[![Google Gemini](https://img.shields.io/badge/Google%20Gemini-4285F4?style=for-the-badge&logo=google&logoColor=white)](https://ai.google.dev/)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-FF6F61?style=for-the-badge)](https://www.trychroma.com/)

An enterprise-grade, asynchronous backend service and neural AI pipeline designed for automated legal contract ingestion, risk detection, indemnification exposure scoring, real-time streaming RAG Q&A (ChatGPT/Gemini style), and complete Admin Panel management.

---

## 🌟 Key Features

- ⚡ **Real-Time Token Streaming Q&A Endpoint**:
  - `POST /contracts/{contract_id}/ask`: Streams answers token-by-token using FastAPI `StreamingResponse` (`text/event-stream`).
  - Utilizes `genai_client.models.generate_content_stream` to stream output without waiting for full generation.

- 👤 **User Profile Management & OTP Security**:
  - **Unique Username Constraint**: Guaranteed unique username indexing across all registered accounts.
  - **OTP-Verified Sensitive Actions**:
    - **Email Change**: `POST /users/me/email/request` dispatches a 6-digit OTP code to the new target email, and `POST /users/me/email/confirm` validates the OTP to update the email address.
    - **Password Change**: `POST /users/me/password/request` dispatches a 6-digit OTP code to the user's registered email, and `POST /users/me/password/confirm` verifies current password + OTP to safely update the password hash.
  - `PATCH /users/me/username` for updating user profile handle.

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

---

## 📁 Directory Structure

```text
Backend/
├── ai_engine/                    # Neural AI Engine & Graph Pipeline
│   ├── graph/                    # LangGraph State & Node Definitions
│   ├── schemas/                  # Analysis Result Pydantic Schemas
│   ├── services/                 # AI Engine Services
│   │   ├── chunk_service.py      # Noise Filtering & Recursive Chunking
│   │   ├── embedding_service.py  # SentenceTransformer Embeddings
│   │   ├── llm_service.py        # Gemini API, Vision OCR & Token Streaming Q&A (ask_question_stream)
│   │   ├── parser_service.py     # Resilient JSON Parser
│   │   ├── prompt_service.py     # Legal Prompt Engineering
│   │   ├── save_analysis.py      # Analysis Result Saver
│   │   ├── text_extractor.py     # PyMuPDF & Gemini Vision OCR Extractor
│   │   └── vector_store_service.py # ChromaDB Queries & Filter Logic
│   └── vector_store/             # ChromaDB Persistent Storage
│
├── app/                          # Core FastAPI Application
│   ├── api/                      # Router Controllers (contracts.py with StreamingResponse)
│   ├── core/                     # Application Config & Security Settings
│   ├── database/                 # SQLAlchemy Async Engines & Models
│   ├── dependencies/             # Fast API Dependencies & JWT Validators
│   ├── models/                   # SQLAlchemy Database Models (User, Contract, Analysis)
│   ├── repositories/             # Async Database Repository Layer
│   ├── schemas/                  # Pydantic Request & Response Schemas
│   └── services/                 # Business Logic Controllers (user_service, auth_service, otp_service, admin_service)
```
