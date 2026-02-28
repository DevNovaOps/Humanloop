/*
   HumanLoop — Core Logic, RBAC & State Management
   Version: 4.0 (Role-Based Access Control)
*/

document.addEventListener('DOMContentLoaded', () => {
    ThemeManager.init();
    AuthManager.init();
    App.init();
});

/* ═══════════════════════════════════════════
   ROLE-BASED ACCESS CONTROL CONFIG
   ═══════════════════════════════════════════ */
const RBAC = {
    roles: ['innovator', 'ngo', 'beneficiary', 'admin'],

    roleLabels: {
        innovator: 'Innovator',
        ngo: 'NGO Partner',
        beneficiary: 'Beneficiary',
        admin: 'Administrator'
    },

    roleIcons: {
        innovator: 'fa-lightbulb',
        ngo: 'fa-building-ngo',
        beneficiary: 'fa-user-check',
        admin: 'fa-shield-halved'
    },

    roleColors: {
        innovator: '#1A56DB',
        ngo: '#0D9488',
        beneficiary: '#ea580c',
        admin: '#7c3aed'
    },

    /*
     * FEATURE-LEVEL PERMISSIONS (from photo)
     * ┌──────────────┬─────────────┬───────────┬──────┬───────────┬───────┐
     * │ Feature      │ Beneficiary │ NGO  │ Innovator │ Admin │
     * ├──────────────┼─────────────┼──────┼───────────┼───────┤
     * │ Create Pilot │     ✗       │  ✓   │     ✓     │   ✓   │
     * │ View Budget  │     ✗       │ Ltd  │     ✓     │   ✓   │
     * │ Export Data  │     ✗       │  ✗   │     ✗     │   ✓   │
     * └──────────────┴─────────────┴──────┴───────────┴───────┘
     */
    featurePermissions: {
        createPilot: { innovator: true, ngo: true, beneficiary: false, admin: false },
        viewBudget: { innovator: true, ngo: 'limited', beneficiary: false, admin: true },
        exportData: { innovator: false, ngo: false, beneficiary: false, admin: true }
    },

    canUseFeature(feature, role) {
        const perms = this.featurePermissions[feature];
        if (!perms) return false;
        return perms[role] === true || perms[role] === 'limited';
    },

    isFeatureLimited(feature, role) {
        const perms = this.featurePermissions[feature];
        return perms && perms[role] === 'limited';
    },

    /* Pages accessible by each role */
    permissions: {
        innovator: ['dashboard', 'planner', 'pilot', 'expenses', 'settings'],
        ngo: ['dashboard-ngo', 'planner', 'pilot', 'expenses', 'settings', 'team'],
        beneficiary: ['dashboard-beneficiary', 'settings', 'feedback', 'explore-programs'],
        admin: ['dashboard-admin', 'dashboard', 'pilot', 'expenses', 'settings', 'team']
    },

    /* Sidebar items per role — tKey is the translation key, label is the English fallback */
    sidebarItems: {
        innovator: [
            { href: '/dashboard/', icon: 'fa-chart-pie', tKey: 'overview', label: 'Overview' },
            { href: '/planner/', icon: 'fa-calendar-plus', tKey: 'plan_new_pilot', label: 'Create Pilot' },
            { href: '/pilot/', icon: 'fa-bars-progress', tKey: 'active_pilots', label: 'Active Pilots' },
            { href: '/expenses/', icon: 'fa-wallet', label: 'Budget' },
            { divider: true },
            { href: '/settings/', icon: 'fa-gear', tKey: 'settings', label: 'Settings' }
        ],
        ngo: [
            { href: '/dashboard-ngo/', icon: 'fa-chart-pie', tKey: 'overview', label: 'Overview' },
            { href: '/pilot/', icon: 'fa-bars-progress', tKey: 'active_pilots', label: 'Assigned Pilots' },
            { divider: true },
            { href: '/settings/', icon: 'fa-gear', tKey: 'settings', label: 'Settings' },
            { href: '/team/', icon: 'fa-users', tKey: 'team', label: 'Team Members' }
        ],
        beneficiary: [
            { href: '/dashboard-beneficiary/', icon: 'fa-home', tKey: 'my_programs', label: 'My Programs' },
            { href: '/explore-programs/', icon: 'fa-compass', tKey: 'explore_programs', label: 'Explore Programs' },
            { href: '/feedback/', icon: 'fa-pen-to-square', tKey: 'write_feedback', label: 'Write Feedback' },
            { divider: true },
            { href: '/settings/', icon: 'fa-gear', tKey: 'settings', label: 'Settings' }
        ],
        admin: [
            { href: '/dashboard-admin/', icon: 'fa-gauge-high', label: 'System Overview' },
            { href: '/dashboard/', icon: 'fa-chart-pie', label: 'Impact Dashboard' },
            { href: '/pilot/', icon: 'fa-bars-progress', label: 'Pilots' },
            { divider: true },
            { href: '/settings/', icon: 'fa-gear', tKey: 'settings', label: 'Settings' }
        ]
    },

    /* Public pages (no auth needed) */
    publicPages: ['', 'login', 'register', 'forgot-password', 'verify-otp', 'about', 'contact', 'partners', '403'],

    isPublicPage(page) {
        return this.publicPages.includes(page);
    },

    canAccess(role, page) {
        if (this.isPublicPage(page)) return true;
        if (!role) return false;
        if (role === 'admin') return true;
        return (this.permissions[role] || []).includes(page);
    },

    getDashboardForRole(role) {
        const map = {
            innovator: '/dashboard/',
            ngo: '/dashboard-ngo/',
            beneficiary: '/dashboard-beneficiary/',
            admin: '/dashboard-admin/'
        };
        return map[role] || '/login/';
    }
};

/* ═══════════════════════════════════════════
   THEME MANAGER
   ═══════════════════════════════════════════ */
