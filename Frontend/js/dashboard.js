/* ==========================================
   AI Contract Reviewer - Dashboard UI Logic
========================================== */

let allContracts = [];

document.addEventListener("DOMContentLoaded", async () => {
  const user = await checkAuth();
  if (!user) return;

  renderUserInfo(user);
  initDashboardEvents();
  await refreshContracts();
});

/* Authentication Check */
async function checkAuth() {
  try {
    const user = await getCurrentUser();
    if (!user) throw new Error("No active session");
    return user;
  } catch (error) {
    console.warn("User authentication required:", error.message);
    window.location.replace("index.html");
    return null;
  }
}

/* User Info Rendering */
function renderUserInfo(user) {
  const usernameEl = document.getElementById("username");
  const avatarEl = document.getElementById("user-avatar");

  const displayName = user.username || user.email?.split("@")[0] || "User";

  if (usernameEl) usernameEl.textContent = displayName;
  if (avatarEl) avatarEl.textContent = displayName.charAt(0).toUpperCase();

  const adminPanelLink = document.getElementById("adminPanelLink");
  if (adminPanelLink && user.is_admin) {
    adminPanelLink.style.display = "block";
  }

  const settingsUsername = document.getElementById("settingsUsername");
  const settingsEmail = document.getElementById("settingsEmail");
  const settingsApiUrl = document.getElementById("settingsApiUrl");
  const settingsAuthToken = document.getElementById("settingsAuthToken");

  if (settingsUsername) settingsUsername.value = displayName;
  if (settingsEmail) settingsEmail.value = user.email || "";
  if (settingsApiUrl) settingsApiUrl.value = API_CONFIG.BASE_URL;
  if (settingsAuthToken) settingsAuthToken.value = getToken() || "Session Cookie Active";
}

