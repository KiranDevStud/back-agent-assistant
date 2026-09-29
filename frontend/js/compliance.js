// PattuBook - Indian Compliance & Tax Calendar Guardian
const ComplianceComponent = {
  async init() {
    await this.loadComplianceList();
  },

  async loadComplianceList() {
    try {
      const res = await fetch("/api/compliance/list");
      const records = await res.json();
      const grid = document.getElementById("compliance-cards-grid");
      if (!grid) return;

      grid.innerHTML = records.map(r => {
        let badgeStyle = "badge-success";
        let cardBorder = "var(--border-subtle)";
        if (r.urgency === "CRITICAL" || r.urgency === "OVERDUE") {
          badgeStyle = "badge-danger";
          cardBorder = "rgba(244, 63, 94, 0.4)";
        } else if (r.urgency === "UPCOMING") {
          badgeStyle = "badge-warning";
          cardBorder = "rgba(245, 158, 11, 0.4)";
        }

        return `
          <div class="kpi-card" style="border-color: ${cardBorder}; display: flex; flex-direction: column; justify-content: space-between;">
            <div>
              <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px;">
                <span class="badge ${badgeStyle}">${r.days_left <= 0 ? 'DUE TODAY / OVERDUE' : `${r.days_left} Days Left`}</span>
                <span style="font-size: 0.75rem; color: var(--text-muted); font-weight: 600;">${escapeHtml(r.frequency)}</span>
              </div>
              <h3 style="font-size: 1.05rem; font-weight: 700; margin-bottom: 6px;">${escapeHtml(r.title)}</h3>
              <p style="font-size: 0.82rem; color: var(--text-secondary); margin-bottom: 12px; line-height: 1.5;">${escapeHtml(r.description)}</p>
              
              <div style="background: var(--bg-surface); padding: 8px 12px; border-radius: 6px; font-size: 0.78rem; color: var(--accent-warning); margin-bottom: 14px;">
                Penalty: ${escapeHtml(r.penalty_info)}
              </div>
            </div>

            <div style="border-top: 1px solid var(--border-subtle); padding-top: 12px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
              <div>
                <span style="font-size: 0.7rem; color: var(--text-muted); text-transform: uppercase;">Next Due Date</span>
                <div style="font-weight: 700; font-size: 0.95rem; color: var(--text-primary);">${escapeHtml(r.next_due_date)}</div>
              </div>
              <div style="display: flex; gap: 6px;">
                <button class="btn btn-secondary btn-sm" onclick="ComplianceComponent.addToGoogleCalendar('${escapeJsString(r.title)}', '${escapeJsString(r.next_due_date)}', '${escapeJsString(r.penalty_info)}')">
                  Add to GCal
                </button>
                <button class="btn btn-primary btn-sm" onclick="ComplianceComponent.openDraftEmailModal('${escapeJsString(r.code)}')">
                  Draft CA Email
                </button>
              </div>
            </div>
          </div>
        `;
      }).join("");

      // Update Top Nav / KPI GST tracker
      const gstr3b = records.find(r => r.code === "GSTR_3B");
      if (gstr3b) {
        const kpiEl = document.getElementById("kpi-gst-countdown");
        if (kpiEl) {
          kpiEl.innerText = `${gstr3b.days_left} Days Left`;
        }
      }
    } catch (e) {
      console.error("Error loading compliance:", e);
    }
  },

  async openDraftEmailModal(code) {
    App.showToast("Synthesizing compliance filing draft for CA...", "info");
    try {
      const res = await fetch(`/api/compliance/draft-email?code=${encodeURIComponent(code)}`);
      const draft = await res.json();

      document.getElementById("modal-generic-title").innerText = `Draft Email for Chartered Accountant (CA)`;
      document.getElementById("modal-generic-body").innerHTML = `
        <div style="display: flex; flex-direction: column; gap: 14px;">
          <div class="form-group">
            <label class="form-label">Recipient CA Email</label>
            <input type="text" id="ca-email-to" class="form-input" value="${escapeHtml(draft.recipient)}" />
          </div>
          <div class="form-group">
            <label class="form-label">Subject</label>
            <input type="text" id="ca-email-subj" class="form-input" value="${escapeHtml(draft.subject)}" />
          </div>
          <div class="form-group">
            <label class="form-label">Body (Auto-Computed from Invoices & Sales Ledger)</label>
            <textarea id="ca-email-body" class="form-textarea" rows="10" style="font-family: var(--font-sans); font-size: 0.88rem; line-height: 1.6;">${escapeHtml(draft.body)}</textarea>
          </div>
          <div style="display: flex; justify-content: flex-end; gap: 10px;">
            <button class="btn btn-secondary" onclick="ComplianceComponent.copyCADraft()">
              Copy to Clipboard
            </button>
            <button class="btn btn-secondary" onclick="ComplianceComponent.sendViaGmail()">
              Open in Gmail
            </button>
            <button class="btn btn-primary" onclick="ComplianceComponent.sendViaMailto()">
              Open in Default Mail Client
            </button>
          </div>
        </div>
      `;
      App.openModal();
    } catch (e) {
      App.showToast("Failed to draft CA email: " + e.message, "danger");
    }
  },

  addToGoogleCalendar(title, dateStr, penalty) {
    const cleanDate = (dateStr || "").replace(/-/g, "");
    const url = `https://calendar.google.com/calendar/render?action=TEMPLATE&text=${encodeURIComponent('[Tax Deadline] ' + title)}&dates=${cleanDate}/${cleanDate}&details=${encodeURIComponent('Indian Statutory Return Deadline: ' + title + '\nPenalty Info: ' + penalty + '\nGenerated by PattuBook Back Office Assistant')}&location=Online+GST+Portal`;
    window.open(url, "_blank");
  },

  sendViaGmail() {
    const to = document.getElementById("ca-email-to").value;
    const subj = encodeURIComponent(document.getElementById("ca-email-subj").value);
    const body = encodeURIComponent(document.getElementById("ca-email-body").value);
    window.open(`https://mail.google.com/mail/?view=cm&fs=1&to=${to}&su=${subj}&body=${body}`, "_blank");
  },

  copyCADraft() {
    const text = document.getElementById("ca-email-body").value;
    navigator.clipboard.writeText(text)
      .then(() => App.showToast("Filing draft copied for your CA!", "success"))
      .catch(() => App.showToast("Failed to copy", "danger"));
  },

  sendViaMailto() {
    const to = document.getElementById("ca-email-to").value;
    const subj = encodeURIComponent(document.getElementById("ca-email-subj").value);
    const body = encodeURIComponent(document.getElementById("ca-email-body").value);
    window.open(`mailto:${to}?subject=${subj}&body=${body}`, "_blank");
  }
};
