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
  deferredPrompt: null,

  async init() {
    this.initTheme();
    this.bindEvents();
    this.registerServiceWorker();
    this.initPwaInstallPrompt();
    
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

  registerServiceWorker() {
    if ("serviceWorker" in navigator) {
      window.addEventListener("load", () => {
        navigator.serviceWorker.register("/sw.js", { scope: "/" })
          .then((reg) => {
            console.log("[PWA] Service Worker registered:", reg.scope);
          })
          .catch((err) => {
            console.warn("[PWA] Service Worker registration failed:", err);
          });
      });
    }
  },

  initPwaInstallPrompt() {
    window.addEventListener("beforeinstallprompt", (e) => {
      e.preventDefault();
      this.deferredPrompt = e;
      const installBtn = document.getElementById("btn-pwa-install");
      if (installBtn) {
        installBtn.style.display = "inline-flex";
      }
    });

    window.addEventListener("appinstalled", () => {
      this.deferredPrompt = null;
      const installBtn = document.getElementById("btn-pwa-install");
      if (installBtn) installBtn.style.display = "none";
      this.showToast("PattuBook installed successfully! Enjoy your mobile app experience.", "success");
    });
  },

  async installPwa() {
    if (!this.deferredPrompt) {
      this.showToast("To install on iOS: Tap Share -> 'Add to Home Screen'. On Android: Tap browser menu -> 'Install app'.", "info");
      return;
    }
    this.deferredPrompt.prompt();
    const { outcome } = await this.deferredPrompt.userChoice;
    if (outcome === "accepted") {
      this.deferredPrompt = null;
      const installBtn = document.getElementById("btn-pwa-install");
      if (installBtn) installBtn.style.display = "none";
    }
  },

  toggleMobileDrawer() {
    const sidebar = document.getElementById("app-sidebar");
    const backdrop = document.getElementById("sidebar-backdrop");
    if (!sidebar) return;
    const isOpen = sidebar.classList.contains("drawer-open");
    if (isOpen) {
      this.closeMobileDrawer();
    } else {
      sidebar.classList.add("drawer-open");
      if (backdrop) backdrop.classList.add("active");
      document.body.classList.add("drawer-no-scroll");
    }
  },

  closeMobileDrawer() {
    const sidebar = document.getElementById("app-sidebar");
    const backdrop = document.getElementById("sidebar-backdrop");
    if (sidebar) sidebar.classList.remove("drawer-open");
    if (backdrop) backdrop.classList.remove("active");
    document.body.classList.remove("drawer-no-scroll");
  },

  renderThemeIcon(theme) {
    const themeBtn = document.getElementById("theme-toggle-btn");
    if (!themeBtn) return;
    if (theme === "dark") {
      themeBtn.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-label="Switch to light mode"><circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line></svg>`;
    } else {
      themeBtn.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-label="Switch to dark mode"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>`;
    }
  },

  initTheme() {
    const saved = localStorage.getItem("pattubook_theme") || "dark";
    document.documentElement.setAttribute("data-theme", saved);
    this.renderThemeIcon(saved);
  },

  toggleTheme() {
    const current = document.documentElement.getAttribute("data-theme") || "dark";
    const next = current === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem("pattubook_theme", next);
    this.renderThemeIcon(next);
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

    // Update desktop sidebar nav links
    document.querySelectorAll(".nav-item").forEach(item => {
      if (item.dataset.tab === tabId) item.classList.add("active");
      else item.classList.remove("active");
    });

    // Update mobile bottom nav buttons
    document.querySelectorAll(".mobile-nav-btn").forEach(btn => {
      if (btn.dataset.tab === tabId) btn.classList.add("active");
      else btn.classList.remove("active");
    });

    // Close mobile drawer on tab switch
    this.closeMobileDrawer();

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
