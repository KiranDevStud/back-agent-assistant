// PattuBook - Cross-Platform Integrations Hub Controller

const IntegrationsComponent = {
  statusData: null,

  async init() {
    await this.loadStatus();
    this.renderCards();
  },

  async loadStatus() {
    try {
      const headers = (typeof AuthComponent !== "undefined" && AuthComponent.getAuthHeaders)
        ? AuthComponent.getAuthHeaders()
        : { "Content-Type": "application/json" };
      const res = await fetch("/api/integrations/status", { headers });
      if (res.ok) {
        this.statusData = await res.json();
      }
    } catch (e) {
      console.warn("Could not fetch integrations status:", e);
    }
  },

  renderCards() {
    const container = document.getElementById("integrations-cards-grid");
    if (!container) return;

    const data = this.statusData || {};
    const dbInfo = data.database || { engine: "SQLite (Local Dev)", is_postgres: false };
    const isGmailConnected = data.gmail && data.gmail.imap_configured;
    const isUserSignedIn = (typeof AuthComponent !== "undefined" && AuthComponent.currentUser);
    const gmailAccountName = (data.gmail && data.gmail.imap_user) || (isUserSignedIn ? "No account connected" : "Sign in to connect Gmail");

    container.innerHTML = `
      <!-- Card 1: Google Calendar -->
      <div class="glass-panel" style="display: flex; flex-direction: column; justify-content: space-between;">
        <div>
          <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px;">
            <div style="display: flex; align-items: center; gap: 10px;">
              <div class="kpi-icon-bubble" style="background: rgba(66, 133, 244, 0.15); color: #4285f4; font-size: 1rem; font-weight: 700;">GC</div>
              <div>
                <h3 style="font-size: 1.1rem; font-weight: 700;">Google Calendar</h3>
                <div style="font-size: 0.78rem; color: var(--text-muted);">Compliance & Invoice Due Date Sync</div>
              </div>
            </div>
            <span class="status-badge status-paid">Connected</span>
          </div>
          <p style="font-size: 0.84rem; color: var(--text-secondary); line-height: 1.5; margin-bottom: 14px;">
            Automatically pushes GSTR-1, GSTR-3B, TDS, and Advance Tax statutory deadlines plus customer invoice payment due dates into Google Calendar.
          </p>
          <ul style="font-size: 0.8rem; color: var(--text-muted); list-style: none; padding: 0; margin-bottom: 18px; display: flex; flex-direction: column; gap: 6px;">
            <li>- 1-Click Direct Calendar Add buttons</li>
            <li>- Live iCal (.ics) perpetual auto-sync feed</li>
            <li>- Automatic penalty prevention alerts</li>
          </ul>
        </div>
        <div style="display: flex; flex-direction: column; gap: 8px;">
          <button class="btn btn-primary btn-sm" style="width: 100%;" onclick="IntegrationsComponent.addAllDeadlinesToCalendar()">
            Add All Deadlines to Google Calendar
          </button>
          <button class="btn btn-secondary btn-sm" style="width: 100%;" onclick="IntegrationsComponent.copyIcalFeedUrl()">
            Copy Live iCal (.ics) Feed URL
          </button>
          <button class="btn btn-secondary btn-sm" style="width: 100%;" onclick="IntegrationsComponent.showCalendarGuide()">
            How to Connect Calendar
          </button>
        </div>
      </div>

      <!-- Card 2: Gmail & Workspace (IMAP Auto-Sync) -->
      <div class="glass-panel" style="display: flex; flex-direction: column; justify-content: space-between;">
        <div>
          <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px;">
            <div style="display: flex; align-items: center; gap: 10px;">
              <div class="kpi-icon-bubble" style="background: rgba(234, 67, 53, 0.15); color: #ea4335; font-size: 1rem; font-weight: 700;">GM</div>
              <div>
                <h3 style="font-size: 1.1rem; font-weight: 700;">Gmail / Workspace</h3>
                <div style="font-size: 0.78rem; color: var(--text-muted);">AI Ingestion & Auto-Sync</div>
              </div>
            </div>
            <span class="status-badge ${isGmailConnected ? 'status-paid' : 'status-pending'}">
              ${isGmailConnected ? 'Connected & Active' : (isUserSignedIn ? 'Not Connected' : 'Sign In Required')}
            </span>
          </div>
          <p style="font-size: 0.84rem; color: var(--text-secondary); line-height: 1.5; margin-bottom: 14px;">
            ${isGmailConnected 
              ? 'Automatically polls inbox communications for supplier bills, bank NEFT/UPI alerts, and tax notices with AI summary and auto-OCR.'
              : 'Connect your personal Gmail inbox with a secure Google App Password to automatically ingest your invoices, bills, and payment alerts.'}
          </p>
          <ul style="font-size: 0.8rem; color: var(--text-muted); list-style: none; padding: 0; margin-bottom: 18px; display: flex; flex-direction: column; gap: 6px;">
            <li>- <strong>Account:</strong> <span style="color: ${isGmailConnected ? 'var(--accent-success)' : 'var(--text-muted)'}; font-weight: 600;">${escapeHtml(gmailAccountName)}</span></li>
            <li>- <strong>Status:</strong> ${isGmailConnected ? 'Background worker active (SSL :993)' : 'Ready for connection'}</li>
          </ul>
        </div>
        <div style="display: flex; flex-direction: column; gap: 8px;">
          ${isGmailConnected ? `
            <button class="btn btn-primary btn-sm" style="width: 100%;" id="btn-sync-gmail" onclick="IntegrationsComponent.syncGmailInbox()">
              Sync Inbox Now
            </button>
            <button class="btn btn-secondary btn-sm" style="width: 100%;" onclick="IntegrationsComponent.openCaEmailComposer()">
              Draft CA Filing Package via Gmail
            </button>
            <button class="btn btn-secondary btn-sm" style="width: 100%; color: var(--accent-danger);" onclick="IntegrationsComponent.disconnectGmail()">
              Disconnect Gmail Account
            </button>
          ` : (isUserSignedIn ? `
            <button class="btn btn-primary btn-sm" style="width: 100%;" onclick="IntegrationsComponent.openConnectGmailModal()">
              Connect Personal Gmail
            </button>
            <button class="btn btn-secondary btn-sm" style="width: 100%;" onclick="IntegrationsComponent.showGmailGuide()">
              How to Generate App Password
            </button>
          ` : `
            <button class="btn btn-primary btn-sm" style="width: 100%;" onclick="AuthComponent.openAuthModal('login')">
              Sign In to Connect Gmail
            </button>
            <button class="btn btn-secondary btn-sm" style="width: 100%;" onclick="IntegrationsComponent.showGmailGuide()">
              How It Works
            </button>
          `)}
        </div>
      </div>

      <!-- Card 3: WhatsApp Business -->
      <div class="glass-panel" style="display: flex; flex-direction: column; justify-content: space-between;">
        <div>
          <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px;">
            <div style="display: flex; align-items: center; gap: 10px;">
              <div class="kpi-icon-bubble" style="background: rgba(37, 211, 102, 0.15); color: var(--accent-whatsapp); font-size: 1rem; font-weight: 700;">WA</div>
              <div>
                <h3 style="font-size: 1.1rem; font-weight: 700;">WhatsApp Business</h3>
                <div style="font-size: 0.78rem; color: var(--text-muted);">UPI Instant-Pay Dispatcher</div>
              </div>
            </div>
            <span class="status-badge status-paid">Ready</span>
          </div>
          <p style="font-size: 0.84rem; color: var(--text-secondary); line-height: 1.5; margin-bottom: 14px;">
            Sends personalized payment collection notices to debtors directly on WhatsApp with 1-click clickable UPI payment links for zero fee instant settlement.
          </p>
          <ul style="font-size: 0.8rem; color: var(--text-muted); list-style: none; padding: 0; margin-bottom: 18px; display: flex; flex-direction: column; gap: 6px;">
            <li>- Multi-tone notices (Formal, Gentle, Firm, Hinglish)</li>
            <li>- Pre-populated invoice balance & QR UPI payload</li>
            <li>- Works seamlessly on mobile & WhatsApp Web</li>
          </ul>
        </div>
        <div style="display: flex; flex-direction: column; gap: 8px;">
          <button class="btn btn-whatsapp btn-sm" style="width: 100%;" onclick="App.switchTab('comms-view')">
            Open WhatsApp Payment Dispatcher
          </button>
        </div>
      </div>

      <!-- Card 4: Tally Prime / ERP 9 -->
      <div class="glass-panel" style="display: flex; flex-direction: column; justify-content: space-between;">
        <div>
          <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px;">
            <div style="display: flex; align-items: center; gap: 10px;">
              <div class="kpi-icon-bubble" style="background: rgba(245, 158, 11, 0.15); color: var(--accent-warning); font-size: 1rem; font-weight: 700;">TP</div>
              <div>
                <h3 style="font-size: 1.1rem; font-weight: 700;">Tally Prime & ERP 9</h3>
                <div style="font-size: 0.78rem; color: var(--text-muted);">Standard Ledger & Voucher Export</div>
              </div>
            </div>
            <span class="status-badge status-paid">Ready</span>
          </div>
          <p style="font-size: 0.84rem; color: var(--text-secondary); line-height: 1.5; margin-bottom: 14px;">
            Bridge your digital back office with Indian accounting software. Exports all extracted purchase and sales vouchers directly into Tally XML format.
          </p>
          <ul style="font-size: 0.8rem; color: var(--text-muted); list-style: none; padding: 0; margin-bottom: 18px; display: flex; flex-direction: column; gap: 6px;">
            <li>- Tally XML Voucher Import structure</li>
            <li>- Day Book CSV export for audit trails</li>
            <li>- Zero manual data entry for your accountant</li>
          </ul>
        </div>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
          <a href="/api/integrations/tally/export.xml" class="btn btn-secondary btn-sm" download="tally_import.xml" style="text-align: center;">
            Tally XML
          </a>
          <a href="/api/integrations/tally/export.csv" class="btn btn-secondary btn-sm" download="tally_daybook.csv" style="text-align: center;">
            Day Book CSV
          </a>
        </div>
      </div>

      <!-- Card 5: Railway Cloud PostgreSQL -->
      <div class="glass-panel" style="display: flex; flex-direction: column; justify-content: space-between;">
        <div>
          <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px;">
            <div style="display: flex; align-items: center; gap: 10px;">
              <div class="kpi-icon-bubble" style="background: rgba(16, 185, 129, 0.15); color: var(--accent-success); font-size: 1rem; font-weight: 700;">PG</div>
              <div>
                <h3 style="font-size: 1.1rem; font-weight: 700;">Database Engine</h3>
                <div style="font-size: 0.78rem; color: var(--text-muted);">${escapeHtml(dbInfo.engine)}</div>
              </div>
            </div>
            <span class="status-badge ${dbInfo.is_postgres ? 'status-paid' : 'status-unpaid'}">
              ${dbInfo.is_postgres ? 'PostgreSQL Online' : 'SQLite Active'}
            </span>
          </div>
          <p style="font-size: 0.84rem; color: var(--text-secondary); line-height: 1.5; margin-bottom: 14px;">
            ${dbInfo.is_postgres 
              ? 'Running production PostgreSQL database hosted on Railway with pooled connection reliability and high concurrency.' 
              : 'Running high-performance SQLite engine locally. When deployed to Railway, the system automatically detects DATABASE_URL and promotes to PostgreSQL seamlessly.'}
          </p>
          <ul style="font-size: 0.8rem; color: var(--text-muted); list-style: none; padding: 0; margin-bottom: 18px; display: flex; flex-direction: column; gap: 6px;">
            <li>- Auto-detects <code>DATABASE_URL</code> in Railway</li>
            <li>- Multi-user tenancy with JWT authentication</li>
            <li>- Zero migration downtime design</li>
          </ul>
        </div>
        <div>
          <div style="background: var(--bg-surface); padding: 8px 12px; border-radius: var(--radius-sm); font-size: 0.76rem; color: var(--text-muted); font-family: monospace;">
            Engine: ${escapeHtml(dbInfo.engine)}
          </div>
        </div>
      </div>
    `;
  },

  async addAllDeadlinesToCalendar() {
    try {
      const res = await fetch("/api/integrations/calendar/events");
      const data = await res.json();
      if (!data.events || data.events.length === 0) {
        App.showToast("No upcoming calendar events found.", "info");
        return;
      }

      // Open modal with list of direct Google Calendar add links
      const modal = document.getElementById("generic-modal");
      const title = document.getElementById("modal-generic-title");
      const body = document.getElementById("modal-generic-body");

      title.innerText = "Add Events to Google Calendar";
      body.innerHTML = `
        <p style="font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 16px;">
          Click any deadline below to open directly in Google Calendar with pre-configured dates, reminders, and penalty warnings:
        </p>
        <div style="display: flex; flex-direction: column; gap: 10px; max-height: 380px; overflow-y: auto;">
          ${data.events.map(ev => `
            <div style="background: var(--bg-surface); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); padding: 12px; display: flex; justify-content: space-between; align-items: center;">
              <div>
                <div style="font-weight: 600; font-size: 0.88rem; color: var(--text-primary);">${escapeHtml(ev.title)}</div>
                <div style="font-size: 0.78rem; color: var(--accent-warning);">Due: ${escapeHtml(ev.date)}</div>
              </div>
              <a href="${ev.google_calendar_url}" target="_blank" class="btn btn-primary btn-sm" style="text-decoration: none;">
                Add to GCal
              </a>
            </div>
          `).join("")}
        </div>
        <div style="margin-top: 16px; border-top: 1px solid var(--border-subtle); padding-top: 12px; text-align: center;">
          <button class="btn btn-secondary btn-sm" onclick="IntegrationsComponent.copyIcalFeedUrl()">
            Or Subscribe via iCal Feed (Auto-Sync All)
          </button>
        </div>
      `;

      App.openModal();
    } catch (e) {
      App.showToast("Could not load calendar events.", "danger");
    }
  },

  copyIcalFeedUrl() {
    const feedUrl = `${window.location.origin}/api/integrations/calendar/feed.ics`;
    navigator.clipboard.writeText(feedUrl).then(() => {
      App.showToast("Live iCal subscription link copied to clipboard! Paste it into Google Calendar -> 'From URL'.", "success");
    }).catch(() => {
      prompt("Copy this iCal feed URL to subscribe in Google Calendar:", feedUrl);
    });
  },

  async syncGmailInbox() {
    const btn = document.getElementById("btn-sync-gmail");
    if (btn) {
      btn.disabled = true;
      btn.innerText = "Syncing Inbox...";
    }

    try {
      const headers = (typeof AuthComponent !== "undefined" && AuthComponent.getAuthHeaders)
        ? AuthComponent.getAuthHeaders()
        : { "Content-Type": "application/json" };
      const res = await fetch("/api/integrations/gmail/sync", { method: "POST", headers });
      const data = await res.json();
      if (data.status === "guest" || data.status === "not_configured") {
        App.showToast(data.message, "warning");
      } else {
        App.showToast(data.message || "Inbox synchronized successfully!", "success");
      }

      // Refresh briefing and emails
      if (window.BriefingComponent) {
        if (typeof BriefingComponent.loadBriefing === "function") {
          await BriefingComponent.loadBriefing();
        }
        if (typeof BriefingComponent.loadEmailFeed === "function") {
          await BriefingComponent.loadEmailFeed();
        }
      }
      await this.loadStatus();
      this.renderCards();
    } catch (e) {
      console.error("Gmail sync error:", e);
      App.showToast("Failed to sync Gmail inbox.", "danger");
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.innerText = "Sync Inbox Now";
      }
    }
  },

  openConnectGmailModal() {
    if (typeof AuthComponent !== "undefined" && !AuthComponent.currentUser) {
      AuthComponent.openAuthModal("login");
      return;
    }

    const modal = document.getElementById("generic-modal");
    const title = document.getElementById("modal-generic-title");
    const body = document.getElementById("modal-generic-body");

    title.innerText = "Connect Your Personal Gmail Account";
    const userEmail = (AuthComponent.currentUser && AuthComponent.currentUser.email) || "";

    body.innerHTML = `
      <div style="display: flex; flex-direction: column; gap: 14px; font-size: 0.88rem; line-height: 1.5;">
        <p style="margin: 0; color: var(--text-secondary);">
          Connect your Gmail inbox to automatically pull supplier bills, bank alerts, and statutory tax notices into your morning briefing.
        </p>

        <div style="background: rgba(59, 130, 246, 0.08); border: 1px solid rgba(59, 130, 246, 0.25); border-radius: var(--radius-sm); padding: 12px; font-size: 0.82rem;">
          <strong style="color: var(--accent-primary);">🔒 Security Requirement: Google App Password</strong>
          <p style="margin: 4px 0 0 0; color: var(--text-secondary);">
            Google does not allow third-party apps to use your regular password. You generate a dedicated 16-character <strong>App Password</strong> in 1 minute.
            <a href="https://myaccount.google.com/apppasswords" target="_blank" style="color: var(--accent-primary); text-decoration: underline; margin-left: 4px;">Generate App Password &rarr;</a>
          </p>
        </div>

        <div>
          <label style="display: block; font-size: 0.82rem; font-weight: 600; margin-bottom: 6px;">Gmail Address</label>
          <input type="email" id="input-connect-email" value="${escapeHtml(userEmail)}" placeholder="you@gmail.com"
                 style="width: 100%; padding: 9px 12px; background: var(--bg-surface); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); color: var(--text-primary); font-size: 0.88rem;">
        </div>

        <div>
          <label style="display: block; font-size: 0.82rem; font-weight: 600; margin-bottom: 6px;">16-Character Google App Password</label>
          <input type="password" id="input-connect-pwd" placeholder="abcd efgh ijkl mnop"
                 style="width: 100%; padding: 9px 12px; background: var(--bg-surface); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); color: var(--text-primary); font-size: 0.88rem; letter-spacing: 1px;">
          <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 4px;">
            Spaces don't matter. Stored securely and only accessed for your account.
          </div>
        </div>

        <div id="connect-gmail-error" style="color: var(--accent-danger); font-size: 0.82rem; display: none; background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.2); padding: 8px 12px; border-radius: 6px;"></div>

        <div style="display: flex; justify-content: flex-end; gap: 8px; margin-top: 8px;">
          <button class="btn btn-secondary btn-sm" onclick="App.closeModal()">Cancel</button>
          <button class="btn btn-primary btn-sm" id="btn-submit-connect-gmail" onclick="IntegrationsComponent.submitConnectGmail()">
            Connect & Sync Inbox
          </button>
        </div>
      </div>
    `;
    App.openModal();
  },

  async submitConnectGmail() {
    const emailInput = document.getElementById("input-connect-email");
    const pwdInput = document.getElementById("input-connect-pwd");
    const errEl = document.getElementById("connect-gmail-error");
    const btn = document.getElementById("btn-submit-connect-gmail");

    const email = emailInput ? emailInput.value.trim() : "";
    const app_password = pwdInput ? pwdInput.value.trim() : "";

    if (!email || !app_password) {
      if (errEl) {
        errEl.innerText = "Please provide both your Gmail address and 16-character App Password.";
        errEl.style.display = "block";
      }
      return;
    }

    if (btn) {
      btn.disabled = true;
      btn.innerText = "Connecting & Verifying...";
    }
    if (errEl) errEl.style.display = "none";

    try {
      const headers = (typeof AuthComponent !== "undefined" && AuthComponent.getAuthHeaders)
        ? AuthComponent.getAuthHeaders()
        : { "Content-Type": "application/json" };
      const res = await fetch("/api/integrations/gmail/connect", {
        method: "POST",
        headers,
        body: JSON.stringify({ email, app_password })
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Authentication failed. Please verify your App Password.");
      }

      App.showToast(data.message || "Gmail connected successfully!", "success");
      App.closeModal();
      await this.init();
      if (window.BriefingComponent && typeof BriefingComponent.init === "function") {
        BriefingComponent.init();
      }
    } catch (err) {
      if (errEl) {
        errEl.innerText = err.message;
        errEl.style.display = "block";
      }
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.innerText = "Connect & Sync Inbox";
      }
    }
  },

  async disconnectGmail() {
    if (!confirm("Are you sure you want to disconnect your Gmail account? Automated sync will be paused.")) {
      return;
    }
    try {
      const headers = (typeof AuthComponent !== "undefined" && AuthComponent.getAuthHeaders)
        ? AuthComponent.getAuthHeaders()
        : { "Content-Type": "application/json" };
      const res = await fetch("/api/integrations/gmail/disconnect", {
        method: "POST",
        headers
      });
      const data = await res.json();
      App.showToast(data.message || "Gmail account disconnected.", "info");
      await this.init();
      if (window.BriefingComponent && typeof BriefingComponent.init === "function") {
        BriefingComponent.init();
      }
    } catch (e) {
      App.showToast("Failed to disconnect Gmail.", "danger");
    }
  },

  async openCaEmailComposer() {
    try {
      const res = await fetch("/api/compliance/draft-email?code=GSTR_3B");
      const d = await res.json();
      const composeUrl = `https://mail.google.com/mail/?view=cm&fs=1&to=${encodeURIComponent(d.to_email || '')}&su=${encodeURIComponent(d.subject || '')}&body=${encodeURIComponent(d.body || '')}`;
      window.open(composeUrl, "_blank");
      App.showToast("Opened Gmail composer with pre-filled CA package!", "success");
    } catch (e) {
      App.showToast("Could not prepare CA email.", "danger");
    }
  },

  showCalendarGuide() {
    const modal = document.getElementById("generic-modal");
    const title = document.getElementById("modal-generic-title");
    const body = document.getElementById("modal-generic-body");
    const feedUrl = `${window.location.origin}/api/integrations/calendar/feed.ics`;

    title.innerText = "How to Connect Google Calendar";
    body.innerHTML = `
      <div style="display: flex; flex-direction: column; gap: 16px; font-size: 0.88rem; line-height: 1.6;">
        <div style="background: rgba(66, 133, 244, 0.1); border: 1px solid rgba(66, 133, 244, 0.3); border-radius: var(--radius-sm); padding: 14px;">
          <strong style="color: #4285f4; font-size: 0.95rem;">Method 1: Live Auto-Sync via iCal (Recommended)</strong>
          <p style="margin: 6px 0 10px 0; color: var(--text-secondary);">Subscribing via iCal automatically synchronizes all statutory GST & tax deadlines and invoice due dates to your phone and computer:</p>
          <ol style="margin-left: 20px; color: var(--text-primary); display: flex; flex-direction: column; gap: 6px;">
            <li>Copy your live iCal subscription URL:
              <div style="display: flex; gap: 8px; margin-top: 6px;">
                <input type="text" readonly value="${feedUrl}" style="flex: 1; font-family: monospace; font-size: 0.78rem; padding: 6px 10px; background: var(--bg-surface); border: 1px solid var(--border-subtle); border-radius: 6px; color: var(--text-primary);" />
                <button class="btn btn-primary btn-sm" onclick="IntegrationsComponent.copyIcalFeedUrl()">Copy URL</button>
              </div>
            </li>
            <li>Open <a href="https://calendar.google.com" target="_blank" style="color: var(--accent-primary);">calendar.google.com</a> in your browser.</li>
            <li>On the left sidebar, click the <strong>+</strong> icon next to <strong>Other calendars</strong> and select <strong>From URL</strong>.</li>
            <li>Paste your copied URL and click <strong>Add calendar</strong>.</li>
          </ol>
        </div>

        <div style="background: var(--bg-surface); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); padding: 14px;">
          <strong style="color: var(--text-primary); font-size: 0.95rem;">Method 2: 1-Click Direct Addition (Zero Setup)</strong>
          <p style="margin: 6px 0 8px 0; color: var(--text-secondary);">Add individual deadlines on the fly:</p>
          <ul style="margin-left: 20px; color: var(--text-primary); display: flex; flex-direction: column; gap: 4px;">
            <li>Go to <strong>Tax & Compliance</strong> tab -> Click <strong>Add to GCal</strong> on any return.</li>
            <li>Go to <strong>Invoices & Bills</strong> tab -> Click <strong>GCal</strong> on any invoice row with a due date.</li>
            <li>Click <strong>Add All Deadlines to Google Calendar</strong> on this card to pick and add events directly.</li>
          </ul>
        </div>
      </div>
    `;
    App.openModal();
  },

  showGmailGuide() {
    const modal = document.getElementById("generic-modal");
    const title = document.getElementById("modal-generic-title");
    const body = document.getElementById("modal-generic-body");

    title.innerText = "How to Generate a Google App Password";
    body.innerHTML = `
      <div style="display: flex; flex-direction: column; gap: 16px; font-size: 0.88rem; line-height: 1.6;">
        <div style="background: rgba(34, 197, 94, 0.1); border: 1px solid rgba(34, 197, 94, 0.3); border-radius: var(--radius-sm); padding: 14px;">
          <strong style="color: var(--accent-success); font-size: 0.95rem;">⚡ Why Use an App Password?</strong>
          <p style="margin: 6px 0 0 0; color: var(--text-secondary);">
            A Google App Password is a secure 16-character passcode that lets PattuBook read supplier invoices, bills, and tax notices via IMAP SSL without sharing your main Google password.
          </p>
        </div>

        <div style="background: var(--bg-surface); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); padding: 14px;">
          <strong style="color: var(--text-primary); font-size: 0.95rem;">Quick 3-Step Setup:</strong>
          <ol style="margin-left: 20px; margin-top: 8px; color: var(--text-primary); display: flex; flex-direction: column; gap: 8px;">
            <li>Make sure <strong>2-Step Verification</strong> is ON in your <a href="https://myaccount.google.com/security" target="_blank" style="color: var(--accent-primary);">Google Security Settings</a>.</li>
            <li>Go to <a href="https://myaccount.google.com/apppasswords" target="_blank" style="color: var(--accent-primary); font-weight: 600;">myaccount.google.com/apppasswords</a>.</li>
            <li>Give it an App name (e.g., <code>PattuBook</code>) and click <strong>Create</strong>.</li>
            <li>Copy the 16-character password displayed on screen (e.g. <code>abcd efgh ijkl mnop</code>).</li>
            <li>Return here and click <strong>Connect Personal Gmail</strong>, paste your code, and click <strong>Connect & Sync</strong>!</li>
          </ol>
        </div>

        <div style="text-align: right;">
          <button class="btn btn-primary btn-sm" onclick="IntegrationsComponent.openConnectGmailModal()">
            Connect Now
          </button>
        </div>
      </div>
    `;
    App.openModal();
  }
};
