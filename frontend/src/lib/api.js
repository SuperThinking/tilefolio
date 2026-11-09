// Thin fetch wrappers for the FastAPI backend.
// Same origin by default (Vite proxies /api in dev). For a split deploy (frontend on GitHub Pages),
// build with VITE_API_BASE=https://api.host — requests then go cross-origin with a bearer token
// instead of the session cookie (third-party cookies are blocked by browsers).

const API_BASE = (import.meta.env.VITE_API_BASE || '').replace(/\/+$/, '');
const TOKEN_KEY = 'tf.session';

export const apiUrl = (path) => API_BASE + path;

export function setSessionToken(token) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch { /* storage blocked: sync just won't persist across reloads */ }
}

function sessionToken() {
  try { return localStorage.getItem(TOKEN_KEY); } catch { return null; }
}

async function req(path, opts = {}) {
  const headers = { ...(opts.headers || {}) };
  const token = sessionToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  const r = await fetch(apiUrl(path), { credentials: API_BASE ? 'omit' : 'same-origin', ...opts, headers });
  let body = null;
  try { body = await r.json(); } catch { /* non-JSON */ }
  if (!r.ok) {
    if (r.status === 401 && token) setSessionToken(null); // expired/invalid session
    const msg = body?.detail ? (typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)) : `HTTP ${r.status}`;
    const err = new Error(msg);
    err.status = r.status;
    throw err;
  }
  return body;
}

const json = (method, body) => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
});

export const api = {
  config: () => req('/api/config'),
  quotes: (keys) => req('/api/quotes', json('POST', { keys })),
  search: (q, kinds = 'IN_EQ,MF,US_EQ') => req(`/api/search?q=${encodeURIComponent(q)}&kinds=${kinds}`),

  importFile: (file, broker) =>
    req(`/api/import/file?broker=${encodeURIComponent(broker)}&filename=${encodeURIComponent(file.name)}`, {
      method: 'POST', headers: { 'Content-Type': 'application/octet-stream' }, body: file,
    }),
  importCas: (file, password) =>
    req('/api/import/cas', {
      method: 'POST', headers: { 'Content-Type': 'application/pdf', 'X-CAS-Password': password }, body: file,
    }),

  kiteHoldings: (b) => req('/api/brokers/kite/holdings', json('POST', b)),
  upstoxHoldings: (b) => req('/api/brokers/upstox/holdings', json('POST', b)),
  requestBroker: (broker, note) => req('/api/broker-requests', json('POST', { broker, note })),

  me: () => req('/api/auth/me'),
  googleLogin: (credential) => req('/api/auth/google', json('POST', { credential })),
  logout: () => req('/api/auth/logout', { method: 'POST' }),
  getState: () => req('/api/state'),
  putState: (state, updatedAt) => req('/api/state', json('PUT', { state, updatedAt })),
};
