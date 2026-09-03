/* ==========================================
   AI Contract Reviewer - Unified API Service
   Connects to Backend REST API
========================================== */

const API_CONFIG = {
  get BASE_URL() {
    return localStorage.getItem("ai_contract_base_url") || "http://127.0.0.1:8000";
  },
  set BASE_URL(url) {
    localStorage.setItem("ai_contract_base_url", url);
  },
  TOKEN_KEY: "ai_contract_token",
  USER_KEY: "ai_contract_user",
  TIMEOUT_MS: 15000,
};

/* Token & Session Management */
function saveToken(token) {
  if (token) {
    localStorage.setItem(API_CONFIG.TOKEN_KEY, token);
  }
}

function getToken() {
  return localStorage.getItem(API_CONFIG.TOKEN_KEY);
}

function removeToken() {
  localStorage.removeItem(API_CONFIG.TOKEN_KEY);
  localStorage.removeItem(API_CONFIG.USER_KEY);
}

function isAuthenticated() {
  return !!getToken();
}

/* HTTP Request Core */
async function apiRequest(endpoint, options = {}) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), API_CONFIG.TIMEOUT_MS);

  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };

  const token = getToken();
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  let response;
  try {
    response = await fetch(`${API_CONFIG.BASE_URL}${endpoint}`, {
      ...options,
      headers,
      signal: controller.signal,
      credentials: "include",
    });
    clearTimeout(timeoutId);
  } catch (err) {
    clearTimeout(timeoutId);
    if (err.name === "AbortError") {
      throw new Error("Request timed out. Please check backend server connection.");
    }
    throw new Error("Cannot connect to backend server. Make sure FastAPI server is running.");
  }

  let data = null;
  const contentType = response.headers.get("content-type");
  if (contentType && contentType.includes("application/json")) {
    try {
      data = await response.json();
    } catch {
      data = null;
    }
  }

  if (!response.ok) {
    if (response.status === 401 && !endpoint.startsWith("/auth/")) {
      removeToken();
      if (!window.location.pathname.endsWith("index.html") && !window.location.pathname.endsWith("register.html")) {
        window.location.href = "index.html";
      }
    }
    const errMsg = data?.detail || data?.message || `Request failed with status ${response.status}`;
    throw new Error(errMsg);
  }

  return data;
}

/* Helper to normalize API contract objects into uniform frontend schema */
function normalizeContractData(c) {
  if (!c) return null;

  const id = c.id !== undefined ? c.id : c.contract_id;
  const original_filename = c.original_filename || c.filename || "Untitled Contract";
  const status = c.status || "processing";

  // Parse file size bytes
  let file_size = "N/A";
  if (typeof c.file_size === "number") {
    file_size = ContractUtils ? ContractUtils.formatFileSize(c.file_size) : `${(c.file_size / 1024).toFixed(1)} KB`;
  } else if (typeof c.file_size === "string") {
    file_size = c.file_size;
  }

  const created_at = c.created_at || new Date().toISOString();

  // Extract analysis fields if present (from computed property or latest_analysis)
  const latest = c.latest_analysis || (c.analyses && c.analyses.length ? c.analyses[c.analyses.length - 1] : null);
  
  const summary = c.summary || latest?.summary || (status === "processing" 
    ? "AI engine is currently analyzing contract clauses and calculating risk scores..." 
    : "No summary available for this document.");

  const risk_score = c.risk_score !== undefined && c.risk_score !== null 
    ? c.risk_score 
    : (latest?.risk_score !== undefined ? latest.risk_score : null);

  const risk_level = c.risk_level || latest?.risk_level || null;
  const recommendations = latest?.recommendations || c.recommendations || "";

  // Normalize key findings
  let key_findings = [];
  if (Array.isArray(c.key_findings) && c.key_findings.length > 0) {
    key_findings = c.key_findings;
  } else if (recommendations) {
    const recList = recommendations.split("\n").map(r => r.trim()).filter(Boolean);
    const levelStr = (risk_level || "medium").toLowerCase();
    key_findings = recList.map((rec, idx) => ({
      type: levelStr,
      clause: `Finding #${idx + 1}`,
      description: rec
    }));
  } else if (latest?.high_risk_clause) {
    key_findings = [{
      type: (risk_level || "high").toLowerCase(),
      clause: "High Exposure Clause",
      description: typeof latest.high_risk_clause === "string" ? latest.high_risk_clause : JSON.stringify(latest.high_risk_clause)
    }];
  }

  return {
    id,
    original_filename,
    status,
    file_size,
    content_type: c.content_type || "application/pdf",
    created_at,
    summary,
    risk_score,
    risk_level,
    recommendations,
    key_findings,
    latest_analysis: latest,
    ...c,
  };
}

