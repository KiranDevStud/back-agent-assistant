// PattuBook - Morning Briefing & Communication Stream Component
const BriefingComponent = {
  async init() {
    await this.loadBriefing();
    await this.loadEmailFeed();
    await this.checkImapStatus();
  },

  async loadEmails() {
    await this.loadEmailFeed();
  },

  async syncImapNow() {
    const btn = document.getElementById("btn-briefing-sync");
    if (btn) {
      btn.disabled = true;
      btn.innerText = "Syncing Inbox...";
    }
    try {
      const headers = typeof AuthComponent !== "undefined" ? AuthComponent.getAuthHeaders() : {};
      const res = await fetch("/api/integrations/gmail/sync", { method: "POST", headers });
      const data = await res.json();
      if (data.status === "auth_error") {
        App.showToast(data.message, "danger");
      } else if (data.status === "preview_mode" || data.status === "not_configured" || data.status === "guest") {
        App.showToast(data.message, "warning");
      } else {
        App.showToast(data.message || "Inbox synchronized successfully!", "success");
      }
      await this.loadBriefing();
      await this.loadEmailFeed();
      await this.checkImapStatus();
    } catch (e) {
      console.error("IMAP manual sync error:", e);
      App.showToast("Could not sync inbox. Please check network/server.", "danger");
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.innerText = "Sync Inbox Now";
      }
    }
  },

  async checkImapStatus() {
    try {
      const headers = typeof AuthComponent !== "undefined" ? AuthComponent.getAuthHeaders() : {};
      const res = await fetch("/api/integrations/imap/status", { headers });
      if (res.ok) {
        const status = await res.json();
        const pill = document.getElementById("imap-sync-pill");
        if (pill) {
          if (status.enabled) {
            pill.className = "status-badge status-paid";
            pill.innerText = `Auto-Sync (Active)`;
            pill.title = `Connected to ${status.user || status.host}. Automated background sync active.`;
          } else {
            pill.className = "status-badge status-pending";
            pill.innerText = `IMAP Standby`;
            pill.title = `Connect your Gmail in Integrations to sync inbox automatically.`;
          }
        }
      }
    } catch (e) {
      // Silent fail
    }
  },

  async loadBriefing() {
    try {
      const headers = typeof AuthComponent !== "undefined" ? AuthComponent.getAuthHeaders() : {};
      const res = await fetch("/api/emails/briefing", { headers });
      const data = await res.json();

      const heroEl = document.getElementById("briefing-hero-content");
      if (!heroEl) return;

      let actionsHtml = "";
      if (data.urgent_actions && data.urgent_actions.length > 0) {
        actionsHtml = data.urgent_actions.map(a => {
          const cat = (a.category || "").toLowerCase();
          const subj = (a.subject || "").toLowerCase();
          let btnLabel = "View Details";

          if (cat.includes("gst") || cat.includes("statutory") || cat.includes("tax")) {
            btnLabel = "Open Compliance";
          } else if (cat.includes("invoice") || cat.includes("bill") || cat.includes("payment demand") || cat.includes("dispatch")) {
            btnLabel = "View Bill / Pay";
          } else if (cat.includes("bank")) {
            btnLabel = "View Cash Flow";
          } else if (cat.includes("security") || subj.includes("security")) {
            btnLabel = "Review Security";
          }

          const safeSubj = (a.subject || "").replace(/'/g, "\\'");
          const safeCat = (a.category || "").replace(/'/g, "\\'");

          return `
            <div class="briefing-action-item ${a.category === 'Payment Demand' ? 'danger' : ''}">
              <div>
                <div style="font-weight: 600; font-size: 0.95rem;">${escapeHtml(a.subject)}</div>
                <div style="font-size: 0.82rem; color: var(--text-muted); margin-top: 2px;">
                  From: <strong>${escapeHtml(a.sender)}</strong> • Action: <span style="color: var(--accent-warning);">${escapeHtml(a.action)}</span>
                </div>
              </div>
              <button class="btn btn-secondary btn-sm" onclick="BriefingComponent.handleActionItem(${a.id || 0}, '${safeCat}', '${safeSubj}')">
                ${btnLabel}
              </button>
            </div>
          `;
        }).join("");
      } else {
        actionsHtml = `<div style="color: var(--text-muted); font-size: 0.88rem;">No urgent action items flagged for today. All operations on track.</div>`;
      }

      heroEl.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 10px;">
          <div>
            <h3>${escapeHtml(data.headline)}</h3>
            <p style="color: var(--text-secondary); font-size: 0.9rem;">
              You have <strong>${data.total_emails}</strong> communications tracked today, with 
              <span class="badge badge-danger">${data.high_priority_count} High Priority</span> items requiring attention.
            </p>
          </div>
          <button class="btn btn-primary btn-sm" onclick="BriefingComponent.openAddEmailModal()">
            Ingest Email/Message
          </button>
        </div>
        <div class="briefing-action-list">
          ${actionsHtml}
        </div>
      `;

      // Update KPI banner if present
      const actionBadge = document.getElementById("kpi-unread-actions");
      if (actionBadge) {
        actionBadge.innerText = `${data.high_priority_count} Urgent`;
      }
    } catch (e) {
      console.error("Error loading briefing:", e);
    }
  },

  async loadEmailFeed() {
    try {
      const headers = typeof AuthComponent !== "undefined" ? AuthComponent.getAuthHeaders() : {};
      const res = await fetch("/api/emails", { headers });
      const emails = await res.json();
      const tbody = document.getElementById("emails-table-body");
      if (!tbody) return;

      if (!Array.isArray(emails) || emails.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 30px;">No email records found.</td></tr>`;
        return;
      }

      // Ensure newest emails are at the top (descending by date and id)
      emails.sort((a, b) => {
        const dateA = a.date || "";
        const dateB = b.date || "";
        if (dateA !== dateB) {
          return dateB.localeCompare(dateA);
        }
        return (b.id || 0) - (a.id || 0);
      });

      tbody.innerHTML = emails.map(e => {
        let badgeClass = "badge-info";
        if (e.category === "Bank Alert") badgeClass = "badge-success";
        else if (e.category === "Payment Demand") badgeClass = "badge-danger";
        else if (e.category === "Statutory / GST") badgeClass = "badge-warning";
        else if (e.category === "Customer Inquiry") badgeClass = "badge-primary";

        return `
          <tr>
            <td style="font-weight: 500;">
              <div>${escapeHtml(e.sender)}</div>
              <div style="font-size: 0.75rem; color: var(--text-muted);">${escapeHtml(e.date || '')}</div>
            </td>
            <td>
              <span class="badge ${badgeClass}">${escapeHtml(e.category)}</span>
            </td>
            <td>
              <div style="font-weight: 600; color: var(--text-primary);">${escapeHtml(e.subject)}</div>
              <div style="font-size: 0.82rem; color: var(--text-secondary);">${escapeHtml(e.summary)}</div>
            </td>
            <td>
              <span style="font-size: 0.82rem; color: var(--accent-warning); font-weight: 500;">
                ${escapeHtml(e.action_required || 'Review')}
              </span>
            </td>
            <td>
              <button class="btn btn-secondary btn-sm" onclick="BriefingComponent.viewEmailDetail(${e.id})">
                View
              </button>
            </td>
          </tr>
        `;
      }).join("");
    } catch (e) {
      console.error("Error loading email feed:", e);
    }
  },

  handleActionItem(id, category, subject) {
    const cat = (category || "").toLowerCase();
    const subj = (subject || "").toLowerCase();

    if (cat.includes("gst") || cat.includes("statutory") || cat.includes("tax")) {
      App.switchTab("compliance-view");
    } else if (cat.includes("invoice") || cat.includes("bill") || cat.includes("payment demand") || cat.includes("dispatch")) {
      App.switchTab("invoices-view");
    } else if (cat.includes("bank")) {
      App.switchTab("mis-view");
    } else if (id && id > 0) {
      this.viewEmailDetail(id);
    } else {
      this.viewEmailDetail(subject);
    }
  },

  async viewEmailDetail(idOrSubject) {
    try {
      const res = await fetch("/api/emails");
      const emails = await res.json();
      const email = emails.find(e => 
        e.id === Number(idOrSubject) || 
        (typeof idOrSubject === "string" && e.subject.toLowerCase() === idOrSubject.toLowerCase()) ||
        (typeof idOrSubject === "string" && e.subject.toLowerCase().includes(idOrSubject.toLowerCase()))
      );
      if (!email) {
        App.showToast("Email record not found.", "info");
        return;
      }

      let extraActionBtn = "";
      const cat = (email.category || "").toLowerCase();
      const subj = (email.subject || "").toLowerCase();

      if (cat.includes("security") || subj.includes("security")) {
        extraActionBtn = `<a href="https://myaccount.google.com/security" target="_blank" class="btn btn-primary btn-sm" style="text-decoration: none;">Open Google Security</a>`;
      } else if (cat.includes("gst") || cat.includes("statutory") || cat.includes("tax")) {
        extraActionBtn = `<button class="btn btn-primary btn-sm" onclick="App.switchTab('compliance-view'); App.closeModal();">Go to Tax & Compliance</button>`;
      } else if (cat.includes("invoice") || cat.includes("bill") || cat.includes("dispatch")) {
        extraActionBtn = `<button class="btn btn-primary btn-sm" onclick="App.switchTab('invoices-view'); App.closeModal();">Go to Invoices & Bills</button>`;
      } else if (cat.includes("payment demand")) {
        extraActionBtn = `<button class="btn btn-primary btn-sm" onclick="App.switchTab('comms-view'); App.closeModal();">Draft Payment Reminder</button>`;
      } else if (cat.includes("bank")) {
        extraActionBtn = `<button class="btn btn-primary btn-sm" onclick="App.switchTab('mis-view'); App.closeModal();">View Cash Flow & MIS</button>`;
      }

      document.getElementById("modal-generic-title").innerText = `Communication: ${email.subject}`;
      document.getElementById("modal-generic-body").innerHTML = `
        <div style="display: flex; flex-direction: column; gap: 12px;">
          <div style="display: flex; justify-content: space-between; border-bottom: 1px solid var(--border-subtle); padding-bottom: 8px; flex-wrap: wrap; gap: 6px;">
            <div><strong>From:</strong> ${escapeHtml(email.sender)} &lt;${escapeHtml(email.sender_email || 'N/A')}&gt;</div>
            <div style="font-size: 0.82rem; color: var(--text-muted);">${escapeHtml(email.date)}</div>
          </div>
          <div>
            <strong>Category:</strong> <span class="badge badge-primary">${escapeHtml(email.category)}</span>
            <span style="margin-left: 10px;"><strong>Priority:</strong> <span class="badge ${email.priority === 'high' ? 'badge-danger' : 'badge-info'}">${escapeHtml((email.priority || 'medium').toUpperCase())}</span></span>
          </div>
          <div>
            <strong>Action Required:</strong>
            <div style="background: rgba(245, 158, 11, 0.1); border-left: 3px solid var(--accent-warning); padding: 8px 12px; margin-top: 4px; border-radius: 4px;">
              ${escapeHtml(email.action_required || 'Review')}
            </div>
          </div>
          <div>
            <strong>Full Message Content:</strong>
            <div style="background: var(--bg-surface); padding: 14px; border-radius: 8px; font-size: 0.9rem; line-height: 1.6; margin-top: 6px; white-space: pre-wrap; max-height: 320px; overflow-y: auto;">${escapeHtml(email.raw_body || '(No body text)')}</div>
          </div>
          <div style="display: flex; justify-content: flex-end; gap: 8px; margin-top: 10px; border-top: 1px solid var(--border-subtle); padding-top: 10px;">
            ${extraActionBtn}
            <button class="btn btn-secondary btn-sm" onclick="App.closeModal()">Close</button>
          </div>
        </div>
      `;
      App.openModal();
    } catch (err) {
      console.error(err);
    }
  },

  openAddEmailModal() {
    document.getElementById("modal-generic-title").innerText = "Ingest New Email or WhatsApp Message";
    document.getElementById("modal-generic-body").innerHTML = `
      <form id="add-email-form" onsubmit="BriefingComponent.submitNewEmail(event)">
        <div class="form-group">
          <label class="form-label">Sender Name / Entity</label>
          <input type="text" id="new-email-sender" class="form-input" placeholder="e.g. HDFC Bank, Havells Distributor, Client Name" required />
        </div>
        <div class="form-group">
          <label class="form-label">Sender Email / Mobile</label>
          <input type="text" id="new-email-addr" class="form-input" placeholder="e.g. billing@supplier.com or +91 98200..." />
        </div>
        <div class="form-group">
          <label class="form-label">Subject / Header</label>
          <input type="text" id="new-email-subject" class="form-input" placeholder="e.g. Urgent Payment Due for Bill 402" required />
        </div>
        <div class="form-group">
          <label class="form-label">Message Content</label>
          <textarea id="new-email-body" class="form-textarea" rows="4" placeholder="Paste the email or WhatsApp text here..." required></textarea>
        </div>
        <div style="display: flex; justify-content: flex-end; gap: 10px; margin-top: 15px;">
          <button type="button" class="btn btn-secondary" onclick="App.closeModal()">Cancel</button>
          <button type="submit" class="btn btn-primary">Process with AI</button>
        </div>
      </form>
    `;
    App.openModal();
  },

  async submitNewEmail(e) {
    e.preventDefault();
    const sender = document.getElementById("new-email-sender").value;
    const sender_email = document.getElementById("new-email-addr").value;
    const subject = document.getElementById("new-email-subject").value;
    const body = document.getElementById("new-email-body").value;

    try {
      const res = await fetch("/api/emails/add", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sender, sender_email, subject, body })
      });
      if (res.ok) {
        App.showToast("Email ingested and classified successfully!", "success");
        App.closeModal();
        await this.loadBriefing();
        await this.loadEmailFeed();
      }
    } catch (err) {
      App.showToast("Failed to process email: " + err.message, "danger");
    }
  }
};