const ThemeManager = {
    storageKey: 'civicpilot_theme',
    init() {
        const saved = localStorage.getItem(this.storageKey) || 'system';
        this.setTheme(saved);
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
            if (this.getTheme() === 'system') this.setTheme('system');
        });
        document.querySelectorAll('[data-theme-set]').forEach(btn => {
            btn.addEventListener('click', () => this.setTheme(btn.dataset.themeSet));
        });
    },
    getTheme() { return localStorage.getItem(this.storageKey) || 'system'; },
    setTheme(mode) {
        document.documentElement.setAttribute('data-theme', mode);
        localStorage.setItem(this.storageKey, mode);
        this.updateToggleUI(mode);
    },
    updateToggleUI(mode) {
        document.querySelectorAll('[data-theme-set]').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.themeSet === mode);
        });
    }
};

/* ═══════════════════════════════════════════
   AUTH MANAGER
   ═══════════════════════════════════════════ */
const AuthManager = {
    storageKey: 'humanloop_user',

    init() {
        this.enforceRouteProtection();
        this.renderRoleBadge();
        this.renderDynamicSidebar();
        this.renderNotificationBell();
    },

    getUser() {
        // Prefer localStorage, but fall back to server-injected window.__USER__
        const fromStorage = JSON.parse(localStorage.getItem(this.storageKey));
        if (fromStorage) return fromStorage;
        if (window.__USER__) {
            // Sync server user to localStorage so JS RBAC works
            localStorage.setItem(this.storageKey, JSON.stringify(window.__USER__));
            return window.__USER__;
        }
        return null;
    },

    login(email, role, serverUser) {
        // Use real server-returned user data if available
        const user = serverUser ? {
            id: serverUser.id,
            email: serverUser.email,
            name: serverUser.name,
            role: serverUser.role,
            organization: serverUser.organization,
            verified: serverUser.verified,
            language: serverUser.language,
            loginTime: new Date().toISOString()
        } : {
            email,
            role,
            name: email.split('@')[0].replace(/[._]/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
            loginTime: new Date().toISOString(),
            verified: role === 'ngo' ? true : undefined
        };
        localStorage.setItem(this.storageKey, JSON.stringify(user));
        return user;
    },

    async logout() {
        // Call Django backend to clear the server session
        try {
            await fetch('/api/logout/', { method: 'POST', headers: { 'Content-Type': 'application/json' } });
        } catch (e) { /* ignore network errors */ }
        localStorage.removeItem(this.storageKey);
        window.location.href = '/login/';
    },

    isLoggedIn() {
        return !!this.getUser();
    },

    enforceRouteProtection() {
        // Extract the meaningful path segment, e.g. '/dashboard/' -> 'dashboard'
        const parts = window.location.pathname.replace(/^\/|\/$/, '').split('/');
        const page = parts[parts.length - 1] || '';
        if (RBAC.isPublicPage(page)) return;
        const user = this.getUser();
        if (!user) { window.location.href = '/login/'; return; }
        if (!RBAC.canAccess(user.role, page)) { window.location.href = '/403/'; return; }
    },

    renderRoleBadge() {
        const user = this.getUser();
        if (!user) return;

        const profileEl = document.querySelector('.nav-user-profile');
        if (!profileEl) return;

        const nameSpan = profileEl.querySelector('.text-medium-sm');
        if (nameSpan) {
            nameSpan.innerHTML = `${user.name} <span class="role-badge" style="background:${RBAC.roleColors[user.role]}; color:#fff; font-size:0.65rem; padding:0.15rem 0.5rem; border-radius:999px; margin-left:0.35rem; font-weight:600; text-transform:uppercase; letter-spacing:0.03em;">${RBAC.roleLabels[user.role]}${user.role === 'ngo' && user.verified ? ' <i class="fa-solid fa-circle-check" style="font-size:0.6rem;"></i>' : ''}</span>`;
        }

        // Make profile clickable with dropdown
        profileEl.style.cursor = 'pointer';
        profileEl.style.position = 'relative';

        // Create dropdown menu
        const dropdown = document.createElement('div');
        dropdown.className = 'profile-dropdown';
        dropdown.innerHTML = `
            <div class="profile-dropdown-header">
                <div class="profile-dropdown-avatar"><i class="fa-solid fa-user"></i></div>
                <div>
                    <div class="profile-dropdown-name">${user.name}</div>
                    <div class="profile-dropdown-email">${user.email}</div>
                </div>
            </div>
            <div class="profile-dropdown-divider"></div>
            <a href="/settings/" class="profile-dropdown-item">
                <i class="fa-solid fa-user-circle"></i> View Profile
            </a>
            <a href="/settings/" class="profile-dropdown-item">
                <i class="fa-solid fa-gear"></i> Settings
            </a>
            <div class="profile-dropdown-divider"></div>
            <a href="#" class="profile-dropdown-item profile-dropdown-logout" id="profile-logout-btn">
                <i class="fa-solid fa-right-from-bracket"></i> Log Out
            </a>
        `;
        profileEl.appendChild(dropdown);

        // Toggle dropdown on click
        profileEl.addEventListener('click', (e) => {
            e.stopPropagation();
            // Close all other popups first
            const notifPanel = document.getElementById('notif-panel');
            if (notifPanel) notifPanel.remove();
            dropdown.classList.toggle('visible');
        });

        // Close on click outside
        document.addEventListener('click', (e) => {
            if (!profileEl.contains(e.target)) {
                dropdown.classList.remove('visible');
            }
        });

        // Logout handler
        dropdown.querySelector('#profile-logout-btn').addEventListener('click', (e) => {
            e.preventDefault();
            AuthManager.logout();
        });

        // Legacy logout button support
        const logoutBtn = profileEl.querySelector('.btn-logout');
        if (logoutBtn) {
            logoutBtn.href = '#';
            logoutBtn.addEventListener('click', (e) => { e.preventDefault(); AuthManager.logout(); });
        }
    },

    renderDynamicSidebar() {
        const user = this.getUser();
        const sidebarNav = document.querySelector('.sidebar-nav');
        if (!user || !sidebarNav) return;

        const T = window.__TRANSLATIONS__ || {};
        const items = RBAC.sidebarItems[user.role] || [];
        const currentPath = window.location.pathname;

        // Also translate the sidebar section title
        const titleEl = document.querySelector('.sidebar-section-title');
        if (titleEl) titleEl.textContent = T.main_menu || T.my_space || titleEl.textContent;

        sidebarNav.innerHTML = items.map(item => {
            if (item.divider) return '<hr class="sidebar-divider-hr">';
            const isActive = currentPath === item.href ? ' class="active"' : '';
            const displayLabel = (item.tKey && T[item.tKey]) ? T[item.tKey] : item.label;
            return `<a href="${item.href}"${isActive}><i class="fa-solid ${item.icon}"></i> ${displayLabel}</a>`;
        }).join('');
    },

    renderNotificationBell() {
        const user = this.getUser();
        if (!user) return;

        // Don't show on auth or home pages
        const parts = window.location.pathname.replace(/^\/|\/$/, '').split('/');
        const page = parts[parts.length - 1] || '';
        const noNotifPages = ['', 'login', 'register', 'forgot-password', 'verify-otp'];
        if (noNotifPages.includes(page)) return;

        const navActions = document.querySelector('.nav-actions');
        if (!navActions || navActions.querySelector('.notification-bell')) return;

        const bell = document.createElement('div');
        bell.className = 'notification-bell';
        bell.style.cssText = 'position:relative;cursor:pointer;margin-right:0.75rem;';
        bell.innerHTML = `<i class="fa-solid fa-bell" style="font-size:1.1rem;color:var(--text-secondary);transition:color 0.2s;"></i><span class="notif-count" style="position:absolute;top:-6px;right:-8px;background:#ef4444;color:#fff;font-size:0.6rem;font-weight:700;width:16px;height:16px;border-radius:50%;display:flex;align-items:center;justify-content:center;">3</span>`;

        const themeToggle = navActions.querySelector('.theme-toggle');
        if (themeToggle) themeToggle.after(bell);

        // Pre-fetch notifications to update the badge count immediately
        NotificationCenter.fetchNotifications();

        bell.addEventListener('click', (e) => {
            e.stopPropagation();
            // Close all other popups first
            const profileDropdown = document.querySelector('.profile-dropdown.visible');
            if (profileDropdown) profileDropdown.classList.remove('visible');
            NotificationCenter.toggle(bell);
        });
    }
};

/* ═══════════════════════════════════════════
   NOTIFICATION CENTER — Real API data
   ═══════════════════════════════════════════ */
const NotificationCenter = {
    _cache: null,
    _unread: 0,

    async fetchNotifications() {
        if (this._cache) return this._cache;
        try {
            const res = await fetch('/api/notifications/');
            if (!res.ok) throw new Error('not ok');
            const data = await res.json();
            this._cache = data.notifications || [];
            this._unread = data.unread_count || 0;
            // Update bell badge with real count
            const badge = document.querySelector('.notif-count');
            if (badge) {
                badge.textContent = this._unread > 9 ? '9+' : (this._unread || '');
                badge.style.display = this._unread > 0 ? 'flex' : 'none';
            }
        } catch (e) {
            this._cache = [];
        }
        return this._cache;
    },

    async toggle(bellEl) {
        let panel = document.getElementById('notif-panel');
        if (panel) { panel.remove(); return; }

        const notifs = await this.fetchNotifications();

        panel = document.createElement('div');
        panel.id = 'notif-panel';
        const navbar = document.querySelector('.navbar');
        const navbarHeight = navbar ? navbar.getBoundingClientRect().bottom : 56;
        const bellRect = bellEl ? bellEl.getBoundingClientRect() : null;
        const rightPos = bellRect ? Math.max(16, window.innerWidth - bellRect.right + (bellRect.width / 2) - 150) : 80;

        panel.style.cssText = `position:fixed;top:${navbarHeight + 6}px;right:${rightPos}px;width:300px;max-width:calc(100vw - 24px);max-height:380px;overflow-y:auto;background:var(--bg-surface);border:1px solid var(--border-color);border-radius:16px;box-shadow:0 10px 40px rgba(0,0,0,0.12),0 2px 10px rgba(0,0,0,0.06);z-index:9999;padding:0.85rem;animation:notifSlideIn 0.2s ease;`;

        if (!document.getElementById('notif-anim-style')) {
            const style = document.createElement('style');
            style.id = 'notif-anim-style';
            style.textContent = '@keyframes notifSlideIn{from{opacity:0;transform:translateY(-8px);}to{opacity:1;transform:translateY(0);}}';
            document.head.appendChild(style);
        }

        const timeAgo = (isoStr) => {
            const diff = Math.floor((Date.now() - new Date(isoStr)) / 1000);
            if (diff < 60) return diff + 's ago';
            if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
            if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
            return Math.floor(diff / 86400) + 'd ago';
        };

        if (notifs.length === 0) {
            panel.innerHTML = `<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.6rem;padding-bottom:0.5rem;border-bottom:1px solid var(--border-color);"><h4 style="margin:0;color:var(--text-primary);font-size:0.9rem;">Notifications</h4><button onclick="document.getElementById('notif-panel').remove()" style="background:none;border:none;cursor:pointer;color:var(--text-muted);font-size:0.9rem;width:28px;height:28px;border-radius:50%;display:flex;align-items:center;justify-content:center;"><i class="fa-solid fa-xmark"></i></button></div><p style="color:var(--text-muted);font-size:0.85rem;text-align:center;padding:1rem 0;">No notifications yet.</p>`;
        } else {
            panel.innerHTML = `<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.6rem;padding-bottom:0.5rem;border-bottom:1px solid var(--border-color);"><h4 style="margin:0;color:var(--text-primary);font-size:0.9rem;">Notifications</h4><button onclick="document.getElementById('notif-panel').remove()" style="background:none;border:none;cursor:pointer;color:var(--text-muted);font-size:0.9rem;width:28px;height:28px;border-radius:50%;display:flex;align-items:center;justify-content:center;"><i class="fa-solid fa-xmark"></i></button></div>${notifs.map(n => `<div style="display:flex;gap:0.6rem;padding:0.6rem;border-radius:10px;margin-bottom:0.35rem;background:${n.is_read ? 'var(--bg-secondary)' : 'rgba(26,86,219,0.06)'};border:1px solid ${n.is_read ? 'var(--border-color)' : 'rgba(26,86,219,0.15)'};transition:background 0.15s;"><i class="fa-solid ${n.icon || 'fa-bell'}" style="color:#1A56DB;margin-top:2px;font-size:0.8rem;"></i><div><div style="font-size:0.8rem;color:var(--text-primary);line-height:1.35;font-weight:${n.is_read ? '400' : '600'};"><strong>${n.title}</strong><br>${n.message}</div><div style="font-size:0.65rem;color:var(--text-muted);margin-top:0.2rem;">${timeAgo(n.created_at)}</div></div></div>`).join('')}`;
        }

        document.body.appendChild(panel);
        document.addEventListener('click', function handler(e) {
            if (!panel.contains(e.target) && !e.target.closest('.notification-bell')) {
                panel.remove();
                document.removeEventListener('click', handler);
            }
        });
    }
};

/* ═══════════════════════════════════════════
   APP — Core Logic
   ═══════════════════════════════════════════ */
const App = {
    init() {
        this.handleMobileNav();
        this.handleGlobalUI();
        if (document.getElementById('chart-container')) DashboardManager.init();
        if (document.querySelector('form[action="pilot.html"]')) PlannerManager.init();
        // PilotManager disabled — pilot.html uses its own API-based rendering
        // if (document.getElementById('pilot-tasks-list')) PilotManager.init();
        // ExpenseManager disabled — expenses.html uses Django server-side rendering
        // if (document.getElementById('expense-list')) ExpenseManager.init();
        if (document.getElementById('admin-users-table')) AdminManager.init();
        if (document.getElementById('ngo-assigned-pilots')) NgoManager.init();
        if (document.getElementById('beneficiary-programs')) BeneficiaryManager.init();
        this.enforceFeaturePermissions();
        this.enforceDateMinimums();
    },

    /* Prevent past dates on all date inputs (except DOB) */
    enforceDateMinimums() {
        const today = new Date().toISOString().split('T')[0];
        document.querySelectorAll('input[type="date"]').forEach(input => {
            // Skip date-of-birth fields
            if (input.id === 'dob' || input.name === 'dob') return;
            if (!input.min) input.min = today;
        });
    },

    handleMobileNav() {
        const toggle = document.querySelector('.mobile-toggle');
        const navLinks = document.querySelector('.nav-links');
        const sidebar = document.querySelector('.sidebar');
        if (!document.querySelector('.mobile-nav-overlay')) {
            const o = document.createElement('div'); o.className = 'mobile-nav-overlay';
            document.body.appendChild(o); o.addEventListener('click', () => this.closeAllMobileMenus());
        }
        if (sidebar && !document.querySelector('.sidebar-overlay')) {
            const o = document.createElement('div'); o.className = 'sidebar-overlay';
            document.body.appendChild(o); o.addEventListener('click', () => this.closeAllMobileMenus());
        }
        if (toggle) {
            toggle.addEventListener('click', () => {
                if (sidebar) {
                    const isOpen = sidebar.classList.contains('open');
                    this.closeAllMobileMenus();
                    if (!isOpen) { sidebar.classList.add('open'); const o = document.querySelector('.sidebar-overlay'); if (o) o.classList.add('active'); document.body.style.overflow = 'hidden'; }
                } else if (navLinks) {
                    const isActive = navLinks.classList.contains('active');
                    this.closeAllMobileMenus();
                    if (!isActive) { navLinks.classList.add('active'); const o = document.querySelector('.mobile-nav-overlay'); if (o) o.classList.add('active'); document.body.style.overflow = 'hidden'; }
                }
            });
        }
        window.addEventListener('resize', () => { if (window.innerWidth > 768) this.closeAllMobileMenus(); });
        document.addEventListener('keydown', (e) => { if (e.key === 'Escape') this.closeAllMobileMenus(); });
    },

    closeAllMobileMenus() {
        const navLinks = document.querySelector('.nav-links');
        const sidebar = document.querySelector('.sidebar');
        if (navLinks) navLinks.classList.remove('active');
        if (sidebar) sidebar.classList.remove('open');
        document.querySelectorAll('.mobile-nav-overlay,.sidebar-overlay').forEach(o => o.classList.remove('active'));
        document.body.style.overflow = '';
    },

    handleGlobalUI() {
        const parts = window.location.pathname.replace(/^\/|\/$/, '').split('/');
        const currentPath = parts[parts.length - 1] || '';
        document.querySelectorAll('.sidebar-nav a').forEach(link => {
            if (link.getAttribute('href') === currentPath) link.classList.add('active');
            link.addEventListener('click', () => { if (window.innerWidth <= 768) this.closeAllMobileMenus(); });
        });
    },

    enforceFeaturePermissions() {
        const user = AuthManager.getUser();
        if (!user) return;
        const role = user.role;

        // Hide "Create Pilot" links/buttons for roles without permission
        if (!RBAC.canUseFeature('createPilot', role)) {
            document.querySelectorAll('a[href="/planner/"]').forEach(el => {
                el.style.display = 'none';
            });
        }

        // Hide Budget/Expenses links for roles without permission
        if (!RBAC.canUseFeature('viewBudget', role)) {
            document.querySelectorAll('a[href*="/expenses/"], #manage-expenses-link').forEach(el => {
                el.style.display = 'none';
            });
            const budgetSection = document.querySelector('.budget-section');
            if (budgetSection) budgetSection.style.display = 'none';
        }

        // Show "Limited" badge for NGO budget access
        if (RBAC.isFeatureLimited('viewBudget', role)) {
            const budgetCards = document.querySelectorAll('#pilot-budget-total, #pilot-budget-spent');
            budgetCards.forEach(el => {
                const badge = document.createElement('span');
                badge.style.cssText = 'font-size:0.6rem;background:#ea580c;color:#fff;padding:0.1rem 0.4rem;border-radius:999px;margin-left:0.5rem;font-weight:600;text-transform:uppercase;';
                badge.textContent = 'Limited';
                el.parentElement.appendChild(badge);
            });
        }

        // Hide Export buttons for non-admin
        if (!RBAC.canUseFeature('exportData', role)) {
            document.querySelectorAll('#export-audit, [data-feature="export"]').forEach(el => {
                el.style.display = 'none';
            });
        }
    }
};

/* ═══════════════════════════════════════════
   STATE MANAGEMENT
   ═══════════════════════════════════════════ */
const StateStore = {
    getKey: () => 'civicPilot_data_v2',
    getData() {
        const defaults = {
            pilots: [], stats: { impactScore: 8.4, members: 124, budgetEfficiency: 94 },
            users: [
                { id: '1', name: 'Akshat Sharma', email: 'akshat@humanloop.org', role: 'innovator', status: 'active', joined: '2025-11-01' },
                { id: '2', name: 'GreenEarth Foundation', email: 'info@greenearth.org', role: 'ngo', status: 'active', verified: true, joined: '2025-10-15' },
                { id: '3', name: 'Priya Patel', email: 'priya@example.com', role: 'beneficiary', status: 'active', joined: '2025-12-01' },
                { id: '4', name: 'RuralAid India', email: 'contact@ruralaid.org', role: 'ngo', status: 'pending', verified: false, joined: '2026-01-10' },
                { id: '5', name: 'Rahul Dave', email: 'rahul@nss.edu', role: 'innovator', status: 'active', joined: '2025-09-20' }
            ],
            auditLog: [
                { action: 'User Login', user: 'akshat@humanloop.org', timestamp: '2026-02-14T10:00:00', details: 'Role: Innovator' },
                { action: 'Pilot Created', user: 'akshat@humanloop.org', timestamp: '2026-02-13T14:30:00', details: 'Education Drive — Rajasthan' },
                { action: 'NGO Verified', user: 'admin@humanloop.org', timestamp: '2026-02-12T09:15:00', details: 'GreenEarth Foundation approved' }
            ]
        };
        const saved = JSON.parse(localStorage.getItem(this.getKey()));
        if (!saved) return defaults;

        // Ensure new keys exist in saved data
        return {
            ...defaults, ...saved
        };
    },
    saveData(data) { localStorage.setItem(this.getKey(), JSON.stringify(data)); },
    addPilot(pilot) { const d = this.getData(); d.pilots.unshift(pilot); this.saveData(d); },
    updatePilotStatus(id, status) { const d = this.getData(); const p = d.pilots.find(x => x.id === id); if (p) { p.status = status; this.saveData(d); } },
    addExpense(pid, expense) { const d = this.getData(); const p = d.pilots.find(x => x.id === pid); if (p) { p.expenses = p.expenses || []; p.expenses.push(expense); this.saveData(d); } },
    deleteExpense(pid, i) { const d = this.getData(); const p = d.pilots.find(x => x.id === pid); if (p && p.expenses) { p.expenses.splice(i, 1); this.saveData(d); } },
    createUser(user) { const d = this.getData(); d.users.push(user); this.saveData(d); },
    updateUserOrganization(userId, orgId) {
        const d = this.getData();
        const u = d.users.find(x => x.id === userId);
        if (u) { u.organizationId = orgId; this.saveData(d); }
        // Also update current session user if it matches
        const currentUser = AuthManager.getUser();
        if (currentUser && currentUser.id === userId) {
            currentUser.organizationId = orgId;
            localStorage.setItem(AuthManager.storageKey, JSON.stringify(currentUser));
        }
    }
};

/* ═══════════════════════════════════════════
   UI UTILITIES
   ═══════════════════════════════════════════ */
const Utils = {
    showToast(msg, type = 'success') {
        const toast = document.createElement('div');
        toast.className = 'toast-notification show';
        const icon = type === 'success' ? 'circle-check' : 'circle-exclamation';
        const color = type === 'success' ? '#0D9488' : '#ef4444';
        toast.innerHTML = `<i class="fa-solid fa-${icon}" style="color: ${color}; font-size: 1.2rem;"></i> <strong>${type === 'success' ? 'Success' : 'Alert'}</strong> <span>${msg}</span>`;
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), 3000);
    },
    setLoading(btn, isLoading) {
        if (isLoading) { btn.dataset.originalText = btn.innerHTML; btn.innerHTML = 'Processing...'; btn.classList.add('btn-loading'); }
        else { btn.innerHTML = btn.dataset.originalText; btn.classList.remove('btn-loading'); }
    },
    confirmModal(title, message, onConfirm) {
        const overlay = document.createElement('div');
        overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.5);z-index:10000;display:flex;align-items:center;justify-content:center;';
        overlay.innerHTML = `<div style="background:var(--bg-surface);border-radius:16px;padding:2rem;max-width:400px;width:90%;border:1px solid var(--border-color);box-shadow:var(--shadow-lg);"><h3 style="margin-bottom:0.75rem;color:var(--text-primary);">${title}</h3><p style="color:var(--text-secondary);margin-bottom:1.5rem;font-size:0.9rem;">${message}</p><div style="display:flex;gap:0.75rem;justify-content:flex-end;"><button class="btn btn-secondary" onclick="this.closest('div[style]').parentElement.remove()">Cancel</button><button class="btn btn-primary" id="confirm-action-btn">Confirm</button></div></div>`;
        document.body.appendChild(overlay);
        overlay.querySelector('#confirm-action-btn').addEventListener('click', () => { onConfirm(); overlay.remove(); });
    }
};