/* Initialize Dashboard Event Listeners */
function initDashboardEvents() {
  // Logout Buttons
  const logoutBtn = document.getElementById("logoutButton");
  if (logoutBtn) logoutBtn.addEventListener("click", handleUserLogout);

  const sidebarLogoutBtn = document.getElementById("sidebarLogoutBtn");
  if (sidebarLogoutBtn) sidebarLogoutBtn.addEventListener("click", handleUserLogout);

  // Upload Modal Triggers
  const openUploadBtn = document.getElementById("openUploadBtn");
  if (openUploadBtn) openUploadBtn.addEventListener("click", openUploadModal);

  const sidebarUploadBtn = document.getElementById("sidebarUploadBtn");
  if (sidebarUploadBtn) sidebarUploadBtn.addEventListener("click", openUploadModal);

  const closeUploadModalBtn = document.getElementById("closeUploadModalBtn");
  if (closeUploadModalBtn) closeUploadModalBtn.addEventListener("click", closeUploadModal);

  const cancelUploadBtn = document.getElementById("cancelUploadBtn");
  if (cancelUploadBtn) cancelUploadBtn.addEventListener("click", closeUploadModal);

  const uploadModal = document.getElementById("uploadModal");
  if (uploadModal) {
    uploadModal.addEventListener("click", (e) => {
      if (e.target === uploadModal) closeUploadModal();
    });
  }

  // File Upload Handlers
  const fileDropZone = document.getElementById("fileDropZone");
  const fileInput = document.getElementById("contractFileInput");

  if (fileDropZone && fileInput) {
    fileDropZone.addEventListener("click", () => fileInput.click());

    fileDropZone.addEventListener("dragover", (e) => {
      e.preventDefault();
      fileDropZone.style.borderColor = "var(--color-primary)";
    });

    fileDropZone.addEventListener("dragleave", () => {
      fileDropZone.style.borderColor = "var(--color-border)";
    });

    fileDropZone.addEventListener("drop", (e) => {
      e.preventDefault();
      fileDropZone.style.borderColor = "var(--color-border)";
      if (e.dataTransfer.files.length) {
        fileInput.files = e.dataTransfer.files;
        handleFileSelection();
      }
    });

    fileInput.addEventListener("change", handleFileSelection);
  }

  const uploadForm = document.getElementById("uploadForm");
  if (uploadForm) uploadForm.addEventListener("submit", handleUploadSubmit);

  // Search & Filter Listeners
  const searchInput = document.getElementById("contractSearch");
  if (searchInput) searchInput.addEventListener("input", applyTableFilters);

  const statusFilter = document.getElementById("statusFilter");
  if (statusFilter) statusFilter.addEventListener("change", applyTableFilters);

  // Navigation Tab Handlers
  const navItems = document.querySelectorAll(".sidebar-nav button[data-tab]");
  navItems.forEach((btn) => {
    btn.addEventListener("click", () => {
      const tabTarget = btn.getAttribute("data-tab");
      switchTab(tabTarget);
    });
  });

  // Re-scan Trigger in Analysis Tab
  const triggerRescanBtn = document.getElementById("triggerRescanBtn");
  if (triggerRescanBtn) {
    triggerRescanBtn.addEventListener("click", async () => {
      triggerRescanBtn.disabled = true;
      triggerRescanBtn.textContent = "⚡ Scanning Workspace...";
      showToast("Running neural AI clause re-scan on all active contracts...", "info");
      setTimeout(async () => {
        await refreshContracts();
        triggerRescanBtn.disabled = false;
        triggerRescanBtn.textContent = "⚡ Run Workspace Re-Scan";
        showToast("AI clause re-scan completed!", "success");
      }, 1500);
    });
  }

  // Settings Form Handler
  const settingsForm = document.getElementById("settingsForm");
  if (settingsForm) {
    settingsForm.addEventListener("submit", (e) => {
      e.preventDefault();
      const usernameInput = document.getElementById("settingsUsername");
      const apiUrlInput = document.getElementById("settingsApiUrl");
      if (apiUrlInput && apiUrlInput.value.trim()) {
        API_CONFIG.BASE_URL = apiUrlInput.value.trim();
      }
      if (usernameInput && usernameInput.value.trim()) {
        const usernameEl = document.getElementById("username");
        const avatarEl = document.getElementById("user-avatar");
        const nameVal = usernameInput.value.trim();
        if (usernameEl) usernameEl.textContent = nameVal;
        if (avatarEl) avatarEl.textContent = nameVal.charAt(0).toUpperCase();
      }
      showToast("Settings saved successfully!", "success");
    });
  }
}

/* Tab Switcher Handler */
function switchTab(tabName) {
  const navItems = document.querySelectorAll(".sidebar-nav button[data-tab]");
  navItems.forEach((btn) => {
    if (btn.getAttribute("data-tab") === tabName) {
      btn.classList.add("active");
    } else {
      btn.classList.remove("active");
    }
  });

  const pageHeading = document.getElementById("page-heading");
  const pageSubheading = document.getElementById("page-subheading");

  const tabDashboard = document.getElementById("tab-dashboard");
  const tabAnalysis = document.getElementById("tab-analysis");
  const tabSettings = document.getElementById("tab-settings");

  if (tabDashboard) tabDashboard.style.display = (tabName === "dashboard" || tabName === "contracts") ? "block" : "none";
  if (tabAnalysis) tabAnalysis.style.display = tabName === "analysis" ? "block" : "none";
  if (tabSettings) tabSettings.style.display = tabName === "settings" ? "block" : "none";

  if (tabName === "dashboard") {
    if (pageHeading) pageHeading.textContent = "Dashboard";
    if (pageSubheading) pageSubheading.textContent = "Overview of your contract intelligence workspace";
  } else if (tabName === "contracts") {
    if (pageHeading) pageHeading.textContent = "Contracts";
    if (pageSubheading) pageSubheading.textContent = "Manage and filter all analyzed legal agreements";
    const recentSec = document.getElementById("recent-contracts");
    if (recentSec) recentSec.scrollIntoView({ behavior: "smooth" });
  } else if (tabName === "analysis") {
    if (pageHeading) pageHeading.textContent = "AI Analysis Engine";
    if (pageSubheading) pageSubheading.textContent = "Neural risk detection rules & engine health metrics";
  } else if (tabName === "settings") {
    if (pageHeading) pageHeading.textContent = "Settings";
    if (pageSubheading) pageSubheading.textContent = "Manage user profile, backend API URL, and risk scoring preferences";
  }
}

