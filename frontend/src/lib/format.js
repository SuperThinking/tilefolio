const SYM = { INR: '₹', USD: '$' };
export const MASK = '••••';

/** Compact money: INR uses lakh/crore, USD uses K/M/B. */
export function money(v, ccy = 'INR', { compact = true, masked = false, sign = false } = {}) {
  if (masked) return MASK;
  if (v == null || !Number.isFinite(v)) return '—';
  const s = sign && v > 0 ? '+' : v < 0 ? '−' : '';
  const a = Math.abs(v);
  const sym = SYM[ccy] ?? '';
  if (!compact) {
    return s + sym + a.toLocaleString(ccy === 'INR' ? 'en-IN' : 'en-US', { maximumFractionDigits: a < 100 ? 2 : 0 });
  }
  if (ccy === 'INR') {
    if (a >= 1e7) return `${s}${sym}${trim(a / 1e7)}Cr`;
    if (a >= 1e5) return `${s}${sym}${trim(a / 1e5)}L`;
    if (a >= 1e3) return `${s}${sym}${trim(a / 1e3)}k`;
  } else {
    if (a >= 1e9) return `${s}${sym}${trim(a / 1e9)}B`;
    if (a >= 1e6) return `${s}${sym}${trim(a / 1e6)}M`;
    if (a >= 1e3) return `${s}${sym}${trim(a / 1e3)}K`;
  }
  return s + sym + a.toFixed(a < 100 ? 2 : 0);
}

function trim(n) {
  return n >= 100 ? n.toFixed(0) : n >= 10 ? n.toFixed(1) : n.toFixed(2);
}

export function pct(v, digits = 2) {
  if (v == null || !Number.isFinite(v)) return '—';
  return `${v > 0 ? '+' : v < 0 ? '−' : ''}${Math.abs(v).toFixed(digits)}%`;
}

export function price(v, ccy) {
  if (v == null || !Number.isFinite(v)) return '—';
  return (SYM[ccy] ?? '') + v.toLocaleString(ccy === 'USD' ? 'en-US' : 'en-IN', { maximumFractionDigits: 2, minimumFractionDigits: 2 });
}

export function ago(ms) {
  if (!ms) return 'never';
  const s = Math.round((Date.now() - ms) / 1000);
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.round(s / 60)}m ago`;
  return `${Math.round(s / 3600)}h ago`;
}

export const signClass = (v) => (v > 0 ? 'pos' : v < 0 ? 'neg' : '');
