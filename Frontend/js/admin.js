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
    toast.textContent = message;
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

  // Initial Load
  loadDashboardStats();
});
