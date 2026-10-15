/*
 * Shared sign-in for Mundorum apps served from this origin (portal, vp).
 * noid's editor.html implements the same contract inline:
 *   - the DRF token lives in localStorage under `mundorum_token`
 *     (`noid_token` is the pre-shared-server key, read as a fallback);
 *   - Google sign-in uses redirect mode; login_uri carries `next=<app>` so
 *     /auth/google/callback/ returns to that app with ?auth_token=…
 */
const TOKEN_KEY = 'mundorum_token';
const LEGACY_TOKEN_KEY = 'noid_token';

const AUTH_ERRORS = {
  missing_credential: 'Sign-in failed: no credential received.',
  invalid_token: 'Sign-in failed: invalid Google token.',
  not_authorized: 'Access denied. Contact a manager to get access.',
};

function storage() {
  try { return window.localStorage; } catch { return null; }
}

export function getToken() {
  const s = storage();
  return s ? (s.getItem(TOKEN_KEY) || s.getItem(LEGACY_TOKEN_KEY)) : null;
}

export function setToken(token) {
  const s = storage();
  if (s) s.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  const s = storage();
  if (!s) return;
  s.removeItem(TOKEN_KEY);
  s.removeItem(LEGACY_TOKEN_KEY);
}

export class AuthError extends Error {}

/** fetch() with the shared token; a 401 clears the token and throws AuthError. */
export async function apiFetch(url, options = {}) {
  const headers = { ...(options.headers || {}) };
  const token = getToken();
  if (token) headers['Authorization'] = `Token ${token}`;
  const response = await fetch(url, { ...options, headers });
  if (response.status === 401) {
    clearToken();
    throw new AuthError('Session expired — please sign in again.');
  }
  return response;
}

export function signOut() {
  clearToken();
  if (window.google?.accounts?.id) window.google.accounts.id.disableAutoSelect();
}

function waitForGoogle() {
  return new Promise(resolve => {
    if (window.google?.accounts?.id) { resolve(); return; }
    const t = setInterval(() => {
      if (window.google?.accounts?.id) { clearInterval(t); resolve(); }
    }, 100);
  });
}

/**
 * Consume ?auth_token / ?auth_error from the callback redirect, validate the
 * stored token, and (when signed out) render the Google button.
 *
 * @param {object} opts
 * @param {string} opts.app        `next` key for the callback: '', 'noid' or 'vp'
 * @param {HTMLElement} [opts.buttonEl]  where to render the Google button
 * @returns {Promise<{user: object|null, error: string}>}
 */
export async function initAuth({ app, buttonEl } = {}) {
  const params = new URLSearchParams(window.location.search);
  const urlToken = params.get('auth_token');
  const urlError = params.get('auth_error');
  let error = urlError ? (AUTH_ERRORS[urlError] || 'Sign-in failed.') : '';
  if (urlToken) setToken(urlToken);
  if (urlToken || urlError) {
    params.delete('auth_token');
    params.delete('auth_error');
    const qs = params.toString();
    history.replaceState(null, '', window.location.pathname + (qs ? `?${qs}` : ''));
  }

  let user = null;
  if (getToken()) {
    try {
      const r = await apiFetch('/auth/me/');
      if (r.ok) user = await r.json();
      else clearToken();
    } catch {
      clearToken();
    }
  }

  if (!user && buttonEl) {
    try {
      const config = await (await fetch('/auth/config/')).json();
      if (config.google_client_id) {
        await waitForGoogle();
        const next = new URLSearchParams(app ? { next: app } : {}).toString();
        window.google.accounts.id.initialize({
          client_id: config.google_client_id,
          ux_mode: 'redirect',
          login_uri: `${window.location.origin}/auth/google/callback/${next ? '?' + next : ''}`,
        });
        window.google.accounts.id.renderButton(buttonEl, {
          theme: 'outline', size: 'large', shape: 'rectangular', width: 280,
        });
      } else if (!error) {
        error = 'Sign-in is not configured on this server (GOOGLE_CLIENT_ID).';
      }
    } catch (e) {
      if (!error) error = `Could not load sign-in: ${e.message}`;
    }
  }

  return { user, error };
}