/* ═══════════════════════════════════════════
   PAGE MANAGERS (Innovator)
   ═══════════════════════════════════════════ */
const DashboardManager = {
    init() { this.renderStats(); this.renderChart(); },
    renderStats() {
        const data = StateStore.getData();
        const set = (id, val) => { const el = document.getElementById(id); if (el) el.innerText = val; };
        set('stat-impact-score', `${data.stats.impactScore}/10`);
        set('stat-members', data.stats.members);
        const activePilots = data.pilots.filter(p => p.status === 'In Progress').length;
        set('stat-active-pilots', activePilots);
        const beneficiaries = data.pilots.reduce((s, p) => s + parseInt(p.beneficiaries || p.members || 0), 0);
        set('stat-beneficiaries', beneficiaries || '850+');
    },
    renderChart() {
        const container = document.getElementById('chart-container');
        if (!container) return;
        const data = [{ label: 'Jun', value: 40 }, { label: 'Jul', value: 65 }, { label: 'Aug', value: 55 }, { label: 'Sep', value: 85 }, { label: 'Oct', value: 70 }, { label: 'Nov', value: 95 }];
        container.innerHTML = '';
        data.forEach((item, i) => {
            const g = document.createElement('div');
            g.style.cssText = 'display:flex;flex-direction:column;align-items:center;flex:1;';
            g.innerHTML = `<div style="width:40px;height:0px;background:linear-gradient(180deg,#1A56DB,#0D9488);border-radius:4px 4px 0 0;transition:height 1s ease-out 0.2s;opacity:0.85;" id="bar-${i}"></div><div style="margin-top:10px;font-size:0.8rem;color:var(--text-muted);">${item.label}</div>`;
            container.appendChild(g);
            setTimeout(() => document.getElementById(`bar-${i}`).style.height = `${item.value * 2}px`, 100 + (i * 100));
        });
    }
};

