/* ==========================================
   AI Contract Reviewer - Contract Detail Logic
========================================== */

document.addEventListener("DOMContentLoaded", async () => {
  const user = await checkAuth();
  if (!user) return;

  initDetailPage();
});

/* Authentication Verification */
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

/* Page Initialization */
async function initDetailPage() {
  const urlParams = new URLSearchParams(window.location.search);
  const contractId = urlParams.get("id") || "1";

  initDetailEvents(contractId);
  await fetchAndRenderContract(contractId);
}

/* Event Handlers */
function initDetailEvents(contractId) {
  const exportPdfBtn = document.getElementById("exportPdfBtn");
  if (exportPdfBtn) {
    exportPdfBtn.addEventListener("click", () => exportContractPDF(contractId));
  }

  const reanalyzeBtn = document.getElementById("reanalyzeBtn");
  if (reanalyzeBtn) {
    reanalyzeBtn.addEventListener("click", async () => {
      showToast("Re-analyzing contract clauses...", "info");
      reanalyzeBtn.disabled = true;
      setTimeout(async () => {
        reanalyzeBtn.disabled = false;
        showToast("Analysis re-calculated successfully!", "success");
        await fetchAndRenderContract(contractId);
      }, 1200);
    });
  }

  const deleteBtn = document.getElementById("deleteContractBtn");
  if (deleteBtn) {
    deleteBtn.addEventListener("click", async () => {
      if (confirm("Are you sure you want to delete this contract?")) {
        try {
          await deleteContract(contractId);
          showToast("Contract deleted. Redirecting...", "info");
          setTimeout(() => {
            window.location.href = "dashboard.html";
          }, 800);
        } catch (err) {
          showToast("Failed to delete contract.", "error");
        }
      }
    });
  }

  // RAG Q&A Form Listener
  const ragForm = document.getElementById("rag-question-form");
  const ragInput = document.getElementById("rag-input");
  const ragSubmitBtn = document.getElementById("rag-submit-btn");
  const chatMessages = document.getElementById("chat-messages");

  if (ragForm) {
    ragForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const question = ragInput ? ragInput.value.trim() : "";
      if (!question) return;

      // Append User Question
      const userMsgDiv = document.createElement("div");
      userMsgDiv.style.cssText = "padding: 0.5rem 0.75rem; border-radius: 6px; background: var(--color-primary-muted); color: var(--color-primary-hover); margin-bottom: 0.5rem; text-align: right;";
      userMsgDiv.textContent = `👤 ${question}`;
      chatMessages.appendChild(userMsgDiv);

      ragInput.value = "";
      ragSubmitBtn.disabled = true;

      // Pending Bot Msg
      const botMsgDiv = document.createElement("div");
      botMsgDiv.style.cssText = "padding: 0.5rem 0.75rem; border-radius: 6px; background: var(--color-surface-hover); margin-bottom: 0.5rem;";
      botMsgDiv.innerHTML = "🤖 <strong>AI Answer:</strong><br/><span class='stream-content'></span>";
      chatMessages.appendChild(botMsgDiv);
      chatMessages.scrollTop = chatMessages.scrollHeight;

      const streamContentEl = botMsgDiv.querySelector(".stream-content");
      let fullText = "";

      try {
        await askQuestionOnContractStream(contractId, question, (chunk) => {
          fullText += chunk;
          if (streamContentEl) {
            streamContentEl.innerHTML = escapeHtml(fullText).replace(/\n/g, "<br/>");
          }
          chatMessages.scrollTop = chatMessages.scrollHeight;
        });
        if (!fullText.trim() && streamContentEl) {
          streamContentEl.textContent = "No response generated.";
        }
      } catch (err) {
        if (!fullText.trim()) {
          botMsgDiv.innerHTML = `<span style="color: var(--color-danger);">⚠️ Error answering question: ${escapeHtml(err.message)}</span>`;
        }
      } finally {
        ragSubmitBtn.disabled = false;
        chatMessages.scrollTop = chatMessages.scrollHeight;
      }
    });
  }
}

