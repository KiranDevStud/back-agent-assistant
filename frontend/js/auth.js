// PattuBook - Authentication & Email Verification Component

async function safeJson(res) {
  try {
    return await res.json();
  } catch (e) {
    return { detail: `Server responded with status ${res.status}` };
  }
}

const AuthComponent = {
  currentUser: null,
  token: localStorage.getItem("pattubook_token") || null,

  async init() {
    this.checkUrlForVerificationToken();
    if (this.token) {
      await this.loadUserProfile();
    } else {
      this.updateAuthUI();
    }
  },

  checkUrlForVerificationToken() {
    // Check if URL has hash with #verify?token=...
    const hash = window.location.hash;
    if (hash.includes("token=")) {
      const params = new URLSearchParams(hash.replace(/^#\/?verify\??/, ""));
      const token = params.get("token");
      const email = params.get("email");
      if (token) {
        setTimeout(() => {
          this.openAuthModal("verify");
          const tokenInput = document.getElementById("auth-verify-token");
          if (tokenInput) tokenInput.value = token;
          const emailInput = document.getElementById("auth-verify-email");
          if (emailInput && email) emailInput.value = email;
          App.showToast("Verification token detected. Click 'Verify Account' to finish!", "info");
        }, 500);
      }
    }
  },

  getAuthHeaders() {
    const headers = { "Content-Type": "application/json" };
    if (this.token) {
      headers["Authorization"] = `Bearer ${this.token}`;
    }
    return headers;
  },

  async loadUserProfile() {
    try {
      const res = await fetch("/api/auth/me", {
        headers: { "Authorization": `Bearer ${this.token}` }
      });
      if (res.ok) {
        const data = await safeJson(res);
        this.currentUser = data.user;
        this.updateAuthUI();
      } else {
        // Token expired or invalid
        this.logout(false);
      }
    } catch (e) {
      console.warn("Could not fetch user profile:", e);
      this.updateAuthUI();
    }
  },

  updateAuthUI() {
    const nameEl = document.getElementById("sidebar-user-name");
    const avatarEl = document.getElementById("sidebar-user-avatar");
    const storeBadge = document.getElementById("nav-store-name");
    const gstinBadge = document.getElementById("nav-store-gstin");
    const authBtn = document.getElementById("header-auth-btn");

    if (this.currentUser) {
      if (nameEl) nameEl.innerText = this.currentUser.full_name || "Business Owner";
      if (avatarEl) {
        const initials = (this.currentUser.full_name || "BO")
          .split(" ")
          .map(n => n[0])
          .join("")
          .substring(0, 2)
          .toUpperCase();
        avatarEl.innerText = initials;
      }
      if (storeBadge) storeBadge.innerText = this.currentUser.business_name || "My Business";
      if (gstinBadge) gstinBadge.innerText = `GSTIN: ${this.currentUser.gstin || "Unregistered"}`;
      if (authBtn) {
        authBtn.innerHTML = `${escapeHtml(this.currentUser.full_name.split(" ")[0])} (Sign Out)`;
        authBtn.onclick = () => this.confirmLogout();
        authBtn.classList.remove("btn-primary");
        authBtn.classList.add("btn-secondary");
      }
    } else {
      if (nameEl) nameEl.innerText = "Guest / Demo Mode";
      if (avatarEl) avatarEl.innerText = "DM";
      if (authBtn) {
        authBtn.innerHTML = `Sign In / Register`;
        authBtn.onclick = () => window.location.href = "/login";
        authBtn.classList.remove("btn-secondary");
        authBtn.classList.add("btn-primary");
      }
    }
  },

  openAuthModal(tab = "signin") {
    const modal = document.getElementById("generic-modal");
    const title = document.getElementById("modal-generic-title");
    const body = document.getElementById("modal-generic-body");
    if (!modal || !title || !body) return;

    title.innerText = "PattuBook Account & Authentication";
    body.innerHTML = `
      <div class="auth-tabs" style="display: flex; gap: 8px; margin-bottom: 20px; border-bottom: 1px solid var(--border-subtle); padding-bottom: 10px;">
        <button class="btn btn-sm ${tab === 'signin' ? 'btn-primary' : 'btn-secondary'}" id="tab-btn-signin" onclick="AuthComponent.switchAuthTab('signin')">Sign In</button>
        <button class="btn btn-sm ${tab === 'signup' ? 'btn-primary' : 'btn-secondary'}" id="tab-btn-signup" onclick="AuthComponent.switchAuthTab('signup')">Create Account</button>
        <button class="btn btn-sm ${tab === 'verify' ? 'btn-primary' : 'btn-secondary'}" id="tab-btn-verify" onclick="AuthComponent.switchAuthTab('verify')">Verify Email</button>
      </div>

      <!-- Sign In Form -->
      <div id="auth-panel-signin" style="display: ${tab === 'signin' ? 'block' : 'none'};">
        <form onsubmit="AuthComponent.handleLogin(event)">
          <div class="form-group">
            <label class="form-label">Email Address</label>
            <input type="email" id="auth-login-email" class="form-input" placeholder="e.g. ramesh@omsaigroups.in" required />
          </div>
          <div class="form-group">
            <label class="form-label">Password</label>
            <input type="password" id="auth-login-password" class="form-input" placeholder="••••••••" required />
          </div>
          <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 18px;">
            <a href="javascript:void(0)" onclick="AuthComponent.switchAuthTab('signup')" style="font-size: 0.82rem; color: var(--accent-primary);">Create account</a>
            <button type="submit" class="btn btn-primary" id="btn-submit-login">Sign In</button>
          </div>
        </form>
      </div>

      <!-- Sign Up Form -->
      <div id="auth-panel-signup" style="display: ${tab === 'signup' ? 'block' : 'none'};">
        <form onsubmit="AuthComponent.handleSignup(event)">
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
            <div class="form-group">
              <label class="form-label">Full Name</label>
              <input type="text" id="auth-signup-name" class="form-input" placeholder="Ramesh K. Gupta" required />
            </div>
            <div class="form-group">
              <label class="form-label">Business / Shop Name</label>
              <input type="text" id="auth-signup-biz" class="form-input" placeholder="Om Sai Traders" required />
            </div>
          </div>
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
            <div class="form-group">
              <label class="form-label">GSTIN (Optional)</label>
              <input type="text" id="auth-signup-gstin" class="form-input" placeholder="27AAPCG1234F1Z8" />
            </div>
            <div class="form-group">
              <label class="form-label">Phone / WhatsApp</label>
              <input type="text" id="auth-signup-phone" class="form-input" placeholder="+91 98200 12345" />
            </div>
          </div>
          <div class="form-group">
            <label class="form-label">Email Address</label>
            <input type="email" id="auth-signup-email" class="form-input" placeholder="contact@omsaigroups.in" required />
          </div>
          <div class="form-group">
            <label class="form-label">Password</label>
            <input type="password" id="auth-signup-password" class="form-input" placeholder="At least 6 characters" required minlength="6" />
          </div>
          <div style="margin-top: 18px; display: flex; justify-content: space-between; align-items: center;">
            <a href="javascript:void(0)" onclick="AuthComponent.switchAuthTab('signin')" style="font-size: 0.82rem; color: var(--accent-primary);">Already have an account?</a>
            <button type="submit" class="btn btn-primary" id="btn-submit-signup">Register & Send Verification</button>
          </div>
        </form>
      </div>

      <!-- Verify Email Form -->
      <div id="auth-panel-verify" style="display: ${tab === 'verify' ? 'block' : 'none'};">
        <p style="font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 16px;">
          Enter the verification code/token received via email to activate your account.
        </p>
        <div id="auth-verify-banner" style="display: none; background: rgba(99, 102, 241, 0.12); border: 1px solid var(--accent-primary); border-radius: var(--radius-sm); padding: 12px; margin-bottom: 16px;"></div>
        <form onsubmit="AuthComponent.handleVerifyEmail(event)">
          <div class="form-group">
            <label class="form-label">Registered Email</label>
            <input type="email" id="auth-verify-email" class="form-input" placeholder="your@email.com" />
          </div>
          <div class="form-group">
            <label class="form-label">Verification Token</label>
            <input type="text" id="auth-verify-token" class="form-input" placeholder="Paste 32-character verification token" required />
          </div>
          <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 18px;">
            <button type="button" class="btn btn-secondary btn-sm" onclick="AuthComponent.handleResendVerification()">Resend Code</button>
            <button type="submit" class="btn btn-primary" id="btn-submit-verify">Verify & Activate Account</button>
          </div>
        </form>
      </div>
    `;

    App.openModal();
  },

  switchAuthTab(tab) {
    ["signin", "signup", "verify"].forEach(t => {
      const panel = document.getElementById(`auth-panel-${t}`);
      const btn = document.getElementById(`tab-btn-${t}`);
      if (panel) panel.style.display = t === tab ? "block" : "none";
      if (btn) {
        if (t === tab) {
          btn.classList.remove("btn-secondary");
          btn.classList.add("btn-primary");
        } else {
          btn.classList.remove("btn-primary");
          btn.classList.add("btn-secondary");
        }
      }
    });
  },

  async handleSignup(e) {
    e.preventDefault();
    const btn = document.getElementById("btn-submit-signup");
    btn.disabled = true;
    btn.innerText = "Creating Account...";

    const payload = {
      full_name: document.getElementById("auth-signup-name").value,
      business_name: document.getElementById("auth-signup-biz").value,
      gstin: document.getElementById("auth-signup-gstin").value,
      phone: document.getElementById("auth-signup-phone").value,
      email: document.getElementById("auth-signup-email").value,
      password: document.getElementById("auth-signup-password").value,
    };

    try {
      const res = await fetch("/api/auth/signup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await safeJson(res);
      if (!res.ok) {
        throw new Error(data.detail || "Signup failed");
      }

      App.showToast("Account created! Verification code issued.", "success");
      
      // Switch to verify tab
      this.switchAuthTab("verify");
      const emailInput = document.getElementById("auth-verify-email");
      if (emailInput) emailInput.value = payload.email;

      // In dev mode or direct preview, show token banner for 1-click verification
      if (data.verification && data.verification.token) {
        const tokenInput = document.getElementById("auth-verify-token");
        if (tokenInput) tokenInput.value = data.verification.token;

        const banner = document.getElementById("auth-verify-banner");
        if (banner) {
          banner.style.display = "block";
          banner.innerHTML = `
            <div style="font-size: 0.82rem; color: var(--accent-info); font-weight: 600; margin-bottom: 4px;">Instant Dev Verification Ready:</div>
            <div style="font-size: 0.78rem; color: var(--text-muted); margin-bottom: 8px;">Token auto-filled below. Click the button to activate now:</div>
            <button type="button" class="btn btn-primary btn-sm" onclick="AuthComponent.handleVerifyEmail(event)">
              1-Click Activate Account Now
            </button>
          `;
        }
      }
    } catch (err) {
      App.showToast(err.message, "danger");
    } finally {
      btn.disabled = false;
      btn.innerText = "Register & Send Verification";
    }
  },

  async handleVerifyEmail(e) {
    if (e) e.preventDefault();
    const token = document.getElementById("auth-verify-token").value.trim();
    const email = document.getElementById("auth-verify-email") ? document.getElementById("auth-verify-email").value.trim() : "";

    if (!token) {
      App.showToast("Please enter a verification token.", "warning");
      return;
    }

    try {
      const res = await fetch("/api/auth/verify-email", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, email: email || undefined })
      });
      const data = await safeJson(res);
      if (!res.ok) {
        throw new Error(data.detail || "Verification failed");
      }

      this.token = data.access_token;
      localStorage.setItem("pattubook_token", this.token);
      this.currentUser = data.user;
      this.updateAuthUI();

      App.closeModal();
      App.showToast(`Welcome ${this.currentUser.full_name}! Account verified and logged in.`, "success");

      // Reload settings & KPIs for user
      await SettingsComponent.loadSettings();
      await App.refreshGlobalKPIs();
    } catch (err) {
      App.showToast(err.message, "danger");
    }
  },

  async handleResendVerification() {
    const email = document.getElementById("auth-verify-email") ? document.getElementById("auth-verify-email").value.trim() : "";
    if (!email) {
      App.showToast("Please enter your registered email address first.", "warning");
      return;
    }

    try {
      const res = await fetch("/api/auth/resend-verification", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email })
      });
      const data = await safeJson(res);
      if (!res.ok) throw new Error(data.detail || "Failed to resend");

      App.showToast(data.message, "success");
      if (data.verification && data.verification.token) {
        const tokenInput = document.getElementById("auth-verify-token");
        if (tokenInput) tokenInput.value = data.verification.token;
      }
    } catch (err) {
      App.showToast(err.message, "danger");
    }
  },

  async handleLogin(e) {
    e.preventDefault();
    const email = document.getElementById("auth-login-email").value.trim();
    const password = document.getElementById("auth-login-password").value;

    const btn = document.getElementById("btn-submit-login");
    btn.disabled = true;
    btn.innerText = "Signing in...";

    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password })
      });
      const data = await safeJson(res);

      if (res.status === 403) {
        // Unverified email
        App.showToast(data.detail || "Please verify your email address.", "warning");
        this.switchAuthTab("verify");
        const emailInput = document.getElementById("auth-verify-email");
        if (emailInput) emailInput.value = email;
        return;
      }

      if (!res.ok) {
        throw new Error(data.detail || "Login failed");
      }

      this.token = data.access_token;
      localStorage.setItem("pattubook_token", this.token);
      this.currentUser = data.user;
      this.updateAuthUI();

      App.closeModal();
      App.showToast(`Logged in as ${this.currentUser.full_name}!`, "success");

      // Refresh app data
      await SettingsComponent.loadSettings();
      await InvoicesComponent.loadInvoices();
      await App.refreshGlobalKPIs();
    } catch (err) {
      App.showToast(err.message, "danger");
    } finally {
      btn.disabled = false;
      btn.innerText = "Sign In";
    }
  },

  confirmLogout() {
    if (confirm("Are you sure you want to sign out?")) {
      this.logout(true);
    }
  },

  logout(showNotice = true) {
    this.token = null;
    this.currentUser = null;
    localStorage.removeItem("pattubook_token");
    this.updateAuthUI();
    if (showNotice) {
      App.showToast("Signed out. Switched to Guest / Demo mode.", "info");
      SettingsComponent.loadSettings();
    }
  }
};
