// PattuBook - Business Profile & System Settings
const SettingsComponent = {
  async init() {
    await this.loadSettings();
  },

  async loadSettings() {
    try {
      const res = await fetch("/api/settings");
      const s = await res.json();

      document.getElementById("set-biz-name").value = s.business_name || "";
      document.getElementById("set-owner-name").value = s.owner_name || "";
      document.getElementById("set-gstin").value = s.gstin || "";
      document.getElementById("set-upi-id").value = s.upi_id || "";
      document.getElementById("set-phone").value = s.phone || "";
      document.getElementById("set-ca-email").value = s.ca_email || "";

      // Provider and local model
      const providerEl = document.getElementById("set-ai-provider");
      if (providerEl) {
        providerEl.value = "local";
      }

      // Check Local Ollama health & models
      try {
        const localRes = await fetch("/api/system/local-ai-status");
        const localStatus = await localRes.json();
        const badgeEl = document.getElementById("settings-local-ai-badge");
        const modelSelect = document.getElementById("set-local-model");
        const noteEl = document.getElementById("local-ai-note");

        if (localStatus.available) {
          if (badgeEl) {
            badgeEl.className = "badge badge-success";
            badgeEl.innerText = `Ollama Online (${localStatus.models.length} Models)`;
          }
          if (modelSelect && localStatus.models && localStatus.models.length > 0) {
            modelSelect.innerHTML = localStatus.models.map(m => `
              <option value="${escapeHtml(m)}">${escapeHtml(m)} ${m.includes('gemma2') ? '(Recommended, 2.6B)' : (m.includes('phi3') ? '(High Accuracy, 3.8B)' : '')}</option>
            `).join("");
            modelSelect.value = s.local_ai_model || localStatus.active_model || localStatus.models[0];
          }
          if (noteEl) {
            noteEl.innerText = `Active: Running 100% locally on your machine via Ollama (${s.local_ai_model || 'gemma2:2b'}). Unlimited requests, zero cost, and 100% private financial data.`;
            noteEl.style.display = "block";
          }
        } else {
          if (badgeEl) {
            badgeEl.className = "badge badge-warning";
            badgeEl.innerText = "Ollama Offline";
          }
          if (noteEl) {
            noteEl.innerText = "Notice: Local Ollama service is starting up. Check your background terminal.";
            noteEl.style.display = "block";
          }
        }
      } catch (localErr) {
        console.warn("Could not check local AI status:", localErr);
      }

      this.onProviderChange();

      // Update navbar
      const nameEl = document.getElementById("nav-store-name");
      if (nameEl) nameEl.innerText = s.business_name || "Enterprise Store";
      const gstinEl = document.getElementById("nav-store-gstin");
      if (gstinEl) gstinEl.innerText = s.gstin ? `GSTIN: ${s.gstin}` : "GSTIN: Not Configured";
      const userEl = document.getElementById("sidebar-user-name");
      if (userEl) userEl.innerText = s.owner_name || "Business Owner";
    } catch (e) {
      console.error("Error loading settings:", e);
    }
  },

  onProviderChange() {
    const prov = document.getElementById("set-ai-provider")?.value || "local";
    const localGroup = document.getElementById("local-model-group");
    const localNote = document.getElementById("local-ai-note");

    if (localGroup) {
      localGroup.style.display = (prov === "local") ? "block" : "none";
    }
    if (localNote) {
      localNote.style.display = (prov === "local") ? "block" : "none";
    }
  },

  async saveSettings(e) {
    if (e) e.preventDefault();
    const payload = {
      business_name: document.getElementById("set-biz-name").value.trim(),
      owner_name: document.getElementById("set-owner-name").value.trim(),
      gstin: document.getElementById("set-gstin").value.trim(),
      upi_id: document.getElementById("set-upi-id").value.trim(),
      phone: document.getElementById("set-phone").value.trim(),
      ca_email: document.getElementById("set-ca-email").value.trim(),
      gemini_api_key: "",
      ai_provider: "local",
      local_ai_model: document.getElementById("set-local-model") ? document.getElementById("set-local-model").value : "gemma2:2b"
    };

    try {
      const res = await fetch("/api/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (res.ok) {
        App.showToast("Settings and AI Model configuration saved!", "success");
        await this.loadSettings();
        if (window.AssistantComponent) {
          await AssistantComponent.checkStatus();
        }
      }
    } catch (e) {
      App.showToast("Failed to save settings: " + e.message, "danger");
    }
  },

  async purgeData() {
    if (!confirm("Are you sure you want to purge all invoices, transactions, and email records? This action resets the database for a clean production start.")) {
      return;
    }

    try {
      const res = await fetch("/api/system/reset-data", { method: "POST" });
      const data = await res.json();
      if (res.ok) {
        App.showToast("Operational data purged successfully.", "success");
        // Reload components
        if (window.InvoicesComponent) await InvoicesComponent.loadInvoices();
        if (window.MISComponent) await MISComponent.loadReport();
        if (window.BriefingComponent) {
          await BriefingComponent.loadBriefing();
          await BriefingComponent.loadEmailFeed();
        }
        App.refreshGlobalKPIs();
      } else {
        App.showToast("Purge failed: " + data.detail, "danger");
      }
    } catch (e) {
      App.showToast("Network error: " + e.message, "danger");
    }
  }
};