/* API Service Methods */
async function apiGet(endpoint) {
  return apiRequest(endpoint, { method: "GET" });
}

async function apiPost(endpoint, body, extra = {}) {
  return apiRequest(endpoint, {
    method: "POST",
    body: JSON.stringify(body),
    ...extra,
  });
}

async function apiDelete(endpoint) {
  return apiRequest(endpoint, { method: "DELETE" });
}

/* Domain Specific API Calls */
async function login(email, password) {
  const res = await apiPost("/auth/login", { email, password });
  if (res && res.access_token) {
    saveToken(res.access_token);
  }
  if (res && res.user) {
    localStorage.setItem(API_CONFIG.USER_KEY, JSON.stringify(res.user));
  }
  return res;
}

async function register(email, password, username) {
  const res = await apiPost("/auth/register", { email, password, username });
  if (res && res.access_token) {
    saveToken(res.access_token);
  } else {
    // If registration succeeds without automatic login token, perform login
    const loginRes = await login(email, password);
    return loginRes;
  }
  return res;
}

async function logout() {
  try {
    await apiPost("/auth/logout");
  } catch {
    // Ignore error if offline
  } finally {
    removeToken();
    window.location.href = "index.html";
  }
}

async function getCurrentUser() {
  const user = await apiGet("/users/me");
  if (user) {
    localStorage.setItem(API_CONFIG.USER_KEY, JSON.stringify(user));
  }
  return user;
}

async function getContracts() {
  const data = await apiGet("/contracts");
  if (Array.isArray(data)) {
    return data.map(normalizeContractData);
  }
  if (data && Array.isArray(data.contracts)) {
    return data.contracts.map(normalizeContractData);
  }
  return [];
}

async function getContractById(id) {
  const data = await apiGet(`/contracts/${id}`);
  return normalizeContractData(data);
}

async function uploadContract(file) {
  const formData = new FormData();
  formData.append("file", file);
  
  const token = getToken();
  const headers = token ? { Authorization: `Bearer ${token}` } : {};

  const response = await fetch(`${API_CONFIG.BASE_URL}/contracts/upload`, {
    method: "POST",
    headers,
    body: formData,
    credentials: "include",
  });

  if (!response.ok) {
    let errData;
    try {
      errData = await response.json();
    } catch {
      errData = null;
    }
    throw new Error(errData?.detail || errData?.message || "Failed to upload contract.");
  }

  const resData = await response.json();
  return normalizeContractData(resData);
}

async function deleteContract(id) {
  return apiDelete(`/contracts/${id}`);
}

async function askQuestionOnContract(contractId, question) {
  return apiPost(`/contracts/${contractId}/ask`, { question });
}

/* Admin API Methods */
async function adminLogin(email, password) {
  const res = await apiPost("/admin/auth/login", { email, password });
  if (res && res.access_token) {
    saveToken(res.access_token);
  }
  if (res && res.user) {
    localStorage.setItem(API_CONFIG.USER_KEY, JSON.stringify(res.user));
  }
  return res;
}

async function adminGetStats() {
  return apiGet("/admin/dashboard/stats");
}

async function adminGetUsers(params = {}) {
  const query = new URLSearchParams(params).toString();
  return apiGet(`/admin/users${query ? "?" + query : ""}`);
}

async function adminGetUserDetail(userId) {
  return apiGet(`/admin/users/${userId}`);
}

async function adminUpdateUserStatus(userId, isActive) {
  return apiRequest(`/admin/users/${userId}/status`, {
    method: "PATCH",
    body: JSON.stringify({ is_active: isActive }),
  });
}

async function adminUpdateUserRole(userId, isAdmin) {
  return apiRequest(`/admin/users/${userId}/role`, {
    method: "PATCH",
    body: JSON.stringify({ is_admin: isAdmin }),
  });
}

async function adminDeleteUser(userId) {
  return apiDelete(`/admin/users/${userId}`);
}

async function adminGetContracts(params = {}) {
  const query = new URLSearchParams(params).toString();
  return apiGet(`/admin/contracts${query ? "?" + query : ""}`);
}

async function adminGetContractDetail(contractId) {
  return apiGet(`/admin/contracts/${contractId}`);
}

async function adminUpdateContractStatus(contractId, status) {
  return apiRequest(`/admin/contracts/${contractId}/status`, {
    method: "PATCH",
    body: JSON.stringify({ status: status }),
  });
}

async function adminDeleteContract(contractId) {
  return apiDelete(`/admin/contracts/${contractId}`);
}



