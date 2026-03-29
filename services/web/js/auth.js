// services/web/js/auth.js
// Shared auth utilities — token management, authFetch, requireAuth, logout

const API_BASE = window.location.port === '3000' ? 'http://127.0.0.1:8000' : '';

// ---------- Token storage ----------

function saveTokens(accessToken, refreshToken) {
    localStorage.setItem('access_token', accessToken);
    if (refreshToken) localStorage.setItem('refresh_token', refreshToken);
}

function getAccessToken() {
    return localStorage.getItem('access_token');
}

function getRefreshToken() {
    return localStorage.getItem('refresh_token');
}

function clearTokens() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user');
}

function getCurrentUser() {
    try {
        return JSON.parse(localStorage.getItem('user') || 'null');
    } catch {
        return null;
    }
}

// ---------- Auth guard ----------

function requireAuth() {
    if (!getAccessToken()) {
        window.location.href = '/login.html';
        return false;
    }
    return true;
}

// ---------- Token refresh ----------

async function tryRefreshToken() {
    const refreshToken = getRefreshToken();
    if (!refreshToken) return false;
    try {
        const resp = await fetch(`${API_BASE}/auth/refresh`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh_token: refreshToken })
        });
        if (resp.ok) {
            const data = await resp.json();
            saveTokens(data.access_token, refreshToken);
            return true;
        }
    } catch (e) {}
    return false;
}

// ---------- Authenticated fetch ----------

async function authFetch(url, options = {}) {
    let token = getAccessToken();
    options.headers = options.headers || {};
    options.headers['Authorization'] = `Bearer ${token}`;

    let response = await fetch(url, options);

    if (response.status === 401) {
        const refreshed = await tryRefreshToken();
        if (refreshed) {
            token = getAccessToken();
            options.headers['Authorization'] = `Bearer ${token}`;
            response = await fetch(url, options);
        } else {
            clearTokens();
            window.location.href = '/login.html';
            return null;
        }
    }

    return response;
}

// ---------- Logout ----------

function logout() {
    clearTokens();
    window.location.href = '/login.html';
}

// ---------- Render topbar user ----------

function renderTopbarUser() {
    const user = getCurrentUser();
    const el = document.getElementById('topbarUsername');
    if (el && user) el.textContent = user.username;
}