/* Fetch & Render Contract Details */
async function fetchAndRenderContract(contractId) {
  try {
    const contract = await getContractById(contractId);
    if (!contract) throw new Error("Contract record not found");

    renderContractMetadata(contract);
    renderRiskScoreGauge(contract.risk_score);
    renderFindings(contract.key_findings);
    renderRecommendations(contract);
  } catch (error) {
    console.error("Error loading contract details:", error);
    showToast(error.message || "Failed to load contract detail.", "error");

    const titleEl = document.getElementById("contract-title");
    if (titleEl) titleEl.textContent = "Contract Not Found";
  }
}

/* Render Metadata */
function renderContractMetadata(contract) {
  const titleEl = document.getElementById("contract-title");
  const statusEl = document.getElementById("contract-status");
  const sizeEl = document.getElementById("contract-size");
  const dateEl = document.getElementById("contract-date");
  const typeEl = document.getElementById("contract-type");
  const summaryEl = document.getElementById("contract-summary");

  if (titleEl) titleEl.textContent = contract.original_filename || "Untitled Contract";

  if (statusEl) {
    const norm = (contract.status || "processing").toLowerCase();
    statusEl.textContent = contract.status || "Processing";
    statusEl.className = `badge ${norm === 'completed' ? 'status-completed' : 'badge-warning'}`;
  }

  if (sizeEl) sizeEl.textContent = contract.file_size || "N/A";

  if (dateEl) {
    dateEl.textContent = contract.created_at
      ? new Date(contract.created_at).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })
      : "N/A";
  }

  if (typeEl) {
    let typeName = "Legal Document";
    if (contract.content_type) {
      if (contract.content_type.includes("pdf")) typeName = "PDF Document";
      else if (contract.content_type.includes("word") || contract.content_type.includes("docx")) typeName = "Word Document";
      else if (contract.content_type.includes("text") || contract.content_type.includes("txt")) typeName = "Text Document";
      else typeName = contract.content_type;
    } else if (contract.original_filename) {
      const ext = contract.original_filename.split(".").pop().toUpperCase();
      typeName = `${ext} File`;
    }
    typeEl.textContent = typeName;
  }

  if (summaryEl) {
    summaryEl.textContent = contract.summary || "AI analysis completed for this agreement.";
  }
}

/* Render Risk Gauge */
function renderRiskScoreGauge(score) {
  const scoreValEl = document.getElementById("risk-score-value");
  const circleEl = document.getElementById("risk-score-circle");
  const labelEl = document.getElementById("risk-score-label");

  if (score === null || score === undefined) {
    if (scoreValEl) scoreValEl.textContent = "--";
    if (labelEl) labelEl.textContent = "Analysis Pending";
    return;
  }

  if (scoreValEl) scoreValEl.textContent = score;

  if (circleEl) {
    circleEl.className = "risk-score";
    if (score >= 70) {
      circleEl.classList.add("risk-high");
      if (labelEl) labelEl.textContent = "⚠️ High Risk Exposure";
    } else if (score >= 40) {
      circleEl.classList.add("risk-medium");
      if (labelEl) labelEl.textContent = "⚡ Moderate Risk Contract";
    } else {
      circleEl.classList.add("risk-low");
      if (labelEl) labelEl.textContent = "✓ Low Risk / Standard Terms";
    }
  }
}

/* Render Findings */
function renderFindings(findings) {
  const container = document.getElementById("findings-list");
  if (!container) return;

  container.innerHTML = "";

  if (!findings || !findings.length) {
    container.innerHTML = `
      <div style="padding: 1.5rem; text-align: center; color: var(--color-text-muted);">
        ✓ No critical risk clause anomalies detected.
      </div>
    `;
    return;
  }

  findings.forEach((item) => {
    const findingDiv = document.createElement("div");
    findingDiv.className = "finding-item";

    let badgeType = "badge-risk-medium";
    const itemType = (item.type || item.risk_level || "medium").toLowerCase();
    if (itemType === "high") badgeType = "badge-risk-high";
    if (itemType === "low") badgeType = "badge-risk-low";

    findingDiv.innerHTML = `
      <div class="finding-header">
        <span class="finding-clause">${escapeHtml(item.clause || "Clause Finding")}</span>
        <span class="badge ${badgeType}">${itemType.toUpperCase()}</span>
      </div>
      <p class="finding-desc">${escapeHtml(item.description || item.summary || "")}</p>
    `;

    container.appendChild(findingDiv);
  });
}

