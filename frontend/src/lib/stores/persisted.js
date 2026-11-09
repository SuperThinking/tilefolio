import { writable } from 'svelte/store';

/** Writable store mirrored to localStorage. Storage may be unavailable (private mode) — never throw. */
export function persisted(key, initial, { storage = 'local', merge = true } = {}) {
  const store = storage === 'session' ? safe(() => window.sessionStorage) : safe(() => window.localStorage);
  let start = initial;
  try {
    const raw = store?.getItem(key);
    if (raw != null) {
      const parsed = JSON.parse(raw);
      start = merge && isPlainObject(initial) && isPlainObject(parsed) ? { ...initial, ...parsed } : parsed;
    }
  } catch { /* corrupt or blocked: fall back to initial */ }

  const s = writable(start);
  s.subscribe((v) => {
    try { store?.setItem(key, JSON.stringify(v)); } catch { /* quota / blocked */ }
  });
  return s;
}

function safe(fn) { try { return fn(); } catch { return null; } }
function isPlainObject(v) { return v && typeof v === 'object' && !Array.isArray(v); }

export function readStorage(key, storage = 'local') {
  try {
    const s = storage === 'session' ? window.sessionStorage : window.localStorage;
    const raw = s.getItem(key);
    return raw == null ? null : JSON.parse(raw);
  } catch { return null; }
}

export function writeStorage(key, value, storage = 'local') {
  try {
    const s = storage === 'session' ? window.sessionStorage : window.localStorage;
    if (value == null) s.removeItem(key); else s.setItem(key, JSON.stringify(value));
  } catch { /* ignore */ }
}