const PlannerManager = {
    init() {
        const form = document.querySelector('form');
        if (form) form.addEventListener('submit', (e) => { e.preventDefault(); this.handleSearch(e.target); });
    },
    handleSearch(form) {
        const btn = form.querySelector('button');
        Utils.setLoading(btn, true);
        const fd = new FormData(form);
        const pilot = {
            id: Date.now().toString(), type: fd.get('activity_type'), location: fd.get('location'),
            date: fd.get('date'), budget: fd.get('budget'), members: fd.get('members'),
            status: 'In Progress', tasks: this.generateTasks(fd.get('activity_type')),
            aiSuggestion: this.getAISuggestion(fd.get('activity_type')), createdAt: new Date().toISOString()
        };
        setTimeout(() => { StateStore.addPilot(pilot); window.location.href = `/pilot/?id=${pilot.id}`; }, 1500);
    },
    generateTasks(type) {
        const common = ["Obtain Permissions", "Brief Team Members", "Arrange Logistics"];
        const spec = { education: ["Buy Stationery", "Print Worksheets", "Assign Mentors"], health: ["Confirm Doctors", "Buy Meds", "Setup Desk"], environment: ["Buy Saplings", "Get Tools", "Dig Pits"], awareness: ["Print Posters", "Rent Mic", "Prepare Script"] };
        return [...(spec[type] || []), ...common];
    },
    getAISuggestion(type) {
        const t = { education: "Visual aids increase retention by 40%.", health: "Check weather forecast for outdoor camps.", environment: "Soil aeration 2 days prior boosts survival.", awareness: "Evening hours see peak footfall here." };
        return t[type] || "Document everything for impact reports.";
    }
};

