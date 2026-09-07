# 📄 AI Contract Reviewer - Frontend Web Application

[![HTML5](https://img.shields.io/badge/HTML5-E34F26?style=for-the-badge&logo=html5&logoColor=white)](https://developer.mozilla.org/en-US/docs/Web/HTML)
[![CSS3](https://img.shields.io/badge/CSS3-1572B6?style=for-the-badge&logo=css3&logoColor=white)](https://developer.mozilla.org/en-US/docs/Web/CSS)
[![JavaScript](https://img.shields.io/badge/JavaScript-ES6%2B-F7DF1E?style=for-the-badge&logo=javascript&logoColor=black)](https://developer.mozilla.org/en-US/docs/Web/JavaScript)
[![Theme](https://img.shields.io/badge/Design-Glassmorphism%20%26%20Dark%20Mode-7B2CBF?style=for-the-badge)](#-design-system--styling)
[![Docker](https://img.shields.io/badge/Docker-Nginx%20Alpine-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)

A responsive, high-performance web interface for the **AI Contract Reviewer** ecosystem. Built with pure Vanilla HTML5, modern CSS custom properties, glassmorphic UI components, Google Fonts (`Outfit` & `Inter`), SVG vector icons, and ES6+ JavaScript modules connecting directly to the FastAPI REST backend.

---

## ✨ Key Features

- 🔐 **User Registration OTP Verification Flow**:
  - Step-by-step account activation modal popping up upon registration submission (`/auth/register`).
  - Submits 6-digit verification code to `POST /auth/verify-registration`.
  - Supports live OTP resend capabilities via `POST /auth/resend-otp`.

- 👤 **User Profile & Security Preferences**:
  - **Display Name Update**: Username updates connecting to `PATCH /users/me/username` with automated security email notification.
  - **Email Address Change**: 2-step verification workflow (`POST /users/me/email/request` & `/confirm`) with automated email alerts sent to both old and new addresses.
  - **Password Reset**: 2-step security workflow (`POST /users/me/password/request` & `/confirm`) with optional current password requirement.

- ⚡ **Real-Time Token Streaming RAG Assistant**:
  - Interactive Q&A chat assistant on the contract detail page connecting to `POST /contracts/{contract_id}/ask`.
  - Decodes `text/event-stream` SSE tokens in real-time via `ReadableStream.getReader()` for progressive rendering (ChatGPT / Gemini style).

- 🎨 **Midnight Cyber Glassmorphism Theme & SVG Icons**:
  - Midnight dark palette (`#090a0f`) with frosted glass backdrop blur (`backdrop-filter: blur(16px)`), glowing neon cyan and purple accents, smooth hover micro-animations, and clean SVG vector icons across buttons and card headers.

- 🔑 **Authentication & Role Management**:
  - Dual-mode login (User Workspace vs. Admin Portal) connecting to `/auth/login` and `/admin/auth/login`.

- 🛡️ **Full Admin Control Panel & Telemetry Dashboard**:
  - Dedicated administrative interface (`admin.html`) with real-time stats counters, user role management, status toggles, and contract overview controls.
  - Interactive visual System Monitoring Dashboard (`/admin/monitoring/dashboard`) rendering live CPU, memory, disk usage, database/redis latencies, and HTTP response histograms with **Auto-Refresh Controls (ON/OFF Toggle, 5s–30s interval selector)**.

- ⚡ **Performance Benchmarks Tab**:
  - Admin tab for running system-wide performance profiling across AI Engine chunking speed, embedding latency, ChromaDB search speed, JWT ops/sec, and API request throughput.

- 📊 **Interactive Workspace Dashboard**:
  - Stat cards displaying total contracts, completed reviews, high-risk exposure alerts, and processing queues.
  - Search bar and status filtering (`all`, `uploaded`, `processing`, `completed`, `failed`).
  - Drag-and-drop contract file dropzone with pulse dragover feedback.

---

## 🎨 Design System & Styling

- **Theme & CSS Tokens**: Centralized design tokens in `css/theme.css`.
- **Typography**: Google Fonts `Outfit` (headings) and `Inter` (body).
- **Glassmorphic Cards**: Frosted glass panels, glowing neon borders, radial risk exposure gauge charts, and micro-hover states.
- **SVG Vector Icons**: Universal inline SVG icons ensuring crisp rendering across all browsers.

---

## 🐳 Docker Deployment

The Frontend web application is packaged with a lightweight **Nginx Alpine** base image:

```bash
# Build Frontend Image locally
docker build -t ai-contract-frontend ./Frontend

# Run Container on Port 80
docker run -d -p 80:80 --name ai_contract_frontend ai-contract-frontend
```

Or start the complete multi-container stack with Docker Compose:

```bash
docker-compose up -d --build
```

---

## 📁 Repository Directory Structure

```text
Frontend/
├── css/                          # CSS Stylesheets & Design System
│   ├── components/               # Reusable UI Component Styles (badge, button, card, input)
│   ├── auth.css                  # Authentication Specific Layouts
│   ├── contract-detail.css       # Analysis View & Radial Risk Gauge Styles
│   ├── dashboard.css             # Sidebar & Dashboard Grid Layouts
│   ├── login.css                 # Glassmorphic Login & Registration Layouts
│   └── theme.css                 # Design Tokens & Glassmorphism Utilities
│
├── js/                           # JavaScript Logic & API Layer
│   ├── admin.js                  # Admin Control Panel & Monitoring Iframe Controller
│   ├── api.js                    # Unified REST API Layer & Streaming Chat Reader
│   ├── auth.js                   # Dual Login, Registration & OTP Verification Handlers
│   ├── contract-detail.js        # Analysis View & Token Streaming Chat Controller
│   ├── contracts.js              # Utilities (File Size Formatting, Risk Logic)
│   └── dashboard.js              # Workspace Dashboard & User Profile Controller
│
├── admin.html                    # Admin Control Panel Page
├── index.html                    # Sign In View Page (User & Admin Toggles)
├── register.html                 # Create Account & OTP Verification Page
├── dashboard.html                # Workspace Dashboard & Preferences Page
├── contract-detail.html          # Contract Analysis & RAG Streaming View Page
├── nginx.conf                    # Nginx Reverse Proxy & OWASP Security Headers (X-Frame-Options SAMEORIGIN)
├── Dockerfile                    # Containerization Setup (Nginx Alpine)
└── README.md                     # Documentation
```
