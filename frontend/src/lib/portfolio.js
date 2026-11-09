// Pure portfolio maths: holdings + market data -> enriched rows & totals in base currency.

export const ASSET_LABELS = { IN_EQ: 'Indian Equity', US_EQ: 'US Equity', MF: 'Mutual Funds', OTHER: 'Other' };

function fxFactor(ccy, base, usdinr) {
  if (ccy === base) return 1;
  if (!usdinr) return null;
  if (ccy === 'USD' && base === 'INR') return usdinr;
  if (ccy === 'INR' && base === 'USD') return 1 / usdinr;
  return null;
}

export function enrich(holdings, market, base = 'INR') {
  const usdinr = market.fx?.USDINR;
  const rows = [];
  for (const h of holdings) {
    const q = market.quotes[h.key];
    const overridden = h.priceOverride != null;
    const price = overridden ? h.priceOverride : q?.price ?? null;
    const prev = overridden ? null : q?.prevClose ?? null;
    const fx = fxFactor(h.currency, base, usdinr);
    const effPrice = price ?? h.avgPrice; // no quote yet: fall back to cost so the tile still renders
    const value = fx == null ? 0 : effPrice * h.qty * fx;
    const invested = fx == null ? 0 : h.avgPrice * h.qty * fx;
    const dayChange = prev && price != null && fx != null ? (price - prev) * h.qty * fx : 0;
    rows.push({
      ...h,
      price,
      prevClose: prev,
      live: !!q && !overridden,
      quoteSource: overridden ? 'manual' : q?.source || (h.type === 'OTHER' ? 'manual' : 'pending'),
      asOf: q?.asOf,
      value,
      invested,
      dayChange,
      dayPct: prev && price != null ? (price / prev - 1) * 100 : null,
      costKnown: h.avgPrice > 0,
      totalChange: value - invested,
      totalPct: invested > 0 ? (value / invested - 1) * 100 : null,
      assetClass: ASSET_LABELS[h.type] || 'Other',
    });
  }
  return { rows, totals: totalsOf(rows) };
}

/**
 * Totals. Holdings with unknown cost (avgPrice 0, e.g. CAS funds bought before the statement period)
 * are left out of total change/%. Counting them at zero cost would inflate the return.
 */
export function totalsOf(rows) {
  const value = rows.reduce((a, r) => a + r.value, 0);
  const dayChange = rows.reduce((a, r) => a + r.dayChange, 0);
  const known = rows.filter((r) => r.costKnown);
  const invested = known.reduce((a, r) => a + r.invested, 0);
  const knownValue = known.reduce((a, r) => a + r.value, 0);
  const prevValue = value - dayChange;
  return {
    value,
    invested,
    dayChange,
    dayPct: prevValue > 0 ? (dayChange / prevValue) * 100 : null,
    totalChange: knownValue - invested,
    totalPct: invested > 0 ? (knownValue / invested - 1) * 100 : null,
    unknownCostCount: rows.length - known.length,
  };
}

export const TYPE_ORDER = ['IN_EQ', 'US_EQ', 'MF', 'OTHER'];
export const TYPE_SHORT = { IN_EQ: 'IN stocks', US_EQ: 'US stocks', MF: 'Mutual funds', OTHER: 'Other' };

export function isFiltered(settings) {
  const vt = settings.visibleTypes || {};
  return TYPE_ORDER.some((t) => vt[t] === false) || (settings.hiddenBrokers || []).length > 0;
}

/** Quick filters: asset type + account. */
export function filterRows(rows, settings) {
  const vt = settings.visibleTypes || {};
  const hidden = new Set(settings.hiddenBrokers || []);
  return rows.filter((r) => vt[r.type] !== false && !hidden.has(r.broker || 'Unassigned'));
}

/**
 * Merge the same instrument held in several accounts into one tile. Skipped when grouping by
 * broker, because a merged tile can't sit inside one broker's group. Manual (OTHER) holdings never merge.
 */
export function mergeRows(rows) {
  const out = [];
  const byKey = new Map();
  for (const r of rows) {
    if (r.type === 'OTHER') { out.push(r); continue; }
    const m = byKey.get(r.key);
    if (!m) {
      const first = { ...r, parts: [r] };
      byKey.set(r.key, first);
      out.push(first);
      continue;
    }
    m.parts.push(r);
  }
  return out.map((m) => {
    if (!m.parts || m.parts.length < 2) return m.parts ? { ...m.parts[0], parts: undefined } : m;
    const ps = m.parts;
    const qty = ps.reduce((a, p) => a + p.qty, 0);
    const value = ps.reduce((a, p) => a + p.value, 0);
    const invested = ps.reduce((a, p) => a + p.invested, 0);
    const dayChange = ps.reduce((a, p) => a + p.dayChange, 0);
    const costKnown = ps.every((p) => p.costKnown);
    const brokers = [...new Set(ps.map((p) => p.broker || 'Unassigned'))];
    return {
      ...ps[0],
      id: `merged:${m.key}`,
      qty,
      avgPrice: costKnown ? ps.reduce((a, p) => a + p.avgPrice * p.qty, 0) / qty : 0,
      broker: brokers.join(' + '),
      value,
      invested,
      dayChange,
      costKnown,
      totalChange: value - invested,
      totalPct: costKnown && invested > 0 ? (value / invested - 1) * 100 : null,
      parts: ps,
    };
  });
}

/** Everything a view needs: filter → (merge) → totals. */
export function viewModel(enrichedRows, settings) {
  let rows = filterRows(enrichedRows, settings);
  if (settings.mergeAccounts && settings.groupBy !== 'broker') rows = mergeRows(rows);
  return { rows, totals: totalsOf(rows), filtered: isFiltered(settings) };
}

export function groupKey(row, groupBy) {
  switch (groupBy) {
    case 'assetClass': return row.assetClass;
    case 'broker': return row.broker || 'Unassigned';
    case 'sector': return row.sector || (row.type === 'MF' ? 'Mutual Fund' : 'Unclassified');
    default: return null;
  }
}