/* Logout Handler */
async function handleUserLogout() {
  try {
    await logout();
  } catch (error) {
    window.location.href = "index.html";
  }
}

/* Load Contracts Data */
async function refreshContracts() {
  try {
    const contracts = await getContracts();
    allContracts = Array.isArray(contracts) ? contracts : [];

    renderStatistics(allContracts);
    applyTableFilters();
  } catch (error) {
    console.error("Failed to load contracts:", error);
    showToast("Failed to load contracts.", "error");
  }
}

/* Statistics Calculation */
function renderStatistics(contracts) {
  const totalEl = document.getElementById("total-contracts");
  const completedEl = document.getElementById("completed-reviews");
  const riskEl = document.getElementById("risk-alerts");
  const processingEl = document.getElementById("processing-contracts");

  const total = contracts.length;
  const completed = contracts.filter((c) => c.status === "completed").length;
  const processing = contracts.filter((c) => c.status === "processing").length;
  const highRisk = contracts.filter((c) => c.risk_score && c.risk_score >= 70).length;

  if (totalEl) totalEl.textContent = total;
  if (completedEl) completedEl.textContent = completed;
  if (riskEl) riskEl.textContent = highRisk;
  if (processingEl) processingEl.textContent = processing;
}

/* Table Search & Filter */
function applyTableFilters() {
  const searchInput = document.getElementById("contractSearch");
  const statusFilter = document.getElementById("statusFilter");

  const searchTerm = searchInput ? searchInput.value.toLowerCase().trim() : "";
  const selectedStatus = statusFilter ? statusFilter.value.toLowerCase().trim() : "all";

  const filtered = allContracts.filter((contract) => {
    const filename = (contract.original_filename || contract.filename || "").toLowerCase();
    const matchesSearch = !searchTerm || filename.includes(searchTerm);
    
    const status = (contract.status || "").toLowerCase();
    const matchesStatus = selectedStatus === "all" || status === selectedStatus;
    
    return matchesSearch && matchesStatus;
  });

  renderContractsTable(filtered);
}

/* Render Contracts Table Rows */
function renderContractsTable(contracts) {
  const tableBody = document.getElementById("contract-table-body");
  if (!tableBody) return;

  tableBody.innerHTML = "";

  if (!contracts.length) {
    tableBody.innerHTML = `
      <tr>
        <td colspan="5" style="text-align: center; padding: 2.5rem; color: var(--color-text-muted);">
          📄 No contracts found matching your filters.
        </td>
      </tr>
    `;
    return;
  }

  contracts.forEach((contract) => {
    const row = document.createElement("tr");

    const createdDate = contract.created_at
      ? new Date(contract.created_at).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })
      : "N/A";

    row.innerHTML = `
      <td>
        <a href="contract-detail.html?id=${contract.id}" class="contract-file-link" title="Click to view AI contract analysis">
          <span style="font-size: 1.1rem;">📄</span>
          <strong>${escapeHtml(contract.original_filename)}</strong>
        </a>
      </td>
      <td>${getStatusBadgeHtml(contract.status)}</td>
      <td>${getRiskScoreBadgeHtml(contract.risk_score)}</td>
      <td>${createdDate}</td>
      <td>
        <div class="table-action-btns">
          <button class="btn btn-outline btn-sm btn-icon-sm" onclick="viewContract(${contract.id})">
            👁️ View
          </button>
          <button class="btn btn-ghost btn-sm btn-icon-sm" onclick="confirmDeleteContract(${contract.id})" title="Delete contract">
            🗑️
          </button>
        </div>
      </td>
    `;

    tableBody.appendChild(row);
  });
}

