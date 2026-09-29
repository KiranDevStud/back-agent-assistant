// PattuBook - Interactive Gemini Back Office Assistant Component
function safeEscapeHtml(text) {
  if (!text) return "";
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

const AssistantComponent = {
  chatHistory: [],
  isWaiting: false,

  async init() {
    this.bindEvents();
    this.clearChat();
    await this.checkStatus();
  },

  async checkStatus() {
    try {
      const res = await fetch("/api/status");
      const data = await res.json();
      const statusBadge = document.getElementById("assistant-status-badge");
      if (statusBadge) {
        if (data.ai && data.ai.local_ai && data.ai.local_ai.available) {
          statusBadge.className = "badge badge-success";
          statusBadge.innerText = `${data.ai.local_ai.active_model || 'gemma2:2b'} (Local) Connected`;
        } else {
          statusBadge.className = "badge badge-success";
          statusBadge.innerText = "100% Local AI Active";
        }
      }
    } catch (e) {
      console.error("Failed to check assistant status:", e);
    }
  },

  bindEvents() {
    const sendBtn = document.getElementById("assistant-send-btn");
    const inputEl = document.getElementById("assistant-input");
    const clearBtn = document.getElementById("assistant-clear-btn");

    if (sendBtn && inputEl) {
      sendBtn.addEventListener("click", () => this.handleSend());
      inputEl.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();
          this.handleSend();
        }
      });
    }

    if (clearBtn) {
      clearBtn.addEventListener("click", () => this.clearChat());
    }
  },

  askSuggested(promptText) {
    const inputEl = document.getElementById("assistant-input");
    if (inputEl) {
      inputEl.value = promptText;
      this.handleSend();
    }
  },

  clearChat() {
    this.chatHistory = [];
    const chatContainer = document.getElementById("assistant-chat-log");
    if (!chatContainer) return;

    const prompts = [
      { title: "Current Debt & Payables", desc: "What is my current debt and who do I owe money to?" },
      { title: "Market Credit & Receivables", desc: "How much money is pending from customers in the market?" },
      { title: "Sales & Cash Velocity", desc: "What are my recorded sales and net cash position this month?" },
      { title: "Top Overdue Customers", desc: "Who are my top overdue debtors and what is their aging?" },
      { title: "GST & ITC Rules", desc: "Explain ITC reconciliation rules under GSTR-2B" },
      { title: "Draft Payment Notice", desc: "Draft a professional payment demand notice for an overdue bill" }
    ];

    chatContainer.innerHTML = `
      <div style="text-align: center; max-width: 680px; margin: 24px auto; padding: 10px;">
        <h3 style="color: var(--text-primary); font-size: 1.25rem; font-weight: 700; margin-bottom: 8px;">
          How can I assist your business today?
        </h3>
        <p style="font-size: 0.88rem; color: var(--text-secondary); margin-bottom: 24px; line-height: 1.5;">
          Ask questions about your live debts, sales, customer receivables, Indian GST compliance, or draft professional vendor letters.
        </p>

        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; text-align: left;">
          ${prompts.map(p => {
            const safeDesc = safeEscapeHtml(p.desc).replace(/'/g, "\\'");
            return `
              <div onclick="AssistantComponent.askSuggested('${safeDesc}')"
                   style="background: var(--bg-surface); border: 1px solid var(--border-subtle); border-radius: 10px; padding: 12px 14px; cursor: pointer; transition: all 0.2s ease;"
                   onmouseover="this.style.borderColor='var(--accent-primary)'; this.style.transform='translateY(-2px)';"
                   onmouseout="this.style.borderColor='var(--border-subtle)'; this.style.transform='none';">
                <div style="font-size: 0.84rem; font-weight: 600; color: var(--accent-primary); margin-bottom: 3px;">
                  ${safeEscapeHtml(p.title)}
                </div>
                <div style="font-size: 0.78rem; color: var(--text-muted); line-height: 1.35;">
                  ${safeEscapeHtml(p.desc)}
                </div>
              </div>
            `;
          }).join("")}
        </div>
      </div>
    `;
  },

  async handleSend() {
    const inputEl = document.getElementById("assistant-input");
    if (!inputEl) return;
    const text = inputEl.value.trim();
    if (!text || this.isWaiting) return;

    // Add user message
    this.chatHistory.push({ sender: "user", text: text, time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) });
    inputEl.value = "";
    this.renderChat();

    this.isWaiting = true;
    this.renderTypingIndicator();

    try {
      const res = await fetch("/api/assistant/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text })
      });
      const data = await res.json();
      this.chatHistory.push({
        sender: "assistant",
        text: data.reply || "No response received.",
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      });
    } catch (e) {
      this.chatHistory.push({
        sender: "assistant",
        text: "Error communicating with assistant: " + e.message,
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      });
    } finally {
      this.isWaiting = false;
      this.removeTypingIndicator();
      this.renderChat();
    }
  },

  renderChat() {
    const chatContainer = document.getElementById("assistant-chat-log");
    if (!chatContainer) return;

    if (this.chatHistory.length === 0) {
      this.clearChat();
      return;
    }

    chatContainer.innerHTML = this.chatHistory.map(msg => {
      const isUser = msg.sender === "user";
      const formattedText = this.formatAssistantMarkdown(msg.text);

      return `
        <div style="display: flex; justify-content: ${isUser ? 'flex-end' : 'flex-start'}; margin-bottom: 16px;">
          <div style="max-width: ${isUser ? '75%' : '85%'}; background: ${isUser ? 'var(--accent-primary)' : 'var(--bg-surface)'}; color: ${isUser ? '#ffffff' : 'var(--text-primary)'}; padding: 14px 18px; border-radius: ${isUser ? '16px 16px 4px 16px' : '16px 16px 16px 4px'}; border: 1px solid ${isUser ? 'transparent' : 'var(--border-subtle)'}; box-shadow: 0 4px 12px rgba(0,0,0,0.08); font-size: 0.92rem; line-height: 1.55;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; font-size: 0.75rem; opacity: 0.85;">
              <strong>${isUser ? 'You' : 'PattuBook Assistant'}</strong>
              <span>${msg.time}</span>
            </div>
            <div style="white-space: pre-wrap;">${formattedText}</div>
          </div>
        </div>
      `;
    }).join("");

    chatContainer.scrollTop = chatContainer.scrollHeight;
  },

  renderTypingIndicator() {
    const chatContainer = document.getElementById("assistant-chat-log");
    if (!chatContainer) return;
    const typingEl = document.createElement("div");
    typingEl.id = "assistant-typing-indicator";
    typingEl.style = "display: flex; justify-content: flex-start; margin-bottom: 16px;";
    typingEl.innerHTML = `
      <div style="background: var(--bg-surface); padding: 12px 18px; border-radius: 16px; border: 1px solid var(--border-subtle); font-size: 0.85rem; color: var(--text-muted); display: flex; align-items: center; gap: 8px;">
        <span>PattuBook is thinking...</span>
      </div>
    `;
    chatContainer.appendChild(typingEl);
    chatContainer.scrollTop = chatContainer.scrollHeight;
  },

  removeTypingIndicator() {
    const el = document.getElementById("assistant-typing-indicator");
    if (el) el.remove();
  },

  formatAssistantMarkdown(text) {
    if (!text) return "";
    let formatted = safeEscapeHtml(text);
    // Bold **text**
    formatted = formatted.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    // Bullet lists
    formatted = formatted.replace(/^\s*[•\-\*]\s+(.*)$/gm, '<div style="margin-left: 12px; margin-bottom: 4px;">• $1</div>');
    return formatted;
  }
};

window.AssistantComponent = AssistantComponent;

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => {
    AssistantComponent.init();
  });
} else {
  AssistantComponent.init();
}