const PilotManager = {
    init() {
        const params = new URLSearchParams(window.location.search);
        const id = params.get('id');
        let pilot = id ? StateStore.getData().pilots.find(p => p.id === id) : StateStore.getData().pilots[0];
        if (!pilot) {
            const m = document.querySelector('main');
            if (m) m.innerHTML = `<div style="text-align:center;padding:4rem 2rem;"><i class="fa-solid fa-folder-open" style="font-size:3rem;color:var(--text-light);margin-bottom:1rem;display:block;"></i><h3>No Active Pilot Found</h3><p style="margin-bottom:1.5rem;">Start a new initiative to see details here.</p><a href="/planner/" class="btn btn-primary">Plan New Pilot</a></div>`;
            return;
        }
        this.renderPilot(pilot);
    },
    renderPilot(pilot) {
        const set = (id, val) => { const el = document.getElementById(id); if (el) el.innerText = val; };
        const labels = { education: 'Education Drive', health: 'Healthcare Camp', environment: 'Cleanliness Drive', awareness: 'Awareness Campaign' };
        set('pilot-title', pilot.title || `${labels[pilot.type] || 'Pilot'}: Phase 1`);
        set('pilot-location', pilot.location);
        set('pilot-budget-total', `₹${parseInt(pilot.budget).toLocaleString()}`);
        set('pilot-ai-suggestion', pilot.aiSuggestion);
        set('pilot-date', new Date(pilot.date).toLocaleDateString());
        const ml = document.getElementById('manage-expenses-link'); if (ml) ml.href = `/expenses/?id=${pilot.id}`;
        const expenses = pilot.expenses || [];
        const totalSpent = expenses.reduce((s, e) => s + parseInt(e.amount), 0);
        const totalBudget = parseInt(pilot.budget || 0);
        const pct = totalBudget === 0 ? 0 : Math.min(100, (totalSpent / totalBudget) * 100);
        const spentEl = document.getElementById('pilot-budget-spent'); if (spentEl) spentEl.innerText = `₹${totalSpent.toLocaleString()}`;
        const bar = document.getElementById('pilot-budget-bar'); if (bar) { bar.style.width = `${pct}%`; if (pct > 90) bar.style.background = '#ef4444'; }
        const list = document.querySelector('#pilot-tasks-list');
        if (list) {
            list.innerHTML = '';
            pilot.tasks.forEach(task => {
                list.innerHTML += `<label style="display:flex;gap:1rem;align-items:center;padding:1rem;border:1px solid var(--border-color);border-radius:8px;cursor:pointer;transition:all 0.2s;background:var(--bg-surface);" onclick="this.classList.toggle('completed');PilotManager.updateProgress()"><input type="checkbox" style="width:1.2rem;height:1.2rem;accent-color:#1A56DB;"><span style="color:var(--text-secondary);">${task}</span></label>`;
            });
            this.updateProgress();
        }
        const cb = document.querySelector('#complete-pilot-btn');
        if (cb) cb.addEventListener('click', (e) => {
            e.preventDefault();
            StateStore.updatePilotStatus(pilot.id, 'Completed');
            const d = StateStore.getData(); d.stats.impactScore = Math.min(10, parseFloat(d.stats.impactScore) + 0.5).toFixed(1); d.stats.members += parseInt(pilot.members || 0); StateStore.saveData(d);
            Utils.showToast('Pilot marked as Completed! Stats updated.');
            const dash = RBAC.getDashboardForRole((AuthManager.getUser() || {}).role);
            setTimeout(() => window.location.href = dash, 1500);
        });
    },
    updateProgress() {
        const total = document.querySelectorAll('#pilot-tasks-list label').length;
        const checked = document.querySelectorAll('#pilot-tasks-list input:checked').length;
        const pct = total === 0 ? 0 : (checked / total) * 100;
        const bar = document.getElementById('task-progress-fill'); if (bar) bar.style.width = `${pct}%`;
        const text = document.getElementById('task-progress-text'); if (text) text.innerText = `${Math.round(pct)}%`;
    }
};

