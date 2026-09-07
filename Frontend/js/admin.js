/* ==========================================
   AI Contract Reviewer - Admin Controller
   Handles Admin Panel Interactions & API Integration
========================================== */

document.addEventListener("DOMContentLoaded", async () => {
  // 1. Strict Authentication & Admin Access Check
  if (typeof isAuthenticated === "function" && !isAuthenticated()) {
    window.location.replace("index.html");
    return;
  }

  let user = JSON.parse(localStorage.getItem(API_CONFIG.USER_KEY) || "{}");

  // Validate session live from backend if possible
  if (typeof getCurrentUser === "function") {
    try {
      user = await getCurrentUser();
    } catch (e) {
      window.location.replace("index.html");
      return;
    }
  }

  if (!user || !user.is_admin) {
    alert("Access Denied: You need Administrator privileges to access the Admin Control Panel.");
    window.location.replace("dashboard.html");
    return;
  }

  // State Management
  const state = {
    currentTab: "dashboard",
    usersPage: 1,
    contractsPage: 1,
    usersLimit: 10,
    contractsLimit: 10,
  };

  // DOM Elements
  const adminUsername = document.getElementById("admin-username");
  const adminAvatar = document.getElementById("admin-avatar");
  const adminLogoutBtn = document.getElementById("admin-logout-btn") || document.getElementById("adminLogoutBtn");
  const modal = document.getElementById("adminModal");
  const closeModalBtn = document.getElementById("closeModalBtn");
  const closeModalFooterBtn = document.getElementById("closeModalFooterBtn");
  const modalTitle = document.getElementById("modalTitle");
  const modalBody = document.getElementById("modalBody");

  // User Profile Header Setup
  if (user && user.username) {
    if (adminUsername) adminUsername.textContent = user.username;
    if (adminAvatar) adminAvatar.textContent = user.username.charAt(0).toUpperCase();
  }

  // Logout Handler
  if (adminLogoutBtn) {
    adminLogoutBtn.addEventListener("click", () => logout());
  }

  // Modal Handlers
  const hideModal = () => {
    if (modal) modal.style.display = "none";
  };
  if (closeModalBtn) closeModalBtn.addEventListener("click", hideModal);
  if (closeModalFooterBtn) closeModalFooterBtn.addEventListener("click", hideModal);

  // Notification Toast Helper
  function showToast(message, type = "info") {
    let displayMsg = message;
    if (message && typeof message === "object") {
      if (message instanceof Error) {
        displayMsg = message.message;
      } else if (typeof message.message === "string") {
        displayMsg = message.message;
      } else if (typeof message.detail === "string") {
        displayMsg = message.detail;
      } else if (Array.isArray(message.detail)) {
        displayMsg = message.detail.map(item => (typeof item === "string" ? item : (item.msg || JSON.stringify(item)))).join("; ");
      } else {
        try {
          displayMsg = JSON.stringify(message);
        } catch {
          displayMsg = String(message);
        }
      }
    }

    const container = document.getElementById("toast-container");
    if (!container) return;
    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    toast.style.padding = "0.75rem 1rem";
    toast.style.marginBottom = "0.5rem";
    toast.style.borderRadius = "6px";
    toast.style.background = type === "danger" ? "#f7768e" : type === "success" ? "#9ece6a" : "#7aa2f8";
    toast.style.color = "#1a1b26";
    toast.style.fontWeight = "600";
    toast.textContent = displayMsg;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
  }

  // Navigation Tabs Switching
  const tabButtons = document.querySelectorAll("[data-admin-tab]");
  const tabContents = document.querySelectorAll(".admin-tab-content");

  tabButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const targetTab = btn.getAttribute("data-admin-tab");
      state.currentTab = targetTab;

      tabButtons.forEach((b) => b.classList.remove("active"));
      tabContents.forEach((c) => c.classList.remove("active"));

      btn.classList.add("active");
      const activeContent = document.getElementById(`tab-${targetTab}`);
      if (activeContent) activeContent.classList.add("active");

      // Update Headings
      const heading = document.getElementById("admin-page-heading");
      const subheading = document.getElementById("admin-page-subheading");
      if (targetTab === "dashboard") {
        if (heading) heading.textContent = "Admin Dashboard";
        if (subheading) subheading.textContent = "System statistics and overall platform control";
        loadDashboardStats();
      } else if (targetTab === "users") {
        if (heading) heading.textContent = "User Management";
        if (subheading) subheading.textContent = "View, activate/deactivate, promote or delete user accounts";
        loadUsers();
      } else if (targetTab === "contracts") {
        if (heading) heading.textContent = "Contract Management";
        if (subheading) subheading.textContent = "Review all uploaded contracts and inspect analysis states";
        loadContracts();
      } else if (targetTab === "monitoring") {
        if (heading) heading.textContent = "System Health & Monitoring";
        if (subheading) subheading.textContent = "Real-time infrastructure CPU/RAM metrics, process details, and DB/Redis latency";
        const token = getToken();
        const origin = (typeof window !== "undefined" && window.location && window.location.origin && window.location.origin !== "null" && window.location.origin !== "file://") ? window.location.origin : API_CONFIG.BASE_URL;
        const baseUrl = window.location.protocol === "https:" ? origin : API_CONFIG.BASE_URL;
        const dashboardUrl = `${baseUrl}/admin/monitoring/dashboard${token ? '?token=' + encodeURIComponent(token) : ''}`;
        const iframe = document.getElementById("monitoring-gui-iframe");
        const fullScreenBtn = document.getElementById("open-gui-fullscreen-btn");
        if (iframe) iframe.src = dashboardUrl;
        if (fullScreenBtn) fullScreenBtn.href = dashboardUrl;
      } else if (targetTab === "benchmarks") {
        if (heading) heading.textContent = "Performance Benchmarks";
        if (subheading) subheading.textContent = "System profiling across AI Engine, ChromaDB vector store, JWT security, and API throughput";
        loadBenchmarks();
      } else if (targetTab === "ai-matrix") {
        if (heading) heading.textContent = "AI Engine Matrix & Performance";
        if (subheading) subheading.textContent = "Neural AI engine health metrics, model status, and legal risk detection rules";
      }
    });
  });

  /* ==========================================
     1. DASHBOARD STATS LOGIC
  ========================================== */
  async function loadDashboardStats() {
    try {
      const stats = await adminGetStats();
      document.getElementById("stat-total-users").textContent = stats.total_users || 0;
      document.getElementById("stat-active-users").textContent = `${stats.active_users || 0} Active Users`;
      document.getElementById("stat-total-contracts").textContent = stats.total_contracts || 0;
      document.getElementById("stat-completed-contracts").textContent = `${stats.completed_contracts || 0} Completed`;
      document.getElementById("stat-total-analyses").textContent = stats.total_analyses || 0;
      document.getElementById("stat-failed-contracts").textContent = `${stats.failed_contracts || 0} Failed`;
      document.getElementById("stat-pending-contracts").textContent = stats.pending_contracts || 0;
    } catch (err) {
      showToast("Failed to load dashboard stats: " + err.message, "danger");
    }
  }

  /* ==========================================
     2. USER MANAGEMENT LOGIC
  ========================================== */
  const userSearchInput = document.getElementById("userSearchInput");
  const userActiveFilter = document.getElementById("userActiveFilter");
  const refreshUsersBtn = document.getElementById("refreshUsersBtn");
  const prevUsersBtn = document.getElementById("prevUsersBtn");
  const nextUsersBtn = document.getElementById("nextUsersBtn");

  if (refreshUsersBtn) refreshUsersBtn.addEventListener("click", () => loadUsers());
  if (userSearchInput) {
    let debounceTimer;
    userSearchInput.addEventListener("input", () => {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        state.usersPage = 1;
        loadUsers();
      }, 400);
    });
  }
  if (userActiveFilter) {
    userActiveFilter.addEventListener("change", () => {
      state.usersPage = 1;
      loadUsers();
    });
  }
  if (prevUsersBtn) {
    prevUsersBtn.addEventListener("click", () => {
      if (state.usersPage > 1) {
        state.usersPage--;
        loadUsers();
      }
    });
  }
  if (nextUsersBtn) {
    nextUsersBtn.addEventListener("click", () => {
      state.usersPage++;
      loadUsers();
    });
  }

  async function loadUsers() {
    const tbody = document.getElementById("usersTableBody");
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;">Loading users...</td></tr>`;

    try {
      const params = {
        page: state.usersPage,
        limit: state.usersLimit,
      };
      if (userSearchInput && userSearchInput.value.trim()) {
        params.search = userSearchInput.value.trim();
      }
      if (userActiveFilter && userActiveFilter.value !== "") {
        params.is_active = userActiveFilter.value;
      }

      const res = await adminGetUsers(params);
      const users = res.users || [];

      document.getElementById("usersPageInfo").textContent = `Page ${res.page} of ${res.pages || 1} (${res.total} users)`;
      prevUsersBtn.disabled = res.page <= 1;
      nextUsersBtn.disabled = res.page >= res.pages;

      if (users.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;">No users found.</td></tr>`;
        return;
      }

      tbody.innerHTML = users
        .map(
          (u) => `
        <tr>
          <td>#${u.id}</td>
          <td><strong>${u.username}</strong></td>
          <td>${u.email}</td>
          <td>
            <span class="badge ${u.is_active ? "badge-success" : "badge-danger"}">
              ${u.is_active ? "Active" : "Inactive"}
            </span>
          </td>
          <td>
            <span class="badge ${u.is_admin ? "badge-primary" : "badge-secondary"}">
              ${u.is_admin ? "Admin" : "User"}
            </span>
          </td>
          <td>${new Date(u.created_at).toLocaleDateString()}</td>
          <td>
            <button class="btn btn-ghost btn-sm view-user-btn" data-id="${u.id}">🔍 View</button>
            <button class="btn btn-secondary btn-sm toggle-status-btn" data-id="${u.id}" data-active="${u.is_active}">
              ${u.is_active ? "Deactivate" : "Activate"}
            </button>
            <button class="btn btn-secondary btn-sm toggle-role-btn" data-id="${u.id}" data-admin="${u.is_admin}">
              ${u.is_admin ? "Demote" : "Make Admin"}
            </button>
            <button class="btn btn-danger btn-sm delete-user-btn" data-id="${u.id}" data-username="${u.username}">🗑️</button>
          </td>
        </tr>
      `
        )
        .join("");

      // Attach Action Event Handlers
      tbody.querySelectorAll(".view-user-btn").forEach((btn) => {
        btn.addEventListener("click", () => openUserDetail(btn.dataset.id));
      });
      tbody.querySelectorAll(".toggle-status-btn").forEach((btn) => {
        btn.addEventListener("click", () => toggleUserStatus(btn.dataset.id, btn.dataset.active === "true"));
      });
      tbody.querySelectorAll(".toggle-role-btn").forEach((btn) => {
        btn.addEventListener("click", () => toggleUserRole(btn.dataset.id, btn.dataset.admin === "true"));
      });
      tbody.querySelectorAll(".delete-user-btn").forEach((btn) => {
        btn.addEventListener("click", () => deleteUserHandler(btn.dataset.id, btn.dataset.username));
      });
    } catch (err) {
      showToast("Error loading users: " + err.message, "danger");
      tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; color: var(--color-danger);">Failed to load users.</td></tr>`;
    }
  }

  async function openUserDetail(userId) {
    modalTitle.textContent = "User Details";
    modalBody.innerHTML = "Loading...";
    modal.style.display = "flex";

    try {
      const detail = await adminGetUserDetail(userId);
      modalBody.innerHTML = `
        <div class="modal-detail-row"><span class="modal-detail-label">User ID:</span> <span>#${detail.id}</span></div>
        <div class="modal-detail-row"><span class="modal-detail-label">Username:</span> <span><strong>${detail.username}</strong></span></div>
        <div class="modal-detail-row"><span class="modal-detail-label">Email:</span> <span>${detail.email}</span></div>
        <div class="modal-detail-row"><span class="modal-detail-label">Status:</span> <span>${detail.is_active ? "Active" : "Inactive"}</span></div>
        <div class="modal-detail-row"><span class="modal-detail-label">Role:</span> <span>${detail.is_admin ? "Administrator" : "Standard User"}</span></div>
        <div class="modal-detail-row"><span class="modal-detail-label">Joined:</span> <span>${new Date(detail.created_at).toLocaleString()}</span></div>
        <div class="modal-detail-row"><span class="modal-detail-label">Total Contracts Uploaded:</span> <span><strong>${detail.contract_count}</strong></span></div>
      `;
    } catch (err) {
      modalBody.innerHTML = `<p style="color: var(--color-danger);">Failed to fetch user details: ${err.message}</p>`;
    }
  }

  async function toggleUserStatus(userId, currentActive) {
    try {
      await adminUpdateUserStatus(userId, !currentActive);
      showToast(`User status updated successfully`, "success");
      loadUsers();
    } catch (err) {
      showToast("Failed to update status: " + err.message, "danger");
    }
  }

  async function toggleUserRole(userId, currentIsAdmin) {
    try {
      await adminUpdateUserRole(userId, !currentIsAdmin);
      showToast(`User role updated successfully`, "success");
      loadUsers();
    } catch (err) {
      showToast("Failed to update role: " + err.message, "danger");
    }
  }

  async function deleteUserHandler(userId, username) {
    if (!confirm(`Are you sure you want to delete user "${username}" (#${userId})? This will remove all their contracts and analyses!`)) {
      return;
    }
    try {
      await adminDeleteUser(userId);
      showToast(`User #${userId} deleted`, "success");
      loadUsers();
    } catch (err) {
      showToast("Failed to delete user: " + err.message, "danger");
    }
  }

  /* ==========================================
     3. CONTRACT MANAGEMENT LOGIC
  ========================================== */
  const contractSearchInput = document.getElementById("contractSearchInput");
  const contractStatusFilter = document.getElementById("contractStatusFilter");
  const refreshContractsBtn = document.getElementById("refreshContractsBtn");
  const prevContractsBtn = document.getElementById("prevContractsBtn");
  const nextContractsBtn = document.getElementById("nextContractsBtn");

  if (refreshContractsBtn) refreshContractsBtn.addEventListener("click", () => loadContracts());
  if (contractSearchInput) {
    let debounceTimer;
    contractSearchInput.addEventListener("input", () => {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        state.contractsPage = 1;
        loadContracts();
      }, 400);
    });
  }
  if (contractStatusFilter) {
    contractStatusFilter.addEventListener("change", () => {
      state.contractsPage = 1;
      loadContracts();
    });
  }
  if (prevContractsBtn) {
    prevContractsBtn.addEventListener("click", () => {
      if (state.contractsPage > 1) {
        state.contractsPage--;
        loadContracts();
      }
    });
  }
  if (nextContractsBtn) {
    nextContractsBtn.addEventListener("click", () => {
      state.contractsPage++;
      loadContracts();
    });
  }

  async function loadContracts() {
    const tbody = document.getElementById("contractsTableBody");
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;">Loading contracts...</td></tr>`;

    try {
      const params = {
        page: state.contractsPage,
        limit: state.contractsLimit,
      };
      if (contractSearchInput && contractSearchInput.value.trim()) {
        params.search = contractSearchInput.value.trim();
      }
      if (contractStatusFilter && contractStatusFilter.value !== "") {
        params.status = contractStatusFilter.value;
      }

      const res = await adminGetContracts(params);
      const contracts = res.contracts || [];

      document.getElementById("contractsPageInfo").textContent = `Page ${res.page} of ${res.pages || 1} (${res.total} contracts)`;
      prevContractsBtn.disabled = res.page <= 1;
      nextContractsBtn.disabled = res.page >= res.pages;

      if (contracts.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;">No contracts found.</td></tr>`;
        return;
      }

      tbody.innerHTML = contracts
        .map((c) => {
          let statusBadgeClass = "badge-info";
          if (c.status === "completed") statusBadgeClass = "badge-success";
          if (c.status === "failed") statusBadgeClass = "badge-danger";
          if (c.status === "processing") statusBadgeClass = "badge-warning";

          return `
        <tr>
          <td>#${c.id}</td>
          <td><strong>${c.original_filename}</strong></td>
          <td>User #${c.user_id}</td>
          <td><span class="badge ${statusBadgeClass}">${c.status}</span></td>
          <td>${(c.file_size / 1024).toFixed(1)} KB</td>
          <td>${new Date(c.created_at).toLocaleDateString()}</td>
          <td>
            <button class="btn btn-ghost btn-sm view-contract-btn" data-id="${c.id}">🔍 Detail</button>
            <button class="btn btn-secondary btn-sm change-status-btn" data-id="${c.id}" data-status="${c.status}">✏️ Status</button>
            <button class="btn btn-danger btn-sm delete-contract-btn" data-id="${c.id}" data-name="${c.original_filename}">🗑️</button>
          </td>
        </tr>
      `;
        })
        .join("");

      // Attach handlers
      tbody.querySelectorAll(".view-contract-btn").forEach((btn) => {
        btn.addEventListener("click", () => openContractDetail(btn.dataset.id));
      });
      tbody.querySelectorAll(".change-status-btn").forEach((btn) => {
        btn.addEventListener("click", () => changeContractStatusPrompt(btn.dataset.id, btn.dataset.status));
      });
      tbody.querySelectorAll(".delete-contract-btn").forEach((btn) => {
        btn.addEventListener("click", () => deleteContractHandler(btn.dataset.id, btn.dataset.name));
      });
    } catch (err) {
      showToast("Error loading contracts: " + err.message, "danger");
      tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; color: var(--color-danger);">Failed to load contracts.</td></tr>`;
    }
  }

  async function openContractDetail(contractId) {
    modalTitle.textContent = "Contract Detail & Analyses";
    modalBody.innerHTML = "Loading...";
    modal.style.display = "flex";

    try {
      const detail = await adminGetContractDetail(contractId);
      const analysesHtml =
        detail.analyses && detail.analyses.length > 0
          ? detail.analyses
              .map(
                (a) => `
            <div style="background: var(--color-surface-elevated); padding: 0.75rem; border-radius: 6px; margin-top: 0.5rem;">
              <div><strong>Risk Score:</strong> ${a.risk_score} (${a.risk_level})</div>
              <div><strong>Summary:</strong> ${a.summary || "N/A"}</div>
            </div>
          `
              )
              .join("")
          : "<em>No analyses performed yet.</em>";

      modalBody.innerHTML = `
        <div class="modal-detail-row"><span class="modal-detail-label">Contract ID:</span> <span>#${detail.id}</span></div>
        <div class="modal-detail-row"><span class="modal-detail-label">Original Filename:</span> <span><strong>${detail.original_filename}</strong></span></div>
        <div class="modal-detail-row"><span class="modal-detail-label">Owner User ID:</span> <span>#${detail.user_id}</span></div>
        <div class="modal-detail-row"><span class="modal-detail-label">Current Status:</span> <span>${detail.status}</span></div>
        <div class="modal-detail-row"><span class="modal-detail-label">File Size:</span> <span>${(detail.file_size / 1024).toFixed(1)} KB</span></div>
        <div class="modal-detail-row"><span class="modal-detail-label">Uploaded At:</span> <span>${new Date(detail.created_at).toLocaleString()}</span></div>
        <h4 style="margin-top: 1rem; color: var(--color-text-light);">Analysis History (${detail.analyses ? detail.analyses.length : 0}):</h4>
        ${analysesHtml}
      `;
    } catch (err) {
      modalBody.innerHTML = `<p style="color: var(--color-danger);">Failed to fetch contract detail: ${err.message}</p>`;
    }
  }

  async function changeContractStatusPrompt(contractId, currentStatus) {
    const newStatus = prompt(`Enter new status for contract #${contractId}\n(Options: uploaded, processing, completed, failed):`, currentStatus);
    if (!newStatus || newStatus === currentStatus) return;

    const validStatuses = ["uploaded", "processing", "completed", "failed"];
    if (!validStatuses.includes(newStatus.toLowerCase())) {
      alert("Invalid status! Must be one of: " + validStatuses.join(", "));
      return;
    }

    try {
      await adminUpdateContractStatus(contractId, newStatus.toLowerCase());
      showToast(`Contract #${contractId} status updated to ${newStatus}`, "success");
      loadContracts();
    } catch (err) {
      showToast("Failed to update contract status: " + err.message, "danger");
    }
  }

  async function deleteContractHandler(contractId, filename) {
    if (!confirm(`Are you sure you want to delete contract "${filename}" (#${contractId})?`)) {
      return;
    }

    try {
      await adminDeleteContract(contractId);
      showToast(`Contract #${contractId} deleted`, "success");
      loadContracts();
    } catch (err) {
      showToast("Failed to delete contract: " + err.message, "danger");
    }
  }

  // Performance Benchmarks Handlers
  async function loadBenchmarks() {
    const jsonOutput = document.getElementById("bench-json-output");
    const timestampElem = document.getElementById("bench-timestamp");
    const badge = document.getElementById("bench-status-badge");

    try {
      if (jsonOutput) jsonOutput.textContent = "Fetching performance benchmark metrics report...";
      const data = await adminGetBenchmarkReport();
      renderBenchmarkData(data);
    } catch (err) {
      if (jsonOutput) jsonOutput.textContent = "Failed to load benchmark report: " + err.message;
      if (badge) {
        badge.textContent = "ERROR";
        badge.className = "badge badge-danger";
      }
    }
  }

  function renderBenchmarkData(data) {
    const jsonOutput = document.getElementById("bench-json-output");
    const timestampElem = document.getElementById("bench-timestamp");
    const badge = document.getElementById("bench-status-badge");

    const chunkSpeed = document.getElementById("bench-chunk-speed");
    const embLatency = document.getElementById("bench-embedding-latency");
    const chromaLatency = document.getElementById("bench-chroma-latency");
    const jwtOps = document.getElementById("bench-jwt-ops");
    const apiRps = document.getElementById("bench-api-rps");
    const ramUsage = document.getElementById("bench-ram-usage");

    if (jsonOutput) jsonOutput.textContent = JSON.stringify(data, null, 2);
    if (timestampElem) timestampElem.textContent = `Last Run: ${data.timestamp || "Unknown"}`;
    if (badge) {
      badge.textContent = "READY";
      badge.className = "badge badge-success";
    }

    const ai = data.ai_pipeline || {};
    const api = data.api_endpoints || {};
    const res = data.system_resources || {};

    if (chunkSpeed) {
      const chars = ai.chunking?.chars_per_sec || 0;
      chunkSpeed.textContent = chars > 1000000 ? `${(chars / 1000000).toFixed(1)}M/s` : `${chars.toLocaleString()}/s`;
    }
    if (embLatency) {
      embLatency.textContent = `${ai.embeddings?.avg_ms_per_chunk || "--"} ms`;
    }
    if (chromaLatency) {
      chromaLatency.textContent = `${ai.vector_store?.avg_query_latency_ms || "--"} ms`;
    }
    if (jwtOps) {
      const ops = api.jwt_security?.creation_ops_per_sec || 0;
      jwtOps.textContent = `${ops.toLocaleString()} ops/s`;
    }
    if (apiRps) {
      apiRps.textContent = `${api.api_throughput?.requests_per_sec || 0} req/s`;
    }
    if (ramUsage) {
      ramUsage.textContent = `${res.memory_rss_mb || "--"} MB`;
    }
  }

  const runBenchmarkBtn = document.getElementById("run-benchmark-btn");
  if (runBenchmarkBtn) {
    runBenchmarkBtn.addEventListener("click", async () => {
      const jsonOutput = document.getElementById("bench-json-output");
      const badge = document.getElementById("bench-status-badge");

      try {
        runBenchmarkBtn.disabled = true;
        runBenchmarkBtn.innerHTML = `⏳ Running Benchmarks...`;
        if (jsonOutput) jsonOutput.textContent = "Executing performance benchmark suite across AI Engine, ChromaDB, JWT, and API REST endpoints...";
        if (badge) {
          badge.textContent = "RUNNING";
          badge.className = "badge badge-warning";
        }

        const freshData = await adminRunBenchmark();
        renderBenchmarkData(freshData);
        showToast("Performance benchmark execution completed!", "success");
      } catch (err) {
        showToast("Benchmark execution failed: " + err.message, "danger");
        if (jsonOutput) jsonOutput.textContent = "Execution Error: " + err.message;
        if (badge) {
          badge.textContent = "FAILED";
          badge.className = "badge badge-danger";
        }
      } finally {
        runBenchmarkBtn.disabled = false;
        runBenchmarkBtn.innerHTML = `🚀 Run Performance Benchmark`;
      }
    });
  }

  // Admin Export Audit PDF Handler
  const exportAdminPdfBtn = document.getElementById("exportAdminPdfBtn");
  if (exportAdminPdfBtn) {
    exportAdminPdfBtn.addEventListener("click", () => exportAdminReportPDF());
  }

  async function exportAdminReportPDF() {
    const totalUsers = document.getElementById("stat-total-users")?.textContent || "0";
    const totalContracts = document.getElementById("stat-total-contracts")?.textContent || "0";
    const totalAnalyses = document.getElementById("stat-total-analyses")?.textContent || "0";
    const activeUsers = document.getElementById("stat-active-users")?.textContent || "0";
    const benchChunk = document.getElementById("bench-chunk-speed")?.textContent || "--";
    const benchEmb = document.getElementById("bench-embedding-latency")?.textContent || "--";
    const benchChroma = document.getElementById("bench-chroma-latency")?.textContent || "--";
    const benchRps = document.getElementById("bench-api-rps")?.textContent || "--";
    const benchRam = document.getElementById("bench-ram-usage")?.textContent || "--";

    const dateStr = new Date().toLocaleString();

    const element = document.createElement("div");
    element.style.padding = "24px";
    element.style.fontFamily = "Arial, sans-serif";
    element.style.color = "#0f172a";
    element.style.backgroundColor = "#ffffff";

    element.innerHTML = `
      <div style="border-bottom: 2px solid #00f0ff; padding-bottom: 12px; margin-bottom: 20px;">
        <h1 style="color: #0f172a; font-size: 22px; margin: 0 0 6px 0;">🛡️ System Overview & Performance Audit Report</h1>
        <p style="color: #64748b; font-size: 13px; margin: 0;">AI Contract Reviewer Platform Administration | Date: ${dateStr}</p>
      </div>

      <h2 style="font-size: 16px; color: #0f172a; border-bottom: 1px solid #cbd5e1; padding-bottom: 4px; margin-bottom: 15px;">📊 Platform Infrastructure Metrics</h2>
      <div style="display: flex; gap: 15px; margin-bottom: 25px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px;">
        <div style="flex: 1;">
          <span style="font-size: 11px; text-transform: uppercase; color: #64748b; font-weight: bold;">Platform Users</span>
          <div style="font-size: 20px; font-weight: bold; color: #0f172a;">${totalUsers} (${activeUsers} Active)</div>
        </div>
        <div style="flex: 1;">
          <span style="font-size: 11px; text-transform: uppercase; color: #64748b; font-weight: bold;">Total Contracts</span>
          <div style="font-size: 20px; font-weight: bold; color: #0284c7;">${totalContracts}</div>
        </div>
        <div style="flex: 1;">
          <span style="font-size: 11px; text-transform: uppercase; color: #64748b; font-weight: bold;">Total AI Analyses</span>
          <div style="font-size: 20px; font-weight: bold; color: #16a34a;">${totalAnalyses}</div>
        </div>
      </div>

      <h2 style="font-size: 16px; color: #0f172a; border-bottom: 1px solid #cbd5e1; padding-bottom: 4px; margin-bottom: 15px;">⚡ Performance Benchmarks Summary</h2>
      <table style="width: 100%; border-collapse: collapse; margin-bottom: 25px; font-size: 13px;">
        <thead>
          <tr style="background: #f1f5f9; text-align: left;">
            <th style="padding: 8px; border-bottom: 1px solid #cbd5e1;">Metric</th>
            <th style="padding: 8px; border-bottom: 1px solid #cbd5e1;">Measured Value</th>
            <th style="padding: 8px; border-bottom: 1px solid #cbd5e1;">Subsystem</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td style="padding: 8px; border-bottom: 1px solid #e2e8f0;">AI Chunking Speed</td>
            <td style="padding: 8px; border-bottom: 1px solid #e2e8f0;"><strong>${benchChunk}</strong></td>
            <td style="padding: 8px; border-bottom: 1px solid #e2e8f0;">ChunkService</td>
          </tr>
          <tr>
            <td style="padding: 8px; border-bottom: 1px solid #e2e8f0;">Embedding Model Latency</td>
            <td style="padding: 8px; border-bottom: 1px solid #e2e8f0;"><strong>${benchEmb}</strong></td>
            <td style="padding: 8px; border-bottom: 1px solid #e2e8f0;">SentenceTransformers</td>
          </tr>
          <tr>
            <td style="padding: 8px; border-bottom: 1px solid #e2e8f0;">ChromaDB Vector Search</td>
            <td style="padding: 8px; border-bottom: 1px solid #e2e8f0;"><strong>${benchChroma}</strong></td>
            <td style="padding: 8px; border-bottom: 1px solid #e2e8f0;">Persistent VectorStore</td>
          </tr>
          <tr>
            <td style="padding: 8px; border-bottom: 1px solid #e2e8f0;">API Request Throughput</td>
            <td style="padding: 8px; border-bottom: 1px solid #e2e8f0;"><strong>${benchRps}</strong></td>
            <td style="padding: 8px; border-bottom: 1px solid #e2e8f0;">FastAPI REST Engine</td>
          </tr>
          <tr>
            <td style="padding: 8px; border-bottom: 1px solid #e2e8f0;">Process RAM Usage</td>
            <td style="padding: 8px; border-bottom: 1px solid #e2e8f0;"><strong>${benchRam}</strong></td>
            <td style="padding: 8px; border-bottom: 1px solid #e2e8f0;">System Resources</td>
          </tr>
        </tbody>
      </table>

      <div style="margin-top: 30px; border-top: 1px solid #e2e8f0; padding-top: 10px; text-align: center; font-size: 11px; color: #94a3b8;">
        Official Administrative System Audit Report - AI Contract Reviewer Enterprise Platform
      </div>
    `;

    const opt = {
      margin: 10,
      filename: `Admin_System_Report_${new Date().toISOString().slice(0, 10)}.pdf`,
      image: { type: 'jpeg', quality: 0.98 },
      html2canvas: { scale: 2 },
      jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' }
    };

    if (exportAdminPdfBtn) {
      exportAdminPdfBtn.disabled = true;
      exportAdminPdfBtn.textContent = "⏳ Exporting...";
    }

    if (typeof html2pdf === "function") {
      html2pdf().set(opt).from(element).save().then(() => {
        if (exportAdminPdfBtn) {
          exportAdminPdfBtn.disabled = false;
          exportAdminPdfBtn.textContent = "📄 Export Audit PDF";
        }
        showToast("Admin audit PDF report downloaded successfully!", "success");
      }).catch(err => {
        if (exportAdminPdfBtn) {
          exportAdminPdfBtn.disabled = false;
          exportAdminPdfBtn.textContent = "📄 Export Audit PDF";
        }
        showToast("Admin PDF export failed: " + err.message, "danger");
      });
    } else {
      window.print();
      if (exportAdminPdfBtn) {
        exportAdminPdfBtn.disabled = false;
        exportAdminPdfBtn.textContent = "📄 Export Audit PDF";
      }
    }
  }

  // Initial Load
  loadDashboardStats();
});


