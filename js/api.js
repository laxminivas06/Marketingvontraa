/**
 * AIVONTRAA AUTOMATION PVT. LTD.
 * Website: www.aivontraa.com | Admin: admin@aivontraa.com
 * Official Logo: https://aivontraa.com/assets/images/ai.png
 * 
 * Unified State, Clean URL Router, Document & Google Auth API Client
 */

const API = {
  state: {
    categories: [],
    commissionSlabsINR: [],
    commissionSlabsUSD: [],
    addons: [],
    quotations: [],
    projects: [],
    users: [],
    marketingResponsibilities: []
  },
  currentUser: null,

  // 14-Stage Engineering & Delivery Workflow
  PROJECT_STAGES: [
    'Assigned',
    'Development Started',
    'Frontend Development',
    'Backend Development',
    'Testing',
    'Testing Website Submitted',
    'Changes Requested',
    'Changes In Progress',
    'Final Website Submitted',
    'Admin Review',
    'Approved',
    'Payment Pending',
    'Payment Verified',
    'Project Completed'
  ],

  // Strict Quotation Lifecycle
  QUOTATION_LIFECYCLE: [
    'Draft',
    'Generated',
    'Sent to Customer',
    'Accepted',
    'Rejected'
  ],

  // Marketing Responsibilities (Excluding Admin)
  MARKETING_RESPONSIBILITIES: [
    'Marketing Executive',
    'Client Communication',
    'Payment Collection',
    'Customer Follow-up',
    'Requirement Collection',
    'Documentation',
    'Project Coordination',
    'Other Responsibilities'
  ],

  async request(endpoint, method = 'GET', data = null) {
    try {
      const options = {
        method,
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        }
      };

      const user = this.getCurrentUser();
      if (user) {
        options.headers['X-User-Role'] = user.role;
        options.headers['X-User-Id'] = user.id;
        options.headers['X-User-Name'] = user.name || user.email;
      }

      if (data && (method === 'POST' || method === 'PUT')) {
        options.body = JSON.stringify(data);
      }

      const res = await fetch(endpoint, options);
      const json = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(json.message || `API request failed with status ${res.status}`);
      }
      return json;
    } catch (err) {
      console.warn(`API [${method} ${endpoint}] error:`, err);
      throw err;
    }
  },

  async syncState() {
    try {
      const data = await this.request('/api/state');
      this.state = data;
      return data;
    } catch (err) {
      console.error('Failed to sync state from backend:', err);
      return this.state;
    }
  },

  // -------------------------------------------------------------
  // Clean URL Routing & History API Management
  // -------------------------------------------------------------
  initRouting(basePath, defaultTab, onTabChange) {
    const getTabFromLocation = () => {
      const path = window.location.pathname.replace(/\/+$/, '');
      const base = basePath.replace(/\/+$/, '');
      if (path.startsWith(base)) {
        const sub = path.substring(base.length).replace(/^\/+/, '');
        if (sub) return sub;
      }

      const params = new URLSearchParams(window.location.search);
      if (params.get('tab')) return params.get('tab');

      const hash = window.location.hash.replace('#', '').trim();
      if (hash) return hash;

      return defaultTab;
    };

    const activeTab = getTabFromLocation();

    window.addEventListener('popstate', (e) => {
      const targetTab = (e.state && e.state.tab) ? e.state.tab : getTabFromLocation();
      if (typeof onTabChange === 'function') {
        onTabChange(targetTab, false);
      }
    });

    return activeTab;
  },

  navigate(basePath, tabId, title = '') {
    const cleanBase = basePath.replace(/\/+$/, '');
    const newUrl = `${cleanBase}/${tabId}`;
    try {
      window.history.pushState({ tab: tabId }, title || document.title, newUrl);
    } catch (e) {
      window.location.hash = tabId;
    }
  },

  // -------------------------------------------------------------
  // Authentication & Permissions (Google Only)
  // -------------------------------------------------------------
  getCurrentUser() {
    if (this.currentUser) return this.currentUser;
    // Migrate legacy iwa_user if exists
    let stored = localStorage.getItem('aivontraa_user');
    if (!stored) {
      const legacy = localStorage.getItem('iwa_user');
      if (legacy) {
        localStorage.setItem('aivontraa_user', legacy);
        localStorage.removeItem('iwa_user');
        stored = legacy;
      }
    }

    if (stored) {
      try {
        this.currentUser = JSON.parse(stored);
        return this.currentUser;
      } catch (e) {
        localStorage.removeItem('aivontraa_user');
      }
    }
    return null;
  },

  setCurrentUser(user) {
    this.currentUser = user;
    if (user) {
      localStorage.setItem('aivontraa_user', JSON.stringify(user));
    } else {
      localStorage.removeItem('aivontraa_user');
      localStorage.removeItem('iwa_user');
    }
  },

  async loginWithGoogleEmail(email, name = '') {
    const res = await this.request('/api/auth/google', 'POST', {
      email,
      name
    });
    if (res.success && res.user) {
      this.setCurrentUser(res.user);
      return res.user;
    }
    throw new Error(res.message || 'Google authentication failed');
  },

  async loginWithGoogleCredential(jwtCredential) {
    const res = await this.request('/api/auth/google', 'POST', {
      credential: jwtCredential
    });
    if (res.success && res.user) {
      this.setCurrentUser(res.user);
      return res.user;
    }
    throw new Error(res.message || 'Google authentication failed');
  },

  requireAuth(allowedRoles = []) {
    const user = this.getCurrentUser();
    if (!user) {
      window.location.href = '/login';
      return false;
    }

    let isPermitted = false;
    if (allowedRoles.length === 0 || user.role === 'admin') {
      isPermitted = true;
    } else if (allowedRoles.includes(user.role)) {
      isPermitted = true;
    } else if (allowedRoles.includes('marketing') && user.role.startsWith('marketing')) {
      isPermitted = true;
    }

    if (!isPermitted) {
      document.body.innerHTML = `
        <div style="display: flex; min-height: 100vh; align-items: center; justify-content: center; background: #f8fafc; padding: 2rem; font-family: system-ui, sans-serif;">
          <div style="background: white; border: 1px solid #fee2e2; border-radius: 14px; padding: 2.5rem; max-width: 480px; text-align: center; box-shadow: 0 10px 25px -5px rgba(0,0,0,0.1);">
            <div style="font-size: 3rem; margin-bottom: 0.75rem;">🚫</div>
            <h2 style="color: #b91c1c; font-size: 1.35rem; margin-bottom: 0.75rem;">Access Restricted</h2>
            <p style="color: #64748b; font-size: 0.95rem; margin-bottom: 1.5rem; line-height: 1.5;">
              You do not have permission to access this portal.<br>
              Logged in as: <strong>${this.escapeHtml(user.name || user.email)}</strong> (${this.formatRoleName(user.role)})
            </p>
            <div style="display: flex; gap: 0.75rem; justify-content: center;">
              <button onclick="API.redirectToRolePortal('${user.role}')" style="background: #2563eb; color: white; border: none; padding: 0.65rem 1.25rem; border-radius: 8px; font-weight: 700; cursor: pointer;">
                Go to My Portal →
              </button>
              <button onclick="API.logout()" style="background: #f1f5f9; color: #334155; border: 1px solid #cbd5e1; padding: 0.65rem 1.25rem; border-radius: 8px; font-weight: 600; cursor: pointer;">
                Sign Out
              </button>
            </div>
          </div>
        </div>
      `;
      return false;
    }

    const nameEl = document.getElementById('header-user-name');
    const emailEl = document.getElementById('header-user-email');
    const roleEl = document.getElementById('header-user-role');
    const avatarEl = document.getElementById('header-user-avatar');
    if (nameEl) nameEl.innerText = user.name || user.email.split('@')[0];
    if (emailEl) emailEl.innerText = user.email || '';
    if (roleEl) roleEl.innerText = this.formatRoleName(user.role).toUpperCase();
    if (avatarEl) avatarEl.innerText = (user.name || user.email).charAt(0).toUpperCase();

    return true;
  },

  formatRoleName(role) {
    if (role === 'admin') return 'Administrator';
    if (role === 'developer') return 'Engineering Specialist';
    return 'Marketing Team';
  },

  formatResponsibilities(user) {
    if (!user) return 'Marketing Executive';
    if (user.role === 'admin') return 'System Administrator';
    if (user.role === 'developer') return 'Software Engineering';
    if (user.responsibilities && Array.isArray(user.responsibilities) && user.responsibilities.length > 0) {
      return user.responsibilities.join(', ');
    }
    return user.assignedResponsibility || 'Marketing Executive';
  },

  redirectToRolePortal(role) {
    if (role === 'admin') {
      window.location.href = '/admin';
    } else if (role === 'developer') {
      window.location.href = '/developer';
    } else {
      window.location.href = '/marketing';
    }
  },

  logout() {
    this.setCurrentUser(null);
    window.location.href = '/login';
  },

  // -------------------------------------------------------------
  // CRITICAL PRIVACY RULE: Hide Developer Details from Marketing
  // -------------------------------------------------------------
  formatDeveloperName(devName) {
    const user = this.getCurrentUser();
    if (!devName) return 'Unassigned';
    if (user && user.role !== 'admin') {
      return 'Engineering Team Assigned';
    }
    return devName;
  },

  // -------------------------------------------------------------
  // Currency, GST & Commission
  // -------------------------------------------------------------
  formatCurrency(amount, currency = 'INR') {
    const num = Math.round(Number(amount) || 0);
    if (currency === 'USD') return `$${num.toLocaleString()}`;
    return `₹${num.toLocaleString()}`;
  },

  calculateGST(subtotalAmount) {
    const subtotal = Math.round(Number(subtotalAmount) || 0);
    const gstRate = 18;
    const gstAmount = Math.round(subtotal * 0.18);
    const totalAmount = subtotal + gstAmount;
    return {
      subtotal,
      gstRate,
      gstAmount,
      totalAmount
    };
  },

  calculateCommission(subtotalPrice, currency = 'INR') {
    const slabs = currency === 'USD' ? (this.state.commissionSlabsUSD || []) : (this.state.commissionSlabsINR || []);
    const evalPrice = Number(subtotalPrice) || 0;

    let matchedSlab = null;
    for (const slab of slabs) {
      if (evalPrice >= slab.minPrice && evalPrice <= slab.maxPrice) {
        matchedSlab = slab;
        break;
      }
    }

    let rate = matchedSlab ? slab.rate : 7.0;
    if (rate > 10.0) rate = 10.0; // Strictly capped at 10%
    if (rate < 0) rate = 0;

    const commissionAmount = Math.round((evalPrice * rate) / 100);
    return {
      rate,
      commissionAmount,
      slabTitle: matchedSlab ? matchedSlab.title : 'Standard Slab',
      formattedCommission: this.formatCurrency(commissionAmount, currency)
    };
  },

  // -------------------------------------------------------------
  // Quotation Lifecycle & Status Badges
  // -------------------------------------------------------------
  normalizeQuotationStatus(status) {
    if (!status) return 'Draft';
    if (status === 'Quotation Generated') return 'Generated';
    return status;
  },

  getLifecycleBadgeClass(status) {
    const norm = this.normalizeQuotationStatus(status);
    switch (norm) {
      case 'Draft':
        return 'badge-lifecycle-draft';
      case 'Generated':
        return 'badge-lifecycle-generated';
      case 'Sent to Customer':
        return 'badge-lifecycle-sent';
      case 'Accepted':
        return 'badge-lifecycle-accepted';
      case 'Rejected':
        return 'badge-lifecycle-rejected';
      default:
        return 'badge-lifecycle-draft';
    }
  },

  getStageIndex(status) {
    const idx = this.PROJECT_STAGES.indexOf(status);
    return idx >= 0 ? idx : 0;
  },

  getStatusBadgeClass(status) {
    switch (status) {
      case 'Project Completed':
      case 'Completed':
      case 'Payment Verified':
      case 'Approved':
        return 'pill-success';
      case 'Final Website Submitted':
      case 'Testing Website Submitted':
      case 'Admin Review':
        return 'pill-primary';
      case 'Changes Requested':
      case 'Payment Rejected':
        return 'pill-danger';
      case 'Changes In Progress':
      case 'Frontend Development':
      case 'Backend Development':
      case 'Development Started':
      case 'Testing':
        return 'pill-warning';
      case 'Payment Proof Uploaded':
      case 'Verification Pending':
      case 'Payment Pending':
        return 'pill-info';
      default:
        return 'pill-secondary';
    }
  },

  getPaymentBadgeClass(status) {
    switch (status) {
      case 'Payment Verified':
        return 'pill-success';
      case 'Payment Proof Uploaded':
      case 'Verification Pending':
        return 'pill-info';
      case 'Partially Paid':
        return 'pill-warning';
      case 'Payment Rejected':
        return 'pill-danger';
      default:
        return 'pill-secondary';
    }
  },

  // -------------------------------------------------------------
  // Supported Document Upload Helpers (.docx, .pdf, .zip <= 500 KB)
  // -------------------------------------------------------------
  async uploadRequirementDocument(quotationId, file, uploadedBy = '') {
    if (!file) throw new Error('No document file selected');
    const ext = file.name.split('.').pop().toLowerCase();
    if (!['docx', 'pdf', 'zip'].includes(ext)) {
      throw new Error('Unsupported format. Allowed file types: .docx, .pdf, .zip');
    }
    if (file.size > 500 * 1024) {
      throw new Error(`Document exceeds 500 KB limit (Current: ${Math.round(file.size / 1024)} KB)`);
    }

    const formData = new FormData();
    formData.append('file', file);
    formData.append('uploadedBy', uploadedBy || (this.getCurrentUser()?.name || 'Marketing Team'));

    const user = this.getCurrentUser();
    const headers = {};
    if (user) {
      headers['X-User-Role'] = user.role;
      headers['X-User-Id'] = user.id;
      headers['X-User-Name'] = user.name || user.email;
    }

    const res = await fetch(`/api/quotations/${quotationId}/documents`, {
      method: 'POST',
      headers,
      body: formData
    });

    const json = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(json.message || 'Requirements document upload failed');
    }
    return json;
  },

  async uploadChangeRequestDocument(projectId, file, title, description, priority = 'Medium') {
    const formData = new FormData();
    if (file) {
      const ext = file.name.split('.').pop().toLowerCase();
      if (!['docx', 'pdf', 'zip'].includes(ext)) {
        throw new Error('Unsupported document format. Allowed: .docx, .pdf, .zip');
      }
      if (file.size > 500 * 1024) {
        throw new Error(`File exceeds 500 KB limit (Current: ${Math.round(file.size / 1024)} KB)`);
      }
      formData.append('file', file);
    }
    formData.append('title', title || 'Change Request');
    formData.append('description', description || '');
    formData.append('priority', priority);
    formData.append('requestedBy', this.getCurrentUser()?.name || 'Marketing Executive');

    const user = this.getCurrentUser();
    const headers = {};
    if (user) {
      headers['X-User-Role'] = user.role;
      headers['X-User-Id'] = user.id;
      headers['X-User-Name'] = user.name || user.email;
    }

    const res = await fetch(`/api/projects/${projectId}/change-requests`, {
      method: 'POST',
      headers,
      body: formData
    });

    const json = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(json.message || 'Failed to submit change request');
    }
    return json;
  },

  async uploadPaymentProof(projectId, file, metadata = {}) {
    if (!file) throw new Error('No payment screenshot file selected');
    const ext = file.name.split('.').pop().toLowerCase();
    if (!['jpg', 'jpeg', 'png', 'pdf'].includes(ext)) {
      throw new Error('Only JPG, JPEG, PNG, and PDF files are accepted');
    }
    if (file.size > 5 * 1024 * 1024) {
      throw new Error(`Payment screenshot exceeds 5 MB limit (Current size: ${Math.round(file.size / (1024 * 1024))} MB)`);
    }

    const formData = new FormData();
    formData.append('file', file);
    formData.append('uploadedBy', metadata.uploadedBy || (this.getCurrentUser()?.name || 'Administrator'));
    if (metadata.amountPaid) formData.append('amountPaid', metadata.amountPaid);
    if (metadata.method) formData.append('method', metadata.method);
    if (metadata.refNumber) formData.append('refNumber', metadata.refNumber);
    if (metadata.notes) formData.append('notes', metadata.notes);

    const user = this.getCurrentUser();
    const headers = {};
    if (user) {
      headers['X-User-Role'] = user.role;
      headers['X-User-Id'] = user.id;
      headers['X-User-Name'] = user.name || user.email;
    }

    const res = await fetch(`/api/projects/${projectId}/payment-proof`, {
      method: 'POST',
      headers,
      body: formData
    });

    const json = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(json.message || 'Payment proof upload failed');
    }
    return json;
  },

  async uploadSignoffDocument(projectId, file) {
    if (!file) throw new Error('No sign-off document file selected');
    const ext = file.name.split('.').pop().toLowerCase();
    if (!['pdf', 'docx'].includes(ext)) {
      throw new Error('Final sign-off document must be in .pdf or .docx format');
    }
    if (file.size > 5 * 1024 * 1024) {
      throw new Error(`Sign-off document exceeds 5 MB limit`);
    }

    const formData = new FormData();
    formData.append('file', file);
    formData.append('verifiedBy', this.getCurrentUser()?.name || 'Administrator');

    const user = this.getCurrentUser();
    const headers = {};
    if (user) {
      headers['X-User-Role'] = user.role;
      headers['X-User-Id'] = user.id;
      headers['X-User-Name'] = user.name || user.email;
    }

    const res = await fetch(`/api/projects/${projectId}/signoff-document`, {
      method: 'POST',
      headers,
      body: formData
    });

    const json = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(json.message || 'Sign-off document upload failed');
    }
    return json;
  },

  // -------------------------------------------------------------
  // UI Helpers
  // -------------------------------------------------------------
  showToast(msg) {
    let c = document.getElementById('toast-container');
    if (!c) {
      c = document.createElement('div');
      c.id = 'toast-container';
      document.body.appendChild(c);
    }
    const t = document.createElement('div');
    t.className = 'toast';
    t.innerHTML = `<span>✓</span><span>${this.escapeHtml(msg)}</span>`;
    c.appendChild(t);
    setTimeout(() => {
      t.style.opacity = '0';
      t.style.transform = 'translateY(10px)';
      t.style.transition = 'all 0.2s ease';
      setTimeout(() => t.remove(), 250);
    }, 2800);
  },

  escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  },

  formatBytes(bytesVal) {
    if (bytesVal === 0 || !bytesVal) return '0.0 B';
    const k = 1024;
    const sizes = ['B', 'KiB', 'MiB', 'GiB', 'TiB'];
    const i = Math.floor(Math.log(bytesVal) / Math.log(k));
    return parseFloat((bytesVal / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  },

  renderHeaderUser(defaultRole = 'USER') {
    const user = this.getCurrentUser();
    const avatarEl = document.getElementById('header-user-avatar');
    const nameEl = document.getElementById('header-user-name');
    const emailEl = document.getElementById('header-user-email');
    const roleEl = document.getElementById('header-user-role');

    if (user) {
      if (nameEl) nameEl.innerText = user.name || user.email.split('@')[0];
      if (emailEl) emailEl.innerText = user.email || '';
      if (roleEl) roleEl.innerText = (user.role || defaultRole || 'USER').toUpperCase();
      if (avatarEl) {
        const initial = (user.name || user.email || 'U').charAt(0).toUpperCase();
        avatarEl.innerText = initial;
      }
    } else {
      if (emailEl) emailEl.innerText = 'user@aivontraa.com';
    }
  },

  toggleMobileSidebar() {
    const sidebar = document.querySelector('.sidebar');
    const backdrop = document.querySelector('.sidebar-backdrop');
    if (sidebar) sidebar.classList.toggle('open');
    if (backdrop) backdrop.classList.toggle('active');
  },

  closeMobileSidebar() {
    const sidebar = document.querySelector('.sidebar');
    const backdrop = document.querySelector('.sidebar-backdrop');
    if (sidebar) sidebar.classList.remove('open');
    if (backdrop) backdrop.classList.remove('active');
  },

  openModal(id) {
    const el = document.getElementById(id);
    if (el) el.classList.add('open');
  },

  closeModal(id) {
    const el = document.getElementById(id);
    if (el) el.classList.remove('open');
  },

  // -----------------------------------------------------------
  // ENTERPRISE SHARDED DATABASE MANAGEMENT
  // -----------------------------------------------------------
  async getDatabaseStats() {
    return this.request('/database/stats');
  },

  async rotateDatabaseShard(module, reason) {
    return this.request('/database/rotate', {
      method: 'POST',
      body: JSON.stringify({ module, reason })
    });
  },

  async runDatabaseIntegrityCheck() {
    return this.request('/database/integrity-check', {
      method: 'POST'
    });
  },

  async optimizeDatabases() {
    return this.request('/database/optimize', {
      method: 'POST'
    });
  },

  async createDatabaseBackup(backupName) {
    return this.request('/database/backup', {
      method: 'POST',
      body: JSON.stringify({ backupName })
    });
  },

  async getDatabaseBackups() {
    return this.request('/database/backups');
  },

  async getDatabaseAuditLogs(limit = 100) {
    return this.request(`/database/audit-logs?limit=${limit}`);
  },

  async simulateDatabaseGrowth(module = 'customers', count = 25) {
    return this.request('/database/simulate-growth', {
      method: 'POST',
      body: JSON.stringify({ module, count })
    });
  }
};

document.addEventListener('DOMContentLoaded', () => {
  API.renderHeaderUser();

  document.querySelectorAll('.modal-backdrop').forEach(backdrop => {
    backdrop.addEventListener('click', function(e) {
      if (e.target === this) {
        this.classList.remove('open');
      }
    });
  });
});
