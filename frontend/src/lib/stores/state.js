import { derived, get, writable } from 'svelte/store';
import { persisted } from './persisted.js';

/**
 * App state. Local-first: everything lives in localStorage; signed-in users also sync
 * {holdings, settings, customThemes} to the server (see lib/sync.js).
 * Broker API keys are deliberately NOT part of synced state (see brokerKeys).
 *
 * Holding shape (mirrors backend models.Holding.to_dict):
 *   { id, key, type: IN_EQ|US_EQ|MF|OTHER, symbol, exchange, name, qty, avgPrice,
 *     currency: INR|USD, broker, sector, isin, priceOverride: number|null }
 */

export const DEFAULT_SETTINGS = {
  view: 'treemap',            // see lib/views/registry.js
  groupBy: 'none',            // none | assetClass | broker | sector
  mergeAccounts: true,        // same instrument in several accounts → one tile (off while grouping by broker)
  visibleTypes: { IN_EQ: true, US_EQ: true, MF: true, OTHER: true },  // quick filter (hotkeys 1-4, 0 = all)
  hiddenBrokers: [],          // quick filter by account
  colorMetric: 'day',         // day | total — drives tile colour
  labelMetric: 'both',        // both | day (= only the colour metric) — % shown on tiles
  showTileValues: true,       // show the selected amount(s) on tiles; hover always includes both
  tileAmountMode: 'value',    // value | both | invested
  showTilePrice: false,       // LTP on tiles
  showSummary: true,          // corner summary (total value, day/total change)
  showTotalValue: true,       // include absolute total in the summary
  privacy: false,             // master switch: hide every absolute amount (hotkey: h)
  baseCurrency: 'INR',
  refreshSec: 60,
  dayFullScale: 3,            // % change at which day colour fully saturates
  totalFullScale: 50,
  theme: 'terminal',
  autoHideGear: true,
  hideCursor: true,
};

export const holdings = persisted('tf.holdings', [], { merge: false });
export const settings = persisted('tf.settings', DEFAULT_SETTINGS);
export const customThemes = persisted('tf.customThemes', [], { merge: false });
export const updatedAt = persisted('tf.updatedAt', 0, { merge: false });
// Bring-your-own broker keys: only persisted if the user ticks "remember on this device".
export const brokerKeys = persisted('tf.brokerKeys', {}, { merge: false });

export const ui = writable({ settingsOpen: false, tab: 'holdings', importPreview: null, toast: null });

// Bump updatedAt whenever synced state changes (used for last-write-wins sync).
let ready = false;
for (const s of [holdings, settings, customThemes]) s.subscribe(() => { if (ready) updatedAt.set(Date.now()); });
ready = true;

export function holdingKey(h) {
  if (h.type === 'IN_EQ') return `IN_EQ:${h.exchange || 'NSE'}:${h.symbol}`;
  if (h.type === 'OTHER') return `OTHER:${h.id}`;
  return `${h.type}:${h.symbol}`;
}

const uid = () => Math.random().toString(36).slice(2, 14);

export function normalizeHolding(h) {
  const n = {
    id: h.id || uid(),
    type: h.type || 'OTHER',
    symbol: String(h.symbol || '').trim(),
    exchange: h.exchange || (h.type === 'IN_EQ' ? 'NSE' : ''),
    name: h.name || '',
    qty: Number(h.qty) || 0,
    avgPrice: Number(h.avgPrice ?? h.avg_price) || 0,
    currency: h.currency || (h.type === 'US_EQ' ? 'USD' : 'INR'),
    broker: h.broker || '',
    sector: h.sector || '',
    isin: h.isin || '',
    priceOverride: h.priceOverride == null || h.priceOverride === '' ? null : Number(h.priceOverride),
  };
  n.key = holdingKey(n);
  return n;
}

export function addHoldings(list) {
  holdings.update((hs) => [...hs, ...list.map(normalizeHolding)]);
}

/** Re-sync: drop existing holdings matching `isReplaced`, then add the new ones. */
export function replaceHoldings(list, isReplaced) {
  holdings.update((hs) => [...hs.filter((h) => !isReplaced(h)), ...list.map(normalizeHolding)]);
}

/**
 * What a re-import replaces:
 *  - CAS (covers every fund across platforms): all existing mutual funds.
 *  - broker file/API: existing holdings with the same (broker, type) pairs as the import.
 */
export function replaceScope(list, source) {
  if (source === 'cas') return (h) => h.type === 'MF' || (h.type === 'OTHER' && h.sector === 'Mutual Fund');
  const pairs = new Set(list.map((h) => `${h.broker}|${h.type}`));
  return (h) => !!h.broker && pairs.has(`${h.broker}|${h.type}`);
}

export function updateHolding(id, patch) {
  holdings.update((hs) => hs.map((h) => (h.id === id ? normalizeHolding({ ...h, ...patch }) : h)));
}

export function removeHolding(id) {
  holdings.update((hs) => hs.filter((h) => h.id !== id));
}

export function toast(msg, kind = 'info') {
  ui.update((u) => ({ ...u, toast: { msg, kind, t: Date.now() } }));
  setTimeout(() => ui.update((u) => (u.toast && Date.now() - u.toast.t >= 3900 ? { ...u, toast: null } : u)), 4000);
}

export function openSettings(tab) {
  ui.update((u) => ({ ...u, settingsOpen: true, tab: tab || u.tab }));
}

export function snapshot() {
  return { holdings: get(holdings), settings: get(settings), customThemes: get(customThemes) };
}

export function restore(state) {
  if (!state) return;
  if (Array.isArray(state.holdings)) holdings.set(state.holdings.map(normalizeHolding));
  if (state.settings) settings.set({ ...DEFAULT_SETTINGS, ...state.settings });
  if (Array.isArray(state.customThemes)) customThemes.set(state.customThemes);
}

export const instrumentKeys = derived(holdings, (hs) =>
  [...new Set(hs.filter((h) => h.type !== 'OTHER' && h.priceOverride == null).map((h) => h.key))]
);