const ExpenseManager = {
    init() {
        const id = new URLSearchParams(window.location.search).get('id'); this.pilotId = id;
        if (!id) { window.location.href = '/dashboard/'; return; }
        const pilot = StateStore.getData().pilots.find(p => p.id === id); if (!pilot) return;
        const bl = document.getElementById('back-link'); if (bl) bl.href = `/pilot/?id=${id}`;
        const sub = document.getElementById('expense-subtitle'); if (sub) sub.innerText = `Track spending for ${pilot.type} (${pilot.location})`;
        this.renderExpenses(pilot);
        const form = document.getElementById('expense-form');
        if (form) form.addEventListener('submit', (e) => { e.preventDefault(); this.addExpense(form); });
    },
    renderExpenses(pilot) {
        const list = document.getElementById('expense-list');
        const expenses = pilot.expenses || [];
        const budget = parseInt(pilot.budget || 0);
        const spent = expenses.reduce((s, e) => s + parseInt(e.amount), 0);
        const rem = budget - spent;
        const remEl = document.getElementById('budget-remaining');
        if (remEl) { remEl.innerText = `₹${rem.toLocaleString()}`; remEl.style.color = rem < 0 ? '#ef4444' : '#0D9488'; }
        if (expenses.length === 0) { list.innerHTML = `<div style="padding:2rem;text-align:center;"><p style="color:var(--text-muted);">No expenses recorded yet.</p></div>`; }
        else { list.innerHTML = `<div style="display:flex;flex-direction:column;gap:0.8rem;">${expenses.map((ex, i) => `<div style="display:flex;justify-content:space-between;align-items:center;padding:1rem;background:var(--bg-surface-hover);border-radius:8px;border:1px solid var(--border-color);"><div><div style="font-weight:600;color:var(--text-primary);">${ex.item}</div><div style="font-size:0.85rem;color:var(--text-muted);">${new Date(ex.date).toLocaleDateString()}</div></div><div style="display:flex;align-items:center;gap:1rem;"><span style="font-weight:700;color:var(--text-primary);">₹${parseInt(ex.amount).toLocaleString()}</span><button onclick="ExpenseManager.deleteExpense(${i})" style="color:#ef4444;background:none;border:none;cursor:pointer;"><i class="fa-solid fa-trash"></i></button></div></div>`).join('')}</div>`; }
    },
    addExpense(form) {
        const fd = new FormData(form);
        StateStore.addExpense(this.pilotId, { item: fd.get('item'), amount: fd.get('amount'), date: fd.get('date'), id: Date.now() });
        Utils.showToast('Expense added!'); form.reset();
        this.renderExpenses(StateStore.getData().pilots.find(p => p.id === this.pilotId));
    },
    deleteExpense(index) {
        StateStore.deleteExpense(this.pilotId, index);
        Utils.showToast('Expense removed.');
        this.renderExpenses(StateStore.getData().pilots.find(p => p.id === this.pilotId));
    }
};