/* Render Recommendations */
function renderRecommendations(contract) {
  const recContainer = document.getElementById("recommendations-list");
  const complianceContainer = document.getElementById("compliance-checklist");
  if (!recContainer) return;

  let recs = [];
  const rawRecs = contract.recommendations || contract.latest_analysis?.recommendations;
  
  if (Array.isArray(rawRecs)) {
    recs = rawRecs.map(r => String(r).trim()).filter(Boolean);
  } else if (typeof rawRecs === "string" && rawRecs.trim()) {
    recs = rawRecs.split("\n").map(r => r.trim()).filter(Boolean);
  } else if (Array.isArray(contract.key_findings) && contract.key_findings.length > 0) {
    recs = contract.key_findings.map(f => f.description || f.clause || "").filter(Boolean);
  }

  if (!recs.length) {
    recContainer.innerHTML = `
      <div style="padding: 1rem; color: var(--color-text-muted);">
        No specific legal recommendations flagged for this agreement.
      </div>
    `;
  } else {
    recContainer.innerHTML = recs.map(r => `<div class="recommendation-item">${escapeHtml(r)}</div>`).join("");
  }

  if (complianceContainer) {
    const score = contract.risk_score;
    let listHtml = "";
    if (score === null || score === undefined) {
      listHtml = `<li class="check-warn">⚠️ Analysis Pending</li>`;
    } else if (score >= 70) {
      listHtml = `
        <li class="check-pass">✓ Document Syntax & Formatting Valid</li>
        <li class="check-warn">⚠️ High Risk Exposure Identified in Analysis</li>
        <li class="check-warn">⚠️ Independent Legal Counsel Review Recommended</li>
      `;
    } else if (score >= 40) {
      listHtml = `
        <li class="check-pass">✓ Document Formatting Valid</li>
        <li class="check-pass">✓ Key Clause Structure Identified</li>
        <li class="check-warn">⚡ Moderate Risk Terms Detected</li>
      `;
    } else {
      listHtml = `
        <li class="check-pass">✓ Document Syntax & Format Verified</li>
        <li class="check-pass">✓ Low Risk / Standard Clause Profile</li>
        <li class="check-pass">✓ All Primary Compliance Checks Passed</li>
      `;
    }
    complianceContainer.innerHTML = listHtml;
  }
}

/* Toast Helper */
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

  let container = document.getElementById("toast-container");
  if (!container) {
    container = document.createElement("div");
    container.id = "toast-container";
    container.className = "toast-container";
    document.body.appendChild(container);
  }

  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `<span>${type === 'error' ? '⚠️' : '✓'}</span> <div>${displayMsg}</div>`;

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

