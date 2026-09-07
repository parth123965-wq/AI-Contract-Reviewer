# ⚖️ AI Contract Reviewer - Backend REST API & AI Engine

[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python)](https://www.python.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Redis](https://img.shields.io/badge/Redis-DC382D?style=for-the-badge&logo=redis&logoColor=white)](https://redis.io/)
[![LangChain](https://img.shields.io/badge/LangChain-121013?style=for-the-badge&logo=chainlink&logoColor=white)](https://www.langchain.com/)
[![Google Gemini](https://img.shields.io/badge/Google%20Gemini-4285F4?style=for-the-badge&logo=google&logoColor=white)](https://ai.google.dev/)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-FF6F61?style=for-the-badge)](https://www.trychroma.com/)

An enterprise-grade, asynchronous backend service and neural AI pipeline designed for automated legal contract ingestion, risk detection, indemnification exposure scoring, real-time streaming RAG Q&A (ChatGPT/Gemini style), high-performance Redis caching, and complete Admin Panel management.

---

## 🌟 Key Features

- ⚡ **Real-Time Token Streaming Q&A Endpoint**:
  - `POST /contracts/{contract_id}/ask`: Streams answers token-by-token using FastAPI `StreamingResponse` (`text/event-stream`).
  - Utilizes `genai_client.models.generate_content_stream` to stream output without waiting for full generation.

- 🚀 **Redis Cache & Security Engine**:
  - High-speed **Redis 7** integration for storing email verification OTPs with automated TTL expiration (`OTP_EXPIRE_SECONDS`), sliding-window API rate limiting, and connection health/latency checks (`get_redis_health()`).

- 👤 **User Profile Management & Security Notifications**:
  - **Unique Username Indexing**: Guaranteed unique username handles across all registered accounts.
  - **Security Notification Emails**:
    - **Username Update**: Automated email notification dispatched to the user's registered email when display name is updated (`username_changed.html`).
    - **Email Address Change**: 2-step OTP flow (`POST /users/me/email/request` & `/confirm`) with notification emails dispatched to **both** `old_email` and `new_email` addresses upon update.
    - **Password Change**: 2-step security OTP flow (`POST /users/me/password/request` & `/confirm`) with optional `current_password` validation and automated security alert email (`password_changed.html`).

- 📊 **Real-Time System Telemetry & Admin Monitoring Dashboard**:
  - `GET /admin/monitoring/system`: Returns CPU, RAM, Disk usage, process runtime metrics (PID, RSS, active threads), database/Redis connection health, and in-memory performance telemetry (HTTP latency histograms, P95 metrics, LLM call stats, vector search speeds).
  - `GET /admin/monitoring/dashboard`: Interactive glassmorphic HTML dashboard UI rendering real-time operational health and latency graphs with configurable **Auto-Refresh Controls (ON/OFF, 5s–30s intervals)**.

- ⚡ **Performance Benchmark Suite**:
  - `POST /admin/benchmarks/run` & `GET /admin/benchmarks/report`: Runs on-demand performance profiling across AI Engine chunking speed, sentence-transformers embedding throughput, ChromaDB similarity query latency, JWT token creation/decoding ops/sec, and REST endpoint throughput.

- 🛠️ **Admin Control Panel & Management APIs**:
  - **User Management**: Paginated search, status activation/deactivation, admin role promotion/demotion, and user deletion.
  - **Contract Management**: View, filter by status, search across filenames/users, update processing status, and delete contracts across all platform users.
  - **Analytics Dashboard**: Real-time stats on user counts, contract processing status queues, and risk level breakdowns.

- 🛡️ **Template-Based Prompt Engineering & Injection Hardening**:
  - Secure template-based prompt generation (`string.Template` structures) isolating context/question inputs from core system instructions.
  - Multi-layer sanitization filtering zero-width spaces, bidirectional text override characters (`\u202a-\u202e`), model tokens, adversarial override patterns, and markdown exfiltration payloads.

- 📄 **Asynchronous Contract Upload & OCR**:
  - Ingestion of contract documents with validation and file storage management.
  - **Multimodal Gemini Vision OCR Fallback**: Automatic image-rendering and OCR text extraction for scanned photo/image-based PDFs.

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
│   ├── api/                      # Router Controllers (Auth, Users, Contracts, Admin)
│   ├── core/                     # Application Config, Redis Setup, Email & Security
│   ├── database/                 # SQLAlchemy Async Engines & Models
│   ├── dependencies/             # Fast API Dependencies & JWT Validators
│   ├── models/                   # SQLAlchemy Database Models (User, Contract, Analysis)
│   ├── repositories/             # Async Database Repository Layer
│   ├── schemas/                  # Pydantic Request & Response Schemas
│   ├── templates/                # HTML email templates & visual monitoring dashboard GUI
│   └── services/                 # Business Logic Controllers (user_service, auth_service, otp_service, email_service, admin_service)
│
├── benchmarks/                   # Performance Benchmark Suite
│   ├── benchmark_ai_pipeline.py  # AI Chunking, Embeddings & Vector Store Profiling
│   ├── benchmark_api_endpoints.py# JWT Overhead & API Throughput Benchmarks
│   └── run_benchmarks.py         # Main Benchmark Suite Runner & Report Generator
```