/* ═══════════════════════════════════════════
   ADMIN MANAGER
   ═══════════════════════════════════════════ */
const AdminManager = {
    init() { this.renderUserTable(); this.renderStats(); this.bindActions(); },
    renderStats() {
        const d = StateStore.getData();
        const set = (id, v) => { const el = document.getElementById(id); if (el) el.innerText = v; };
        set('admin-total-users', d.users.length);
        set('admin-total-pilots', d.pilots.length);
        set('admin-impact', `${d.stats.impactScore}/10`);
        set('admin-active', d.users.filter(u => u.status === 'active').length);
    },
    renderUserTable() {
        const tbody = document.getElementById('admin-users-table');
        if (!tbody) return;
        const d = StateStore.getData();
        tbody.innerHTML = d.users.map(u => `<tr>
            <td style="padding:0.75rem;border-bottom:1px solid var(--border-color);"><div style="display:flex;align-items:center;gap:0.75rem;"><div style="width:32px;height:32px;border-radius:50%;background:${RBAC.roleColors[u.role]};color:#fff;display:flex;align-items:center;justify-content:center;font-size:0.7rem;font-weight:700;">${u.name.split(' ').map(w => w[0]).join('').slice(0, 2)}</div><div><div style="font-weight:600;color:var(--text-primary);font-size:0.85rem;">${u.name}</div><div style="font-size:0.75rem;color:var(--text-muted);">${u.email}</div></div></div></td>
            <td style="padding:0.75rem;border-bottom:1px solid var(--border-color);"><span style="background:${RBAC.roleColors[u.role]};color:#fff;padding:0.15rem 0.5rem;border-radius:999px;font-size:0.7rem;font-weight:600;text-transform:uppercase;">${RBAC.roleLabels[u.role]}${u.role === 'ngo' && u.verified ? ' ✓' : ''}</span></td>
            <td style="padding:0.75rem;border-bottom:1px solid var(--border-color);"><span style="color:${u.status === 'active' ? '#0D9488' : '#ea580c'};font-weight:600;font-size:0.8rem;text-transform:capitalize;">${u.status}</span></td>
            <td style="padding:0.75rem;border-bottom:1px solid var(--border-color);font-size:0.8rem;color:var(--text-muted);">${new Date(u.joined).toLocaleDateString()}</td>
            <td style="padding:0.75rem;border-bottom:1px solid var(--border-color);"><button onclick="AdminManager.toggleStatus('${u.id}')" class="btn btn-outline" style="font-size:0.7rem;padding:0.25rem 0.6rem;">${u.status === 'active' ? 'Suspend' : 'Approve'}</button></td></tr>`).join('');
    },
    toggleStatus(id) {
        const d = StateStore.getData();
        const u = d.users.find(x => x.id === id);
        if (u) { u.status = u.status === 'active' ? 'suspended' : 'active'; StateStore.saveData(d); this.renderUserTable(); this.renderStats(); Utils.showToast(`User ${u.status}`); }
    },
    bindActions() {
        const exportBtn = document.getElementById('export-audit');
        if (exportBtn) exportBtn.addEventListener('click', () => {
            const d = StateStore.getData();
            const csv = 'Action,User,Timestamp,Details\n' + d.auditLog.map(l => `${l.action},${l.user},${l.timestamp},${l.details}`).join('\n');
            const blob = new Blob([csv], { type: 'text/csv' });
            const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'audit_log.csv'; a.click();
            Utils.showToast('Audit log exported!');
        });
    }
};