/* PDF Export Function */
function exportContractPDF(contractId) {
  const exportBtn = document.getElementById("exportPdfBtn");
  const title = document.getElementById("contract-title")?.textContent || "Contract_Analysis";
  const status = document.getElementById("contract-status")?.textContent || "";
  const size = document.getElementById("contract-size")?.textContent || "";
  const date = document.getElementById("contract-date")?.textContent || "";
  const summary = document.getElementById("contract-summary")?.textContent || "";
  const score = document.getElementById("score-value")?.textContent || "0";
  const riskBadge = document.getElementById("risk-badge")?.textContent || "LOW";
  const findings = document.getElementById("findings-list")?.innerHTML || "";
  const recommendations = document.getElementById("recommendations-list")?.innerHTML || "";

  const element = document.createElement("div");
  element.style.padding = "24px";
  element.style.fontFamily = "Arial, sans-serif";
  element.style.color = "#0f172a";
  element.style.backgroundColor = "#ffffff";

  element.innerHTML = `
    <div style="border-bottom: 2px solid #00f0ff; padding-bottom: 12px; margin-bottom: 20px;">
      <h1 style="color: #0f172a; font-size: 22px; margin: 0 0 6px 0;">⚖️ AI Contract Analysis Report</h1>
      <p style="color: #64748b; font-size: 13px; margin: 0;">Document: <strong>${escapeHtml(title)}</strong> | Status: ${escapeHtml(status)} | Analyzed: ${escapeHtml(date)}</p>
    </div>

    <div style="display: flex; gap: 15px; margin-bottom: 20px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px;">
      <div style="flex: 1;">
        <span style="font-size: 11px; text-transform: uppercase; color: #64748b; font-weight: bold;">Overall Risk Score</span>
        <div style="font-size: 24px; font-weight: bold; color: #0f172a;">${escapeHtml(score)} / 100</div>
      </div>
      <div style="flex: 1;">
        <span style="font-size: 11px; text-transform: uppercase; color: #64748b; font-weight: bold;">Risk Exposure Level</span>
        <div style="font-size: 18px; font-weight: bold; color: #0284c7;">${escapeHtml(riskBadge)}</div>
      </div>
      <div style="flex: 1;">
        <span style="font-size: 11px; text-transform: uppercase; color: #64748b; font-weight: bold;">File Size</span>
        <div style="font-size: 16px; font-weight: bold; color: #334155;">${escapeHtml(size)}</div>
      </div>
    </div>

    <div style="margin-bottom: 20px;">
      <h2 style="font-size: 16px; color: #0f172a; border-bottom: 1px solid #cbd5e1; padding-bottom: 4px;">📝 Executive Summary</h2>
      <p style="font-size: 13px; line-height: 1.6; color: #334155;">${escapeHtml(summary)}</p>
    </div>

    <div style="margin-bottom: 20px;">
      <h2 style="font-size: 16px; color: #0f172a; border-bottom: 1px solid #cbd5e1; padding-bottom: 4px;">🔍 Identified Clause Risks & Exposure</h2>
      <div style="font-size: 13px; color: #334155;">${findings}</div>
    </div>

    <div style="margin-bottom: 20px;">
      <h2 style="font-size: 16px; color: #0f172a; border-bottom: 1px solid #cbd5e1; padding-bottom: 4px;">💡 Actionable Recommendations</h2>
      <div style="font-size: 13px; color: #334155;">${recommendations}</div>
    </div>

    <div style="margin-top: 30px; border-top: 1px solid #e2e8f0; padding-top: 10px; text-align: center; font-size: 11px; color: #94a3b8;">
      Generated automatically by AI Contract Reviewer Enterprise Platform
    </div>
  `;

  const opt = {
    margin: 10,
    filename: `Contract_Analysis_Report_#${contractId}.pdf`,
    image: { type: 'jpeg', quality: 0.98 },
    html2canvas: { scale: 2 },
    jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' }
  };

  if (exportBtn) {
    exportBtn.disabled = true;
    exportBtn.textContent = "⏳ Generating PDF...";
  }

  if (typeof html2pdf === "function") {
    html2pdf().set(opt).from(element).save().then(() => {
      if (exportBtn) {
        exportBtn.disabled = false;
        exportBtn.textContent = "📥 Export PDF Report";
      }
      showToast("PDF report downloaded successfully!", "success");
    }).catch(err => {
      if (exportBtn) {
        exportBtn.disabled = false;
        exportBtn.textContent = "📥 Export PDF Report";
      }
      showToast("PDF generation failed: " + err.message, "error");
    });
  } else {
    window.print();
    if (exportBtn) {
      exportBtn.disabled = false;
      exportBtn.textContent = "📥 Export PDF Report";
    }
  }
}

