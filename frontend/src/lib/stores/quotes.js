import { get, writable } from 'svelte/store';
import { api } from '../api.js';
import { instrumentKeys, settings } from './state.js';

/** { quotes: {key: Quote}, fx: {USDINR}, ts, error, loading } */
export const market = writable({ quotes: {}, fx: { USDINR: null }, ts: 0, error: null, loading: false, missing: [] });

let timer = null;
let inflight = false;

export async function refreshQuotes() {
  const keys = get(instrumentKeys);
  if (inflight) return;
  inflight = true;
  market.update((m) => ({ ...m, loading: true }));
  try {
    const r = await api.quotes(keys);
    market.update((m) => ({
      quotes: { ...m.quotes, ...r.quotes },
      fx: r.fx?.USDINR ? r.fx : m.fx,
      ts: r.ts * 1000,
      error: null,
      loading: false,
      missing: r.missing || [],
    }));
  } catch (e) {
    market.update((m) => ({ ...m, error: e.message, loading: false }));
  } finally {
    inflight = false;
  }
}

function schedule() {
  clearInterval(timer);
  const sec = Math.max(15, Number(get(settings).refreshSec) || 60);
  timer = setInterval(() => {
    if (document.visibilityState === 'visible') refreshQuotes();
  }, sec * 1000);
}

export function startPolling() {
  let lastKeys = '';
  instrumentKeys.subscribe((keys) => {
    const k = keys.join('|');
    if (k !== lastKeys) { lastKeys = k; refreshQuotes(); }
  });
  let lastSec = null;
  settings.subscribe((s) => { if (s.refreshSec !== lastSec) { lastSec = s.refreshSec; schedule(); } });
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible' && Date.now() - get(market).ts > 15000) refreshQuotes();
  });
}