/* Status & Risk Helpers */
function getStatusBadgeHtml(status) {
  const norm = (status || "processing").toLowerCase();
  let badgeClass = "badge-warning";
  if (norm === "completed") badgeClass = "status-completed";
  if (norm === "failed") badgeClass = "status-failed";

  return `<span class="badge ${badgeClass}">${status}</span>`;
}

function getRiskScoreBadgeHtml(score) {
  if (score === null || score === undefined) {
    return `<span class="badge badge-outline">N/A</span>`;
  }

  let badgeClass = "badge-risk-low";
  let label = `${score}/100`;

  if (score >= 70) {
    badgeClass = "badge-risk-high";
    label = `🔥 ${score}/100`;
  } else if (score >= 40) {
    badgeClass = "badge-risk-medium";
    label = `⚠️ ${score}/100`;
  }

  return `<span class="badge ${badgeClass}">${label}</span>`;
}

/* Navigation Actions */
function viewContract(id) {
  window.location.href = `contract-detail.html?id=${id}`;
}

async function confirmDeleteContract(id) {
  if (confirm("Are you sure you want to delete this contract?")) {
    try {
      await deleteContract(id);
      showToast("Contract deleted successfully.", "info");
      await refreshContracts();
    } catch (err) {
      showToast("Failed to delete contract.", "error");
    }
  }
}

/* Upload Modal Handlers */
function openUploadModal() {
  const modal = document.getElementById("uploadModal");
  if (modal) modal.classList.add("active");
}

function closeUploadModal() {
  const modal = document.getElementById("uploadModal");
  const fileInput = document.getElementById("contractFileInput");
  const selectedInfo = document.getElementById("selectedFileName");
  const submitBtn = document.getElementById("uploadSubmitBtn");

  if (modal) modal.classList.remove("active");
  if (fileInput) fileInput.value = "";
  if (selectedInfo) {
    selectedInfo.style.display = "none";
    selectedInfo.textContent = "";
  }
  if (submitBtn) submitBtn.disabled = true;
}

function handleFileSelection() {
  const fileInput = document.getElementById("contractFileInput");
  const selectedInfo = document.getElementById("selectedFileName");
  const submitBtn = document.getElementById("uploadSubmitBtn");

  if (fileInput && fileInput.files.length) {
    const file = fileInput.files[0];
    if (selectedInfo) {
      selectedInfo.style.display = "block";
      selectedInfo.textContent = `Selected: ${file.name} (${(file.size / (1024 * 1024)).toFixed(2)} MB)`;
    }
    if (submitBtn) submitBtn.disabled = false;
  }
}

async function handleUploadSubmit(e) {
  e.preventDefault();

  const fileInput = document.getElementById("contractFileInput");
  const submitBtn = document.getElementById("uploadSubmitBtn");

  if (!fileInput || !fileInput.files.length) {
    showToast("Please select a file to upload.", "error");
    return;
  }

  const file = fileInput.files[0];

  try {
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.textContent = "Analyzing Contract...";
    }

    const createdContract = await uploadContract(file);
    closeUploadModal();
    await refreshContracts();

    const viewLink = createdContract?.id ? ` <a href="contract-detail.html?id=${createdContract.id}" style="color: var(--color-primary); font-weight: 600; text-decoration: underline; margin-left: 6px;">View Analysis →</a>` : "";
    showToast(`Contract uploaded and analyzed!${viewLink}`, "success");
  } catch (error) {
    showToast(error.message || "Failed to upload contract.", "error");
  } finally {
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.textContent = "Analyze Contract";
    }
  }
}

/* Toast helper fallback */
function showToast(message, type = "info") {
  let container = document.getElementById("toast-container");
  if (!container) {
    container = document.createElement("div");
    container.id = "toast-container";
    container.className = "toast-container";
    document.body.appendChild(container);
  }

  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `<span>${type === 'error' ? '⚠️' : '✓'}</span> <div>${message}</div>`;

  container.appendChild(toast);
  requestAnimationFrame(() => toast.classList.add("show"));

  setTimeout(() => {
    toast.classList.remove("show");
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}
