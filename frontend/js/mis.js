// PattuBook - Business MIS Reports & Spreadsheet Intelligence Component
const MISComponent = {
  data: null,

  async init() {
    this.setupExcelDropzone();
    await this.loadReport();
  },

  setupExcelDropzone() {
    const dropzone = document.getElementById("mis-dropzone");
    const fileInput = document.getElementById("mis-file-input");

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
        this.handleExcelUpload(e.dataTransfer.files[0]);
      }
    });

    fileInput.addEventListener("change", (e) => {
      if (e.target.files.length > 0) {
        this.handleExcelUpload(e.target.files[0]);
      }
    });
  },

  async handleExcelUpload(file) {
    if (!file) return;
    App.showToast(`Parsing spreadsheet ${file.name}...`, "info");
    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch("/api/mis/upload", {
        method: "POST",
        body: formData
      });
      const result = await res.json();
      if (res.ok) {
        if (result.count > 0) {
          const skipMsg = result.skipped > 0 ? ` (${result.skipped} existing skipped)` : "";
          App.showToast(`Ingested ${result.count} new transactions${skipMsg}!`, "success");
        } else {
          App.showToast(result.message || "All records are already up to date.", "info");
        }
        await this.loadReport();
        App.refreshGlobalKPIs();
      } else {
        App.showToast("Failed to parse sheet: " + result.detail, "danger");
      }
    } catch (e) {
      App.showToast("Upload failed: " + e.message, "danger");
    }
  },

  async loadSampleLedger() {
    App.showToast("Loading September Retail Sales Ledger...", "info");
    try {
      const res = await fetch("/api/mis/load-sample", { method: "POST" });
      const result = await res.json();
      if (res.ok) {
        App.showToast("Sample sales ledger imported!", "success");
        await this.loadReport();
        App.refreshGlobalKPIs();
      } else {
        App.showToast("Error: " + result.detail, "danger");
      }
    } catch (e) {
      App.showToast("Error loading sample: " + e.message, "danger");
    }
  },

  async loadReport() {
    try {
      const res = await fetch("/api/mis/report");
      this.data = await res.json();
      this.renderReport(this.data);
    } catch (e) {
      console.error("Error loading MIS report:", e);
    }
  },

  renderReport(d) {
    // 1. Metric numbers
    document.getElementById("mis-total-sales").innerText = `₹ ${Number(d.total_sales || 0).toLocaleString('en-IN')}`;
    document.getElementById("mis-total-expenses").innerText = `₹ ${Number((d.total_purchases || 0) + (d.total_expenses || 0)).toLocaleString('en-IN')}`;
    
    const expBreakdownEl = document.getElementById("mis-expenses-breakdown");
    if (expBreakdownEl) {
      expBreakdownEl.innerText = `Store Exp: ₹${Number(d.total_expenses || 0).toLocaleString('en-IN')} | Bills: ₹${Number(d.total_purchases || 0).toLocaleString('en-IN')}`;
    }

    const payablesEl = document.getElementById("mis-total-payables");
    if (payablesEl) {
      payablesEl.innerText = `₹ ${Number(d.total_payables || 0).toLocaleString('en-IN')}`;
    }
    const payablesSub = document.getElementById("mis-payables-subtext");
    if (payablesSub) {
      payablesSub.innerText = `${(d.settled_purchases || 0) > 0 ? `Settled: ₹${Number(d.settled_purchases).toLocaleString('en-IN')}` : 'No bills settled'}`;
    }

    const cashEl = document.getElementById("mis-net-cash");
    const cashVal = Number(d.net_cash_flow || 0);
    cashEl.innerText = `₹ ${cashVal.toLocaleString('en-IN')}`;
    cashEl.style.color = cashVal >= 0 ? "var(--accent-success)" : "var(--accent-danger)";

    document.getElementById("mis-receivables").innerText = `₹ ${Number(d.total_receivables || 0).toLocaleString('en-IN')}`;

    // 2. Aging Cards
    const aging = d.aging || {};
    document.getElementById("aging-0-15").innerText = `₹ ${Number(aging["0_15"] || 0).toLocaleString('en-IN')}`;
    document.getElementById("aging-16-30").innerText = `₹ ${Number(aging["16_30"] || 0).toLocaleString('en-IN')}`;
    document.getElementById("aging-31-60").innerText = `₹ ${Number(aging["31_60"] || 0).toLocaleString('en-IN')}`;
    document.getElementById("aging-60-plus").innerText = `₹ ${Number(aging["60_plus"] || 0).toLocaleString('en-IN')}`;

    // 3. Top Debtors Table
    const tbody = document.getElementById("debtors-table-body");
    if (tbody) {
      if (!d.top_debtors || d.top_debtors.length === 0) {
        tbody.innerHTML = `<tr><td colspan="4" style="text-align: center; color: var(--text-muted); padding: 20px;">No outstanding customer balances recorded.</td></tr>`;
      } else {
        tbody.innerHTML = d.top_debtors.map((deb, idx) => `
          <tr>
            <td style="font-weight: 600;">
              <span style="color: var(--text-muted); margin-right: 6px;">#${idx + 1}</span>
              ${escapeHtml(deb.party_name)}
            </td>
            <td style="font-weight: 700; color: var(--accent-danger); font-size: 0.95rem;">
              ₹${Number(deb.amount).toLocaleString('en-IN')}
            </td>
            <td>
              <span class="badge ${deb.amount > 50000 ? 'badge-danger' : 'badge-warning'}">
                ${deb.amount > 50000 ? 'High Exposure' : 'Follow Up'}
              </span>
            </td>
            <td>
              <button class="btn btn-whatsapp btn-sm" onclick="MISComponent.triggerReminder('${escapeJsString(deb.party_name)}', ${deb.amount})">
                Remind WhatsApp
              </button>
            </td>
          </tr>
        `).join("");
      }
    }

    // 4. AI Executive Commentary
    const commBox = document.getElementById("mis-ai-commentary");
    if (commBox) {
      commBox.innerHTML = `
        <div style="line-height: 1.7; font-size: 0.92rem;">
          ${(d.ai_commentary || '').split("\n").map(l => {
            const formatted = l.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
            return formatted.startsWith("•") ? `<div style="margin-bottom: 6px;">${formatted}</div>` : `<p>${formatted}</p>`;
          }).join("")}
        </div>
      `;
    }

    // 5. Draw Trend Chart
    this.drawChart(d.daily_trends);

    // 6. Vendor Purchases & Payables Table
    const purchBody = document.getElementById("purchases-table-body");
    if (purchBody) {
      if (!d.recent_purchases || d.recent_purchases.length === 0) {
        purchBody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 20px;">No vendor purchases or bills recorded yet.</td></tr>`;
      } else {
        purchBody.innerHTML = d.recent_purchases.map(p => {
          const isSettled = (p.status || '').toLowerCase() === 'settled';
          return `
            <tr>
              <td style="font-size: 0.85rem; color: var(--text-secondary);">${escapeHtml(p.date || '-')}</td>
              <td style="font-weight: 600;">${escapeHtml(p.party_name || 'Vendor')}</td>
              <td style="font-family: monospace; font-size: 0.85rem; color: var(--text-muted);">${escapeHtml(p.reference_no || '-')}</td>
              <td style="font-weight: 700; color: var(--accent-danger); font-size: 0.95rem;">₹${Number(p.amount).toLocaleString('en-IN')}</td>
              <td>
                <span class="badge ${isSettled ? 'badge-success' : 'badge-warning'}">
                  ${isSettled ? 'Settled (Paid)' : 'Pending Due'}
                </span>
              </td>
              <td>
                <button class="btn btn-secondary btn-sm" onclick="App.switchTab('invoices-view')">
                  View in Bills
                </button>
              </td>
            </tr>
          `;
        }).join("");
      }
    }
  },

  triggerReminder(partyName, amount) {
    App.switchTab("comms-view");
    CommsComponent.prefillForCustomer(partyName, amount);
  },

  drawChart(trends) {
    const canvas = document.getElementById("mis-trend-canvas");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    
    // Resize for high DPI
    const rect = canvas.parentElement.getBoundingClientRect();
    canvas.width = rect.width;
    canvas.height = 280;

    const width = canvas.width;
    const height = canvas.height;
    ctx.clearRect(0, 0, width, height);

    if (!trends || !trends.labels || trends.labels.length === 0) {
      ctx.fillStyle = "#64748b";
      ctx.font = "14px Inter";
      ctx.textAlign = "center";
      ctx.fillText("No transactions recorded to plot trend graph", width / 2, height / 2);
      return;
    }

    const labels = trends.labels;
    const sales = trends.sales;
    const expenses = trends.expenses;

    const maxVal = Math.max(...sales, ...expenses, 10000) * 1.15;
    const padding = { top: 30, right: 30, bottom: 40, left: 60 };
    const chartW = width - padding.left - padding.right;
    const chartH = height - padding.top - padding.bottom;

    // Draw horizontal grid lines
    ctx.strokeStyle = "rgba(255, 255, 255, 0.06)";
    ctx.lineWidth = 1;
    ctx.fillStyle = "#94a3b8";
    ctx.font = "11px Inter";
    ctx.textAlign = "right";

    const steps = 4;
    for (let i = 0; i <= steps; i++) {
      const yVal = (maxVal / steps) * i;
      const y = height - padding.bottom - (i / steps) * chartH;
      ctx.beginPath();
      ctx.moveTo(padding.left, y);
      ctx.lineTo(width - padding.right, y);
      ctx.stroke();
      ctx.fillText(`₹${(yVal / 1000).toFixed(0)}k`, padding.left - 10, y + 4);
    }

    // Draw Sales Bars (Green gradient)
    const barW = Math.max(6, (chartW / labels.length) * 0.35);
    const spacing = chartW / labels.length;

    labels.forEach((lbl, idx) => {
      const x = padding.left + idx * spacing + spacing / 4;
      const val = sales[idx];
      const h = (val / maxVal) * chartH;
      const y = height - padding.bottom - h;

      // Sales Bar
      ctx.fillStyle = "#10b981";
      ctx.beginPath();
      ctx.roundRect ? ctx.roundRect(x, y, barW, h, [4, 4, 0, 0]) : ctx.rect(x, y, barW, h);
      ctx.fill();

      // Expense Bar
      const expVal = expenses[idx];
      const expH = (expVal / maxVal) * chartH;
      const expY = height - padding.bottom - expH;
      ctx.fillStyle = "#f43f5e";
      ctx.beginPath();
      ctx.roundRect ? ctx.roundRect(x + barW + 2, expY, barW, expH, [4, 4, 0, 0]) : ctx.rect(x + barW + 2, expY, barW, expH);
      ctx.fill();

      // X Axis Label
      ctx.fillStyle = "#64748b";
      ctx.font = "10px Inter";
      ctx.textAlign = "center";
      const shortDate = lbl.length >= 10 ? lbl.slice(5) : lbl;
      ctx.fillText(shortDate, x + barW, height - 15);
    });

    // Draw Legend
    ctx.textAlign = "left";
    ctx.font = "12px Inter";
    // Sales legend
    ctx.fillStyle = "#10b981";
    ctx.fillRect(width - 180, 10, 12, 12);
    ctx.fillStyle = "#f8fafc";
    ctx.fillText("Sales", width - 162, 20);
    // Expense legend
    ctx.fillStyle = "#f43f5e";
    ctx.fillRect(width - 100, 10, 12, 12);
    ctx.fillStyle = "#f8fafc";
    ctx.fillText("Expenses", width - 82, 20);
  }
};
