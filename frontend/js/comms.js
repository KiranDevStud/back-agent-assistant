// PattuBook - Smart Payment Reminders & WhatsApp/Email Communications
const CommsComponent = {
  currentReminder: null,

  async init() {
    this.populateOutstandingDebtors();
  },

  async populateOutstandingDebtors() {
    try {
      const res = await fetch("/api/mis/report");
      const data = await res.json();
      const debtors = data.top_debtors || [];

      const selectEl = document.getElementById("comm-customer-select");
      if (selectEl) {
        selectEl.innerHTML = `<option value="">-- Choose from Outstanding Debtors --</option>` +
          debtors.map(d => `<option value="${escapeHtml(d.party_name)}" data-amount="${d.amount}">${escapeHtml(d.party_name)} (₹${Number(d.amount).toLocaleString('en-IN')})</option>`).join("");
          
        selectEl.addEventListener("change", (e) => {
          const selected = selectEl.options[selectEl.selectedIndex];
          if (selected && selected.value) {
            document.getElementById("comm-customer-name").value = selected.value;
            document.getElementById("comm-amount").value = selected.dataset.amount || "";
            document.getElementById("comm-inv-no").value = "INV-" + Math.floor(1000 + Math.random() * 9000);
            this.generateReminderPreview();
          }
        });
      }

      // If no customer has been manually entered, prefill the first real debtor if any exist
      const currentName = document.getElementById("comm-customer-name").value.trim();
      if (!currentName) {
        if (debtors.length > 0) {
          this.prefillForCustomer(debtors[0].party_name, debtors[0].amount);
        } else {
          this.clearForm();
          this.renderEmptyState();
        }
      }
    } catch (e) {
      console.error(e);
      this.renderEmptyState();
    }
  },

  clearForm() {
    const nameEl = document.getElementById("comm-customer-name");
    const amtEl = document.getElementById("comm-amount");
    const invEl = document.getElementById("comm-inv-no");
    const dateEl = document.getElementById("comm-due-date");
    const phoneEl = document.getElementById("comm-phone");

    if (nameEl) nameEl.value = "";
    if (amtEl) amtEl.value = "";
    if (invEl) invEl.value = "";
    if (dateEl) dateEl.value = "";
    if (phoneEl) phoneEl.value = "";
  },

  prefillForCustomer(partyName, amount) {
    document.getElementById("comm-customer-name").value = partyName || "";
    document.getElementById("comm-amount").value = amount || "";
    document.getElementById("comm-inv-no").value = "";
    document.getElementById("comm-due-date").value = "Immediate";
    document.getElementById("comm-phone").value = "";
    this.generateReminderPreview();
  },

  renderEmptyState(customMsg = "") {
    const previewBox = document.getElementById("comm-preview-box");
    if (!previewBox) return;

    previewBox.innerHTML = `
      <div style="background: var(--bg-surface); border-radius: var(--radius-md); padding: 50px 24px; border: 1px dashed var(--border-subtle); text-align: center; color: var(--text-muted);">
        <div style="font-size: 1.05rem; font-weight: 600; color: var(--text-primary); margin-bottom: 8px;">No Debtor Selected</div>
        <p style="font-size: 0.85rem; max-width: 440px; margin: 0 auto; color: var(--text-secondary); line-height: 1.6;">
          ${escapeHtml(customMsg || "Choose a customer from your recorded outstanding debtors or enter party details on the left to generate an instant payment reminder notice with your UPI quick-pay link.")}
        </p>
      </div>
    `;
  },

  async generateReminderPreview() {
    const customer_name = document.getElementById("comm-customer-name").value.trim();
    const invoice_number = document.getElementById("comm-inv-no").value.trim() || "Pending Bill";
    const amount = parseFloat(document.getElementById("comm-amount").value) || 0;
    const due_date = document.getElementById("comm-due-date").value.trim() || "Immediate";
    const phone = document.getElementById("comm-phone").value.trim();
    const tone = document.getElementById("comm-tone-select").value;

    if (!customer_name || amount <= 0) {
      this.renderEmptyState("Please enter a customer name and pending amount to generate a payment reminder preview.");
      return;
    }

    try {
      const res = await fetch("/api/comms/generate-reminder", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ customer_name, invoice_number, amount, due_date, phone, tone })
      });
      this.currentReminder = await res.json();
      this.renderPreview(this.currentReminder);
    } catch (e) {
      console.error("Error generating reminder:", e);
    }
  },

  renderPreview(rem) {
    const previewBox = document.getElementById("comm-preview-box");
    if (!previewBox) return;

    previewBox.innerHTML = `
      <div style="background: var(--bg-surface); border-radius: var(--radius-md); padding: 18px; border: 1px solid var(--border-subtle); display: flex; flex-direction: column; gap: 14px;">
        <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border-subtle); padding-bottom: 10px;">
          <div>
            <span style="font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase;">Message Subject</span>
            <div style="font-weight: 600; font-size: 0.95rem; color: var(--text-primary);">${escapeHtml(rem.subject)}</div>
          </div>
          <span class="badge badge-primary">${rem.tone.toUpperCase()} TONE</span>
        </div>

        <div>
          <span style="font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase;">Message Preview</span>
          <div style="background: var(--bg-card); padding: 16px; border-radius: 8px; font-size: 0.92rem; line-height: 1.6; white-space: pre-wrap; font-family: var(--font-sans); border: 1px solid var(--border-subtle); margin-top: 4px;">${escapeHtml(rem.message)}</div>
        </div>

        <div style="background: rgba(37, 211, 102, 0.08); border: 1px solid rgba(37, 211, 102, 0.25); border-radius: 8px; padding: 12px; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 10px;">
          <div>
            <div style="font-weight: 600; font-size: 0.85rem; color: var(--accent-whatsapp);">Dynamic UPI Quick-Pay Link Attached</div>
            <div style="font-size: 0.78rem; color: var(--text-muted); font-family: monospace;">${escapeHtml(rem.upi_link)}</div>
          </div>
          <span class="badge badge-success">0% Gateway Fee</span>
        </div>

        <div style="display: flex; gap: 12px; flex-wrap: wrap; justify-content: flex-end; margin-top: 6px;">
          <button class="btn btn-secondary" onclick="CommsComponent.copyText()">
            Copy Text
          </button>
          <a class="btn btn-secondary" href="${rem.mailto_url}" target="_blank">
            Open Email
          </a>
          <a class="btn btn-whatsapp" href="${rem.whatsapp_url}" target="_blank">
            Send via WhatsApp Web
          </a>
        </div>
      </div>
    `;
  },

  copyText() {
    if (!this.currentReminder) return;
    navigator.clipboard.writeText(this.currentReminder.message)
      .then(() => App.showToast("Reminder message copied to clipboard!", "success"))
      .catch(() => App.showToast("Failed to copy", "danger"));
  }
};
