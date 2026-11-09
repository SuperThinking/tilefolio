<script>
  import { money, pct } from '../format.js';

  import { TYPE_ORDER, TYPE_SHORT } from '../portfolio.js';

  let { totals, settings, market, filtered = false } = $props();
  const filterLabel = $derived(
    [
      ...TYPE_ORDER.filter((t) => settings.visibleTypes?.[t] !== false).map((t) => TYPE_SHORT[t]),
    ].join(', ') + ((settings.hiddenBrokers || []).length ? ` · ${(settings.hiddenBrokers || []).length} account(s) hidden` : '')
  );
  const cls = (v) => (v > 0 ? 'pos' : v < 0 ? 'neg' : '');
  const showAbs = $derived(!settings.privacy);
</script>

<div class="summary" aria-live="polite">
  {#if settings.showTotalValue && showAbs}
    <span class="total">{money(totals.value, settings.baseCurrency)}</span>
  {/if}
  <span>Day <b class={cls(totals.dayPct)}>{pct(totals.dayPct)}</b>{#if showAbs}<span class="muted">&nbsp;{money(totals.dayChange, settings.baseCurrency, { sign: true })}</span>{/if}</span>
  <span title={totals.unknownCostCount ? `${totals.unknownCostCount} holding(s) with unknown cost are excluded from Total` : ''}>Total <b class={cls(totals.totalPct)}>{pct(totals.totalPct)}</b>{#if showAbs}<span class="muted">&nbsp;{money(totals.totalChange, settings.baseCurrency, { sign: true })}</span>{/if}{#if totals.unknownCostCount}<span class="muted">*</span>{/if}</span>
  {#if filtered}<span class="tag">{filterLabel}</span>{/if}
  {#if market.error}<span class="neg" title={market.error}>● offline</span>{/if}
</div>

<style>
  .summary {
    position: fixed; left: 10px; bottom: 10px; z-index: 10; display: flex; gap: 14px; align-items: baseline;
    padding: 6px 10px; border-radius: var(--radius); font-size: 13px; font-variant-numeric: tabular-nums;
    background: color-mix(in srgb, var(--bg) 78%, transparent); backdrop-filter: blur(6px);
    color: var(--text); pointer-events: none;
  }
  .total { font-weight: 700; font-size: 15px; }
  .tag { font-size: 11px; padding: 1px 8px; border-radius: 999px; border: 1px solid var(--accent); color: var(--accent); }
</style>
