// PattuBook - Invoice Extraction & Processing Component
const InvoicesComponent = {
  invoices: [],

  async init() {
    this.setupDropzone();
    await this.loadInvoices();
  },

  setupDropzone() {
    const dropzone = document.getElementById("invoice-dropzone");
    const fileInput = document.getElementById("invoice-file-input");

    if (!dropzone || !fileInput) return;

    dropzone.addEventListener("click", () => fileInput.click());

    dropzone.addEventListener("dragover", (e) => {
      e.preventDefault();
      dropzone.classList.add("drag-over");
    });

    dropzone.addEventListener("dragleave", () => {
      dropzone.classList.remove("drag-over");
    });

    dropzone.addEventListener("drop", (e) => {
      e.preventDefault();
      dropzone.classList.remove("drag-over");
      if (e.dataTransfer.files.length > 0) {
        this.handleUpload(e.dataTransfer.files[0]);
      }
    });

    fileInput.addEventListener("change", (e) => {
      if (e.target.files.length > 0) {
        this.handleUpload(e.target.files[0]);
      }
    });
  },

  async handleUpload(file) {
    if (!file) return;
    App.showToast(`Analyzing ${file.name} with AI...`, "info");

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch("/api/invoices/upload", {
        method: "POST",
        body: formData
      });
      const result = await res.json();
      if (res.ok) {
        App.showToast("Invoice extracted & saved to database!", "success");
        this.showInvoiceExtractionModal(result.data);
        await this.loadInvoices();
        App.refreshGlobalKPIs();
      } else {
        App.showToast("Extraction error: " + result.detail, "danger");
      }
    } catch (e) {
      App.showToast("Upload failed: " + e.message, "danger");
    }
  },

  async processSample(filename) {
    App.showToast(`Processing sample: ${filename}...`, "info");
    const formData = new FormData();
    formData.append("filename", filename);

    try {
      const res = await fetch("/api/invoices/process-sample", {
        method: "POST",
        body: formData
      });
      const result = await res.json();
      if (res.ok) {
        App.showToast("Sample invoice extracted successfully!", "success");
        this.showInvoiceExtractionModal(result.data);
        await this.loadInvoices();
        App.refreshGlobalKPIs();
      } else {
        App.showToast("Failed to process sample: " + result.detail, "danger");
      }
    } catch (e) {
      App.showToast("Error processing sample: " + e.message, "danger");
    }
  },

  async loadInvoices() {
    try {
      const res = await fetch("/api/invoices");
      this.invoices = await res.json();
      const tbody = document.getElementById("invoices-table-body");
      if (!tbody) return;

      if (this.invoices.length === 0) {
        tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--text-muted); padding: 30px;">No invoices scanned yet. Drag and drop a PDF tax invoice above to extract data with Local AI.</td></tr>`;
        return;
      }

      tbody.innerHTML = this.invoices.map(inv => {
        const isPaid = inv.status.toLowerCase() === "paid";
        const badgeClass = isPaid ? "badge-success" : "badge-danger";
        
        return `
          <tr>
            <td>
              <div style="font-weight: 600; color: var(--text-primary);">${escapeHtml(inv.invoice_number || 'N/A')}</div>
              <div style="font-size: 0.76rem; color: var(--text-muted);">${escapeHtml(inv.file_name || '')}</div>
            </td>
            <td>
              <div style="font-weight: 500;">${escapeHtml(inv.vendor_name || 'Vendor')}</div>
              <div style="font-size: 0.74rem; font-family: monospace; color: var(--accent-primary);">${escapeHtml(inv.vendor_gstin || 'No GSTIN')}</div>
            </td>
            <td style="font-size: 0.85rem;">
              <div>${escapeHtml(inv.invoice_date || '-')}</div>
              <div style="font-size: 0.75rem; color: var(--accent-warning);">Due: ${escapeHtml(inv.due_date || '-')}</div>
            </td>
            <td style="font-weight: 600;">
              ₹${Number(inv.subtotal || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
            </td>
            <td style="font-size: 0.82rem; color: var(--text-secondary);">
              <div>CGST: ₹${Number(inv.cgst || 0).toFixed(2)}</div>
              <div>SGST: ₹${Number(inv.sgst || 0).toFixed(2)}</div>
              ${inv.igst > 0 ? `<div>IGST: ₹${Number(inv.igst).toFixed(2)}</div>` : ''}
            </td>
            <td style="font-weight: 700; font-size: 1rem; color: var(--text-primary);">
              ₹${Number(inv.total_amount || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
            </td>
            <td>
              <span class="badge ${badgeClass}" style="cursor: pointer;" onclick="InvoicesComponent.toggleStatus(${inv.id}, '${isPaid ? 'Unpaid' : 'Paid'}')">
                ${isPaid ? 'Paid' : 'Due'}
              </span>
            </td>
            <td>
              <div style="display: flex; gap: 6px;">
                <button class="btn btn-secondary btn-sm" title="Add Due Date to Google Calendar" onclick="InvoicesComponent.addInvoiceToCalendar('${escapeJsString(inv.invoice_number)}', '${escapeJsString(inv.customer_name || inv.vendor_name)}', '${escapeJsString(inv.due_date || '')}', ${inv.total_amount || 0})">GCal</button>
                <button class="btn btn-secondary btn-sm" onclick="InvoicesComponent.viewDetails(${inv.id})">Details</button>
                <button class="btn btn-secondary btn-sm" style="color: var(--accent-danger);" onclick="InvoicesComponent.deleteInvoice(${inv.id})">X</button>
              </div>
            </td>
          </tr>
        `;
      }).join("");
    } catch (e) {
      console.error("Error loading invoices:", e);
    }
  },

  showInvoiceExtractionModal(inv) {
    let lineItemsHtml = "";
    const items = typeof inv.line_items === "string" ? JSON.parse(inv.line_items || "[]") : (inv.line_items || []);
    
    if (items.length > 0) {
      lineItemsHtml = `
        <div style="margin-top: 14px;">
          <div style="font-weight: 600; font-size: 0.85rem; margin-bottom: 6px; color: var(--text-secondary);">EXTRACTED LINE ITEMS</div>
          <table style="width: 100%; font-size: 0.82rem; border-collapse: collapse;">
            <thead>
              <tr style="background: var(--bg-surface); text-align: left;">
                <th style="padding: 6px 10px;">Item</th>
                <th style="padding: 6px 10px;">Qty</th>
                <th style="padding: 6px 10px;">Rate (₹)</th>
                <th style="padding: 6px 10px; text-align: right;">Amount (₹)</th>
              </tr>
            </thead>
            <tbody>
              ${items.map(item => `
                <tr style="border-bottom: 1px solid var(--border-subtle);">
                  <td style="padding: 6px 10px;">${escapeHtml(item.description || item.desc || '')}</td>
                  <td style="padding: 6px 10px;">${item.quantity || item.qty || 1}</td>
                  <td style="padding: 6px 10px;">₹${Number(item.rate || 0).toLocaleString('en-IN')}</td>
                  <td style="padding: 6px 10px; text-align: right; font-weight: 600;">₹${Number(item.amount || 0).toLocaleString('en-IN')}</td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        </div>
      `;
    }

    document.getElementById("modal-generic-title").innerText = `Auto-Extracted: Invoice #${inv.invoice_number || 'N/A'}`;
    document.getElementById("modal-generic-body").innerHTML = `
      <div style="display: flex; flex-direction: column; gap: 14px;">
        <div style="display: flex; justify-content: space-between; align-items: center; background: var(--bg-surface); padding: 12px 16px; border-radius: 8px;">
          <div>
            <div style="font-size: 0.75rem; color: var(--text-muted);">SUPPLIER / VENDOR</div>
            <div style="font-weight: 700; font-size: 1.05rem;">${escapeHtml(inv.vendor_name)}</div>
            <div style="font-size: 0.8rem; color: var(--accent-primary); font-family: monospace;">GSTIN: ${escapeHtml(inv.vendor_gstin || 'Unspecified')}</div>
          </div>
          <div style="text-align: right;">
            <div style="font-size: 0.75rem; color: var(--text-muted);">TOTAL PAYABLE</div>
            <div style="font-size: 1.4rem; font-weight: 800; color: var(--accent-success);">₹${Number(inv.total_amount).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</div>
          </div>
        </div>

        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; font-size: 0.88rem;">
          <div style="background: var(--bg-card); border: 1px solid var(--border-subtle); padding: 10px; border-radius: 6px;">
            <div style="color: var(--text-muted); font-size: 0.75rem;">Invoice Date</div>
            <div style="font-weight: 600;">${escapeHtml(inv.invoice_date || '-')}</div>
          </div>
          <div style="background: var(--bg-card); border: 1px solid var(--border-subtle); padding: 10px; border-radius: 6px;">
            <div style="color: var(--text-muted); font-size: 0.75rem;">Payment Due Date</div>
            <div style="font-weight: 600; color: var(--accent-warning);">${escapeHtml(inv.due_date || '-')}</div>
          </div>
        </div>

        ${lineItemsHtml}

        <div style="background: rgba(99, 102, 241, 0.08); border: 1px solid rgba(99, 102, 241, 0.2); border-radius: 8px; padding: 12px;">
          <div style="font-weight: 600; font-size: 0.82rem; margin-bottom: 6px; color: var(--accent-primary);">GST & TAX BREAKDOWN</div>
          <div style="display: flex; justify-content: space-between; font-size: 0.85rem; margin-bottom: 4px;">
            <span>Taxable Subtotal:</span>
            <span>₹${Number(inv.subtotal).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
          </div>
          <div style="display: flex; justify-content: space-between; font-size: 0.85rem; margin-bottom: 4px;">
            <span>CGST:</span>
            <span>₹${Number(inv.cgst).toFixed(2)}</span>
          </div>
          <div style="display: flex; justify-content: space-between; font-size: 0.85rem; margin-bottom: 4px;">
            <span>SGST:</span>
            <span>₹${Number(inv.sgst).toFixed(2)}</span>
          </div>
          ${inv.igst > 0 ? `
            <div style="display: flex; justify-content: space-between; font-size: 0.85rem; margin-bottom: 4px;">
              <span>IGST:</span>
              <span>₹${Number(inv.igst).toFixed(2)}</span>
            </div>
          ` : ''}
          <div style="border-top: 1px solid rgba(99, 102, 241, 0.3); padding-top: 6px; margin-top: 6px; display: flex; justify-content: space-between; font-weight: 700;">
            <span>Total Invoice Amount:</span>
            <span style="color: var(--accent-success);">₹${Number(inv.total_amount).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
          </div>
        </div>

        <div style="display: flex; justify-content: flex-end; gap: 10px;">
          <button class="btn btn-secondary" onclick="App.closeModal()">Close</button>
          <button class="btn btn-primary" onclick="App.closeModal(); InvoicesComponent.loadInvoices();">Done</button>
        </div>
      </div>
    `;
    App.openModal();
  },

  async viewDetails(id) {
    const inv = this.invoices.find(i => i.id === id);
    if (inv) this.showInvoiceExtractionModal(inv);
  },

  async toggleStatus(id, newStatus) {
    const formData = new FormData();
    formData.append("status", newStatus);
    try {
      await fetch(`/api/invoices/${id}/status`, { method: "PUT", body: formData });
      App.showToast(`Status updated to ${newStatus}`, "info");
      await this.loadInvoices();
      App.refreshGlobalKPIs();
    } catch (e) {
      console.error(e);
    }
  },

  async deleteInvoice(id) {
    if (!confirm("Are you sure you want to delete this invoice record?")) return;
    try {
      await fetch(`/api/invoices/${id}`, { method: "DELETE" });
      App.showToast("Invoice deleted", "info");
      await this.loadInvoices();
      App.refreshGlobalKPIs();
    } catch (e) {
      console.error(e);
    }
  },

  exportToCSV() {
    if (!this.invoices.length) {
      App.showToast("No invoices to export", "warning");
      return;
    }
    const headers = ["Invoice Number", "Vendor Name", "GSTIN", "Date", "Due Date", "Taxable Value", "CGST", "SGST", "IGST", "Total Amount", "Status"];
    const rows = this.invoices.map(i => [
      `"${i.invoice_number || ''}"`,
      `"${i.vendor_name || ''}"`,
      `"${i.vendor_gstin || ''}"`,
      `"${i.invoice_date || ''}"`,
      `"${i.due_date || ''}"`,
      i.subtotal || 0,
      i.cgst || 0,
      i.sgst || 0,
      i.igst || 0,
      i.total_amount || 0,
      `"${i.status || ''}"`
    ]);

    const csvContent = "data:text/csv;charset=utf-8," + [headers.join(","), ...rows.map(r => r.join(","))].join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `Invoices_Export_Tally_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    App.showToast("CSV exported for Tally / Excel accounting!", "success");
  },

  addInvoiceToCalendar(invNo, party, dueDate, amount) {
    if (!dueDate) {
      App.showToast("No due date found on this invoice.", "warning");
      return;
    }
    // Clean date string to YYYYMMDD
    let cleanDate = dueDate.replace(/[^0-9]/g, "");
    if (cleanDate.length !== 8) {
      const today = new Date();
      cleanDate = today.toISOString().slice(0, 10).replace(/-/g, "");
    }
    const title = `[Payment Due] Invoice #${invNo} - ${party}`;
    const details = `Invoice Payment Follow-up\nInvoice #${invNo}\nParty: ${party}\nAmount: ₹${Number(amount || 0).toLocaleString('en-IN')}\nSettlement generated by PattuBook`;
    const url = `https://calendar.google.com/calendar/render?action=TEMPLATE&text=${encodeURIComponent(title)}&dates=${cleanDate}/${cleanDate}&details=${encodeURIComponent(details)}&location=Store+Office`;
    window.open(url, "_blank");
  }
};
