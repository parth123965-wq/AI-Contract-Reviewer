# 📄 AI Contract Reviewer - Frontend Web Application

[![HTML5](https://img.shields.io/badge/HTML5-E34F26?style=for-the-badge&logo=html5&logoColor=white)](https://developer.mozilla.org/en-US/docs/Web/HTML)
[![CSS3](https://img.shields.io/badge/CSS3-1572B6?style=for-the-badge&logo=css3&logoColor=white)](https://developer.mozilla.org/en-US/docs/Web/CSS)
[![JavaScript](https://img.shields.io/badge/JavaScript-ES6%2B-F7DF1E?style=for-the-badge&logo=javascript&logoColor=black)](https://developer.mozilla.org/en-US/docs/Web/JavaScript)
[![Theme](https://img.shields.io/badge/Design-Glassmorphism%20%26%20Dark%20Mode-7B2CBF?style=for-the-badge)](#-design-system--styling)

A responsive, high-performance web interface for the **AI Contract Reviewer** ecosystem. Built with pure Vanilla HTML5, modern CSS custom properties, glassmorphic UI components, and ES6+ JavaScript modules connecting directly to the FastAPI REST backend.

---

## ✨ Key Features

- 🔑 **Authentication & Role Management**: Dual-mode login (Standard User vs. Admin Login) connecting to `/auth/login` and `/admin/auth/login`, real-time email validation, password toggles, and session verification.
- 🛡️ **Full Admin Control Panel**: Dedicated administrative interface (`admin.html`) with real-time statistics counters, user management (role promotion, activation/deactivation, account deletion), and contract overview controls.
- 💬 **Ask Document AI (RAG Assistant)**: Interactive Q&A chat assistant on the contract detail page connecting to ChromaDB vector search (`POST /contracts/{contract_id}/ask`) for context-grounded document questions.
- 📊 **Interactive Workspace Dashboard**: Overview metrics displaying total contracts, completed reviews, high-risk alerts, and processing queues.
- 🔍 **Live Search & Multi-Status Filtering**: Instant search by filename or user, with multi-status filtering (`all`, `uploaded`, `processing`, `completed`, `failed`).
- 📤 **Drag-and-Drop Contract Upload Modal**: Modal dialog supporting drag-and-drop file selection for PDF, DOCX, and TXT legal agreements.
- 🎯 **Deep Analysis Breakdown View**:
  - **Risk Score Gauge**: Visual risk indicator badge categorized into High (70+), Medium (40-69), and Low (<40) exposure levels.
  - **Executive Summaries**: Dynamic AI-generated document summaries.
  - **Identified Clause Findings**: Categorized risk findings with severity badges.
  - **Legal Recommendations**: Dynamic legal advice and compliance checklists.
- ⚙️ **REST API Configuration & Profile Settings**: User profile updates, active access token inspection, and configurable REST Backend Base URL settings.
- 🍞 **Toast Notification System**: Animated notification toasts for success, error, and progress feedback.

---

## 🎨 Design System & Styling

The application uses modern Vanilla CSS featuring:
- **Design Tokens & CSS Variables**: Centralized design tokens in `css/theme.css` for background colors, accent gradients, typography, and spacing.
- **Glassmorphic Aesthetics**: Backdrop filter blur, subtle border highlights, and dark-mode color palettes.
- **Component Architecture**: Reusable styling modules for buttons, input fields, badges, and card containers.

---

## 📁 Repository Directory Structure

```text
Frontend/
├── css/                          # CSS Stylesheets & Design System
│   ├── components/               # Reusable UI Component Styles
│   │   ├── badge.css             # Risk Score & Status Badges
│   │   ├── button.css            # Buttons, Icons & Action Styles
│   │   ├── card.css              # Glassmorphic Card Containers
│   │   └── input.css             # Form Inputs, Labels & Dropzones
│   ├── auth.css                  # Authentication Specific Layouts
│   ├── contract-detail.css       # Analysis View & Gauge Sidebar Styles
│   ├── dashboard.css             # Sidebar & Dashboard Grid Layouts
│   ├── login.css                 # Login & Registration Card Layouts
│   └── theme.css                 # Global Design Tokens & Utilities
│
├── js/                           # JavaScript Logic & API Layer
│   ├── admin.js                  # Admin Control Panel Controller & Operations
│   ├── api.js                    # Unified REST API Service & Admin Methods
│   ├── auth.js                   # Dual Login/Register Handlers & Validations
│   ├── contract-detail.js        # Detailed Analysis View & RAG Chat Controller
│   ├── contracts.js              # Utilities (File Size Formatting, Risk Logic)
│   └── dashboard.js              # Dashboard Controller & Workspace State
│
├── admin.html                    # Admin Control Panel View Page
├── index.html                    # Sign In View Page (User & Admin Toggles)
├── register.html                 # Create Account View Page
├── dashboard.html                # Workspace Dashboard & Contracts Page
├── contract-detail.html          # Contract Analysis & RAG Assistant View Page
└── README.md                     # Documentation
```

---

## 🖥️ Page Overview & Functionality

### 1. `index.html` (Sign In)
- Dual-mode sign-in interface supporting Standard User login and Admin login.
- Validates inputs, saves authorization tokens to `localStorage`, and auto-routes admins to `admin.html` and standard users to `dashboard.html`.

### 2. `admin.html` (Admin Control Panel)
- Dedicated admin portal protected by backend session verification.
- **Dashboard Overview**: Metrics for Total Users, Total Contracts, Total Analyses, Pending Queue.
- **Manage Users**: Searchable/filterable user table, activate/deactivate toggles, role promotion, user details modal, and account deletion.
- **Manage Contracts**: Status filter dropdown, filename search, status editor modal, and deletion controls.

### 3. `register.html` (Create Account)
- Account creation form connecting to `/auth/register`.
- Validates password length (8+ chars) and matching password confirmation before submission.

### 4. `dashboard.html` (Workspace Dashboard)
- Central contract intelligence workspace featuring:
  - **Sidebar Navigation**: Dashboard overview, contracts list, upload modal trigger, settings view, and dynamic `🛡️ Admin Panel` button for admin accounts.
  - **Recent Contracts Table**: Search bar, multi-status filter dropdown (`all`, `uploaded`, `processing`, `completed`, `failed`), and contract actions.
  - **Upload Modal**: File selection interface connecting to `/contracts/upload`.

### 5. `contract-detail.html` (Contract Analysis & RAG Assistant)
- In-depth clause and risk assessment view:
  - **Document Q&A (RAG Assistant)**: Interactive Q&A chat form connected to `POST /contracts/{contract_id}/ask`.
  - Executive Summary, Identified Clause Findings, Legal Recommendations, and Compliance Checklist.

---

## 🔌 API Integration & Utility Modules (`js/`)

### `api.js`
Central HTTP communication service supporting:
- Dynamic `BASE_URL` getter/setter reading from `localStorage` (`http://127.0.0.1:8000`).
- User API functions: `login()`, `register()`, `logout()`, `getCurrentUser()`, `getContracts()`, `getContractById()`, `uploadContract()`, `deleteContract()`, `askQuestionOnContract()`.
- Admin API functions: `adminLogin()`, `adminGetStats()`, `adminGetUsers()`, `adminGetUserDetail()`, `adminUpdateUserStatus()`, `adminUpdateUserRole()`, `adminDeleteUser()`, `adminGetContracts()`, `adminGetContractDetail()`, `adminUpdateContractStatus()`, `adminDeleteContract()`.

---

## 🚀 Running the Frontend Locally

### Option 1: Live Server (VS Code Extension)
1. Open the `Frontend` folder in VS Code.
2. Right-click `index.html` and select **Open with Live Server**.

### Option 2: Python Simple HTTP Server
Run a local web server from the `Frontend` directory:

```bash
cd Frontend
python -m http.server 3000
```

Open your browser at:
`http://localhost:3000`

---

## 🔗 Backend Requirements

Ensure the **AI Contract Reviewer Backend API** is running locally on `http://127.0.0.1:8000`:

```bash
# Verify backend is running
curl http://127.0.0.1:8000/docs
```

---

## 🛡️ License

Distributed under the **MIT License**.

