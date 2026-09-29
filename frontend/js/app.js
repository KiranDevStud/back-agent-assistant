// PattuBook - Main Application Controller
function escapeHtml(text) {
  if (!text) return "";
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function escapeJsString(text) {
  if (!text) return "";
  return String(text).replace(/'/g, "\\'").replace(/"/g, '\\"');
}

// Global fetch interceptor to attach Bearer token to API calls
const originalFetch = window.fetch;
window.fetch = async function (url, options = {}) {
  const token = localStorage.getItem("pattubook_token");
  if (token && typeof url === "string" && url.startsWith("/api/")) {
    options.headers = options.headers || {};
    if (options.headers instanceof Headers) {
      if (!options.headers.has("Authorization")) {
        options.headers.set("Authorization", `Bearer ${token}`);
      }
    } else if (!options.headers["Authorization"]) {
      options.headers["Authorization"] = `Bearer ${token}`;
    }
  }
  return originalFetch(url, options);
};

const App = {
  currentTab: "briefing-view",

  async init() {
    this.initTheme();
    this.bindEvents();
    
    // Initialize components
    await AuthComponent.init();
    await IntegrationsComponent.init();
    await SettingsComponent.init();
    await BriefingComponent.init();
    await InvoicesComponent.init();
    await MISComponent.init();
    await CommsComponent.init();
    await ComplianceComponent.init();
    if (window.AssistantComponent) {
      await AssistantComponent.init();
    }

    await this.refreshGlobalKPIs();
  },

  initTheme() {
    const saved = localStorage.getItem("pattubook_theme") || "dark";
    document.documentElement.setAttribute("data-theme", saved);
    const themeBtn = document.getElementById("theme-toggle-btn");
    if (themeBtn) {
      themeBtn.innerText = saved === "dark" ? "☀️" : "🌙";
    }
  },

  toggleTheme() {
    const current = document.documentElement.getAttribute("data-theme") || "dark";
    const next = current === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem("pattubook_theme", next);
    const themeBtn = document.getElementById("theme-toggle-btn");
    if (themeBtn) {
      themeBtn.innerText = next === "dark" ? "☀️" : "🌙";
    }
    // Re-draw chart for theme background
    if (MISComponent.data) {
      MISComponent.drawChart(MISComponent.data.daily_trends);
    }
  },

  bindEvents() {
    // Nav menu tab switching
    document.querySelectorAll(".nav-item").forEach(item => {
      item.addEventListener("click", (e) => {
        e.preventDefault();
        const targetTab = item.dataset.tab;
        if (targetTab) {
          this.switchTab(targetTab);
        }
      });
    });

    // Close modal on backdrop click
    const backdrop = document.getElementById("generic-modal");
    if (backdrop) {
      backdrop.addEventListener("click", (e) => {
        if (e.target === backdrop) this.closeModal();
      });
    }
  },

  switchTab(tabId) {
    this.currentTab = tabId;

    // Update nav links
    document.querySelectorAll(".nav-item").forEach(item => {
      if (item.dataset.tab === tabId) item.classList.add("active");
      else item.classList.remove("active");
    });

    // Update page views
    document.querySelectorAll(".page-view").forEach(view => {
      if (view.id === tabId) view.classList.add("active");
      else view.classList.remove("active");
    });

    // Refresh tab-specific elements if needed
    if (tabId === "mis-view" && MISComponent.data) {
      setTimeout(() => MISComponent.drawChart(MISComponent.data.daily_trends), 50);
    } else if (tabId === "comms-view") {
      CommsComponent.generateReminderPreview();
    } else if (tabId === "integrations-view") {
      IntegrationsComponent.init();
    } else if (tabId === "assistant-view") {
      if (window.AssistantComponent) {
        window.AssistantComponent.checkStatus();
      }
    }
  },

  async refreshGlobalKPIs() {
    try {
      const res = await fetch("/api/mis/report");
      const d = await res.json();
      
      const salesEl = document.getElementById("kpi-total-sales");
      if (salesEl) salesEl.innerText = `₹ ${Number(d.total_sales || 0).toLocaleString('en-IN')}`;

      const recvEl = document.getElementById("kpi-total-receivables");
      if (recvEl) recvEl.innerText = `₹ ${Number(d.total_receivables || 0).toLocaleString('en-IN')}`;

      // GST and actions are refreshed inside their respective services
    } catch (e) {
      console.error("Error refreshing KPIs:", e);
    }
  },

  openModal() {
    const m = document.getElementById("generic-modal");
    if (m) m.classList.add("open");
  },

  closeModal() {
    const m = document.getElementById("generic-modal");
    if (m) m.classList.remove("open");
  },

  showToast(message, type = "info") {
    const container = document.getElementById("toast-container");
    if (!container) return;

    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `<span>${escapeHtml(message)}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = "0";
      toast.style.transform = "translateX(100%)";
      toast.style.transition = "all 0.3s ease";
      setTimeout(() => toast.remove(), 300);
    }, 3500);
  },

  async runQuickDemo() {
    this.showToast("Initiating Full Back Office Walkthrough...", "info");
    
    // 1. Process sample invoice
    await InvoicesComponent.processSample("Invoice_Sharma_Electricals_942.pdf");
    
    // 2. Load sample ledger
    await MISComponent.loadSampleLedger();

    // 3. Switch to overview
    this.switchTab("briefing-view");
    await BriefingComponent.init();

    this.showToast("Demo Complete: Invoice parsed, MIS calculated, Reminders queued!", "success");
  }
};

window.addEventListener("DOMContentLoaded", () => {
  App.init();
});
