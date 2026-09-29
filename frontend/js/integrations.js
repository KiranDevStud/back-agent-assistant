// PattuBook - Cross-Platform Integrations Hub Controller

const IntegrationsComponent = {
  statusData: null,

  async init() {
    await this.loadStatus();
    this.renderCards();
  },

  async loadStatus() {
    try {
      const res = await fetch("/api/integrations/status");
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
                <h3 style="font-size: 1.1rem; font-weight: 700;">Gmail / Yahoo (IMAP)</h3>
                <div style="font-size: 0.78rem; color: var(--text-muted);">5-Minute Auto-Sync & AI Ingestion</div>
              </div>
            </div>
            <span class="status-badge ${data.gmail && data.gmail.imap_configured ? 'status-paid' : 'status-pending'}">
              ${data.gmail && data.gmail.imap_configured ? 'Auto-Sync (5m Active)' : 'IMAP Standby'}
            </span>
          </div>
          <p style="font-size: 0.84rem; color: var(--text-secondary); line-height: 1.5; margin-bottom: 14px;">
            Automatically polls inbox every 5 minutes in background for supplier bills, bank NEFT/UPI alerts, and tax notices with AI summary and auto-OCR.
          </p>
          <ul style="font-size: 0.8rem; color: var(--text-muted); list-style: none; padding: 0; margin-bottom: 18px; display: flex; flex-direction: column; gap: 6px;">
            <li>- <strong>Timer:</strong> Runs automatically every 5 minutes</li>
            <li>- <strong>Host:</strong> ${escapeHtml((data.gmail && data.gmail.imap_host) || 'imap.gmail.com')} (SSL :993)</li>
            <li>- <strong>Account:</strong> ${escapeHtml((data.gmail && data.gmail.imap_user) || 'Add App Password in .env')}</li>
          </ul>
        </div>
        <div style="display: flex; flex-direction: column; gap: 8px;">
          <button class="btn btn-primary btn-sm" style="width: 100%;" id="btn-sync-gmail" onclick="IntegrationsComponent.syncGmailInbox()">
            Sync Inbox Now
          </button>
          <button class="btn btn-secondary btn-sm" style="width: 100%;" onclick="IntegrationsComponent.openCaEmailComposer()">
            Draft CA Filing Package via Gmail
          </button>
          <button class="btn btn-secondary btn-sm" style="width: 100%;" onclick="IntegrationsComponent.showGmailGuide()">
            How to Connect Gmail / Yahoo
          </button>
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
      const res = await fetch("/api/integrations/gmail/sync", { method: "POST" });
      const data = await res.json();
      App.showToast(data.message || "Inbox synchronized successfully!", "success");

      // Refresh briefing and emails
      if (window.BriefingComponent) {
        if (typeof BriefingComponent.loadBriefing === "function") {
          await BriefingComponent.loadBriefing();
        }
        if (typeof BriefingComponent.loadEmailFeed === "function") {
          await BriefingComponent.loadEmailFeed();
        }
      }
    } catch (e) {
      console.error("Gmail sync error:", e);
      App.showToast("Failed to sync Gmail inbox.", "danger");
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.innerText = "Sync Inbox for New Bills & Notices";
      }
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

    title.innerText = "How to Connect Gmail / Yahoo (IMAP Auto-Sync)";
    body.innerHTML = `
      <div style="display: flex; flex-direction: column; gap: 16px; font-size: 0.88rem; line-height: 1.6;">
        <div style="background: rgba(34, 197, 94, 0.1); border: 1px solid rgba(34, 197, 94, 0.3); border-radius: var(--radius-sm); padding: 14px;">
          <strong style="color: var(--accent-success); font-size: 0.95rem;">⚡ Automated 5-Minute Background Ingestion Active</strong>
          <p style="margin: 6px 0 0 0; color: var(--text-secondary);">
            The system runs a background worker daemon that checks your inbox every <strong>5 minutes</strong>. It automatically categorizes bank credits, supplier invoices, and tax advisories into the Daily Briefing, and auto-processes PDF invoice attachments!
          </p>
        </div>

        <div style="background: var(--bg-surface); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); padding: 14px;">
          <strong style="color: var(--text-primary); font-size: 0.95rem;">Step-by-Step: Adding your Google App Password</strong>
          <ol style="margin-left: 20px; margin-top: 8px; color: var(--text-primary); display: flex; flex-direction: column; gap: 6px;">
            <li>Go to <a href="https://myaccount.google.com/security" target="_blank" style="color: var(--accent-primary);">Google Account Security</a> and ensure <strong>2-Step Verification</strong> is enabled.</li>
            <li>Go to <a href="https://myaccount.google.com/apppasswords" target="_blank" style="color: var(--accent-primary);">myaccount.google.com/apppasswords</a>.</li>
            <li>Create an app password named <em>PattuBook</em> (Google generates a 16-character code like <code>abcd efgh ijkl mnop</code>).</li>
            <li>Open your <code>.env</code> file in the project folder and paste:
              <pre style="background: var(--bg-primary); padding: 10px; border-radius: 6px; font-family: monospace; font-size: 0.78rem; margin-top: 6px; overflow-x: auto;">
IMAP_HOST=imap.gmail.com
IMAP_PORT=993
IMAP_USER=your_email@gmail.com
IMAP_PASSWORD=your_16_char_google_app_password
IMAP_SYNC_INTERVAL_MINUTES=5</pre>
            </li>
            <li>Save the file. The system automatically detects your credentials and starts polling your inbox every 5 minutes!</li>
          </ol>
        </div>

        <div style="background: rgba(234, 67, 53, 0.08); border: 1px solid rgba(234, 67, 53, 0.25); border-radius: var(--radius-sm); padding: 12px;">
          <strong style="color: #ea4335; font-size: 0.88rem;">Yahoo Mail / Outlook / Zoho:</strong>
          <p style="margin: 4px 0 0 0; color: var(--text-secondary); font-size: 0.82rem;">
            For Yahoo: Use <code>IMAP_HOST=imap.mail.yahoo.com</code> with a Yahoo App Password.<br>
            For Outlook: Use <code>IMAP_HOST=outlook.office365.com</code>.
          </p>
        </div>
      </div>
    `;
    App.openModal();
  }
};