/* ═══════════════════════════════════════════
   NGO MANAGER — Real API data
   ═══════════════════════════════════════════ */
const NgoManager = {
    async init() {
        await this.loadStats();
        await this.loadAssignedPilots();
    },

    async loadStats() {
        try {
            const res = await fetch('/api/dashboard/stats/');
            if (!res.ok) throw new Error('not ok');
            const d = await res.json();
            const set = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val ?? '—'; };
            set('ngo-ongoing', d.assigned_pilots ?? 0);
            set('ngo-members', d.team_members ?? 0);
            set('ngo-milestone', (d.avg_progress != null ? d.avg_progress + '%' : '—'));
            set('ngo-beneficiaries', '—'); // not computed yet
        } catch (e) { console.warn('NGO stats error:', e); }
    },

    async loadAssignedPilots() {
        const container = document.getElementById('ngo-assigned-pilots');
        if (!container) return;
        try {
            const res = await fetch('/api/pilots/');
            if (!res.ok) throw new Error('not ok');
            const d = await res.json();
            const pilots = d.pilots || [];

            if (pilots.length === 0) {
                container.innerHTML = '<p style="color:var(--text-muted);padding:1rem 0;">No pilots assigned to you yet.</p>';
                return;
            }

            const STATUS_COLOR = { active: '#0D9488', draft: '#6B7280', completed: '#1A56DB', paused: '#D97706' };
            container.innerHTML = pilots.map(p => `
                <div style="display:flex;align-items:center;padding:0.9rem 0;border-bottom:1px solid var(--border-color);gap:1rem;">
                    <div style="flex:1;">
                        <div style="font-weight:600;color:var(--text-primary);">${p.title}</div>
                        <div style="font-size:0.8rem;color:var(--text-muted);margin-top:0.2rem;">${p.location} &middot; Target: ${p.target_date}</div>
                    </div>
                    <div style="display:flex;align-items:center;gap:0.75rem;">
                        <div style="width:80px;background:var(--bg-secondary);border-radius:99px;height:6px;overflow:hidden;">
                            <div style="height:100%;background:${STATUS_COLOR[p.status] || '#6B7280'};width:${p.progress}%;border-radius:99px;"></div>
                        </div>
                        <span style="font-size:0.75rem;color:var(--text-muted);">${p.progress}%</span>
                        <span style="font-size:0.72rem;padding:0.2rem 0.6rem;border-radius:99px;font-weight:600;background:${STATUS_COLOR[p.status] || '#6B7280'}22;color:${STATUS_COLOR[p.status] || '#6B7280'};text-transform:capitalize;">${p.status}</span>
                    </div>
                </div>`).join('');
        } catch (e) {
            if (container) container.innerHTML = '<p style="color:#ef4444;"><i class="fa-solid fa-triangle-exclamation"></i> Failed to load pilots.</p>';
        }
    }
};

/* ═══════════════════════════════════════════
   BENEFICIARY MANAGER — Real API data
   ═══════════════════════════════════════════ */
const BeneficiaryManager = {
    async init() { await this.loadData(); },

    async loadData() {
        try {
            const res = await fetch('/api/dashboard/stats/');
            if (!res.ok) throw new Error('not ok');
            const d = await res.json();

            // Update stat cards
            const set = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val ?? '—'; };
            set('bene-programs', d.programs);
            set('bene-feedback-count', d.feedback_count ?? 0);
            set('bene-certs-count', d.certificate_count ?? 0);

            // Render enrollments
            const container = document.getElementById('beneficiary-programs');
            if (!container) return;

            const enrollments = d.enrollments || [];
            if (enrollments.length === 0) {
                container.innerHTML = '<p style="color:var(--text-muted);padding:2rem 0;text-align:center;"><i class="fa-solid fa-book-open" style="font-size:2rem;opacity:0.3;display:block;margin-bottom:0.5rem;"></i>No programs enrolled yet.</p>';
                return;
            }

            const STATUS_COLOR = { active: '#1A56DB', draft: '#6B7280', completed: '#0D9488', paused: '#D97706' };
            container.innerHTML = enrollments.map(e => `
                <div class="card" style="padding:1.5rem;margin-bottom:1rem;">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.75rem;">
                        <h4 style="color:var(--text-primary);margin:0;">${e.pilot_title}</h4>
                        <span style="background:${STATUS_COLOR[e.status] || '#6B7280'}18;color:${STATUS_COLOR[e.status] || '#6B7280'};padding:0.2rem 0.6rem;border-radius:999px;font-size:0.7rem;font-weight:600;text-transform:capitalize;">${e.status}</span>
                    </div>
                    <p style="color:var(--text-secondary);font-size:0.85rem;margin-bottom:0.75rem;"><i class="fa-solid fa-location-dot"></i> ${e.pilot_location}</p>
                    <div style="margin-bottom:0.75rem;">
                        <div style="display:flex;justify-content:space-between;font-size:0.8rem;margin-bottom:0.3rem;">
                            <span style="color:var(--text-muted);">Progress</span>
                            <span style="font-weight:600;color:var(--text-primary);">${e.progress}%</span>
                        </div>
                        <div style="height:6px;background:var(--bg-secondary);border-radius:3px;overflow:hidden;">
                            <div style="height:100%;width:${e.progress}%;background:linear-gradient(90deg,#1A56DB,#0D9488);border-radius:3px;transition:width 1s ease;"></div>
                        </div>
                    </div>
                    ${e.badges && e.badges.length ? `<div style="font-size:0.8rem;color:var(--text-muted);">Badges: ${e.badges.join(' ')}</div>` : ''}
                </div>`).join('');
        } catch (e) {
            console.warn('Beneficiary data error:', e);
            const container = document.getElementById('beneficiary-programs');
            if (container) container.innerHTML = '<p style="color:#ef4444;"><i class="fa-solid fa-triangle-exclamation"></i> Failed to load programs.</p>';
        }
    }
};


