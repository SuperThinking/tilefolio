<script>
  import { DEFAULT_SETTINGS, settings } from '../stores/state.js';
  import { market, refreshQuotes } from '../stores/quotes.js';
  import { VIEWS } from '../views/registry.js';
  import { ago } from '../format.js';

  const set = (k, v) => settings.update((s) => ({ ...s, [k]: v }));
</script>

<div class="stack">
  <h3>Visualization</h3>
  <div class="grid">
    <label>View
      <select class="ctl" value={$settings.view} onchange={(e) => set('view', e.currentTarget.value)}>
        {#each Object.entries(VIEWS) as [id, v]}<option value={id}>{v.label}</option>{/each}
      </select>
    </label>
    <label>Group by
      <select class="ctl" value={$settings.groupBy} onchange={(e) => set('groupBy', e.currentTarget.value)}>
        <option value="none">Flat (no groups)</option>
        <option value="assetClass">Asset class</option>
        <option value="broker">Broker / account</option>
        <option value="sector">Sector</option>
      </select>
    </label>
    <label>Colour tiles by
      <select class="ctl" value={$settings.colorMetric} onchange={(e) => set('colorMetric', e.currentTarget.value)}>
        <option value="day">Day % change</option>
        <option value="total">Total % (vs. avg cost)</option>
      </select>
    </label>
    <label>% on tiles
      <select class="ctl" value={$settings.labelMetric} onchange={(e) => set('labelMetric', e.currentTarget.value)}>
        <option value="both">Day and total</option>
        <option value="day">Only the colour metric</option>
      </select>
    </label>
    <label>Full colour at day ±%
      <input class="ctl" type="number" min="0.5" max="20" step="0.5" value={$settings.dayFullScale} onchange={(e) => set('dayFullScale', Number(e.currentTarget.value))} />
    </label>
    <label>Full colour at total ±%
      <input class="ctl" type="number" min="5" max="500" step="5" value={$settings.totalFullScale} onchange={(e) => set('totalFullScale', Number(e.currentTarget.value))} />
    </label>
  </div>

  <label class="chk"><input type="checkbox" checked={$settings.mergeAccounts} onchange={(e) => set('mergeAccounts', e.currentTarget.checked)} />
    Merge the same stock or fund across accounts into one tile. Hotkey <b>m</b>. {#if $settings.groupBy === 'broker'}<span class="muted small">(not applied while grouping by broker)</span>{/if}</label>
  <p class="small muted" style="margin:0">Quick filters: chips next to the ⚙ (shift-click = only that one), or keys <b>1</b> IN stocks · <b>2</b> US stocks · <b>3</b> mutual funds · <b>4</b> other · <b>0</b> show all.</p>

  <h3>Privacy &amp; amounts</h3>
  <label class="chk"><input type="checkbox" checked={$settings.privacy} onchange={(e) => set('privacy', e.currentTarget.checked)} /> Hide all amounts (only % shown). Hotkey <b>h</b></label>
  <label class="chk"><input type="checkbox" checked={$settings.showTileValues} onchange={(e) => set('showTileValues', e.currentTarget.checked)} /> Show values on tiles</label>
  <label>Amounts shown on tiles
    <select class="ctl" value={$settings.tileAmountMode || 'value'} onchange={(e) => set('tileAmountMode', e.currentTarget.value)}>
      <option value="value">Current value only</option>
      <option value="both">Current value + invested amount</option>
      <option value="invested">Invested amount only</option>
    </select>
  </label>
  <label class="chk"><input type="checkbox" checked={$settings.showTilePrice} onchange={(e) => set('showTilePrice', e.currentTarget.checked)} /> Show price (LTP) on tiles</label>
  <label class="chk"><input type="checkbox" checked={$settings.showSummary} onchange={(e) => set('showSummary', e.currentTarget.checked)} /> Show portfolio summary (corner)</label>
  <label class="chk"><input type="checkbox" checked={$settings.showTotalValue} disabled={!$settings.showSummary} onchange={(e) => set('showTotalValue', e.currentTarget.checked)} /> Include total portfolio value in summary</label>

  <h3>Screen</h3>
  <label class="chk"><input type="checkbox" checked={$settings.autoHideGear} onchange={(e) => set('autoHideGear', e.currentTarget.checked)} /> Auto-hide settings icon (shows on mouse move)</label>
  <label class="chk"><input type="checkbox" checked={$settings.hideCursor} onchange={(e) => set('hideCursor', e.currentTarget.checked)} /> Hide cursor when idle</label>

  <h3>Data</h3>
  <div class="grid">
    <label>Base currency
      <select class="ctl" value={$settings.baseCurrency} onchange={(e) => set('baseCurrency', e.currentTarget.value)}>
        <option>INR</option><option>USD</option>
      </select>
    </label>
    <label>Refresh every
      <select class="ctl" value={String($settings.refreshSec)} onchange={(e) => set('refreshSec', Number(e.currentTarget.value))}>
        <option value="30">30 s</option><option value="60">60 s</option><option value="120">2 min</option><option value="300">5 min</option>
      </select>
    </label>
  </div>
  <div class="row small muted">
    Last update {ago($market.ts)}
    {#if $market.fx?.USDINR}· USD/INR {$market.fx.USDINR.toFixed(2)}{/if}
    {#if $market.error}<span class="neg">· {$market.error}</span>{/if}
    {#if $market.missing?.length}<span class="warn">· no quote: {$market.missing.slice(0, 5).join(', ')}{$market.missing.length > 5 ? '…' : ''}</span>{/if}
    <button class="btn small" onclick={refreshQuotes}>Refresh now</button>
  </div>
  <p class="small muted">
    Prices come from free sources and may be delayed: Yahoo for NSE and US (Finnhub for US when it's configured), and AMFI for MF NAVs.
    MF day change is the latest NAV vs the previous NAV, because NAVs publish in the evening. Not investment advice.
  </p>
  <div><button class="btn" onclick={() => settings.set({ ...DEFAULT_SETTINGS, theme: $settings.theme })}>Reset display settings</button></div>
</div>

<style>
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
  @media (max-width: 480px) { .grid { grid-template-columns: 1fr; } }
  label:not(.chk) { display: flex; flex-direction: column; gap: 3px; font-size: 12px; color: var(--muted); }
  .chk { display: flex; gap: 8px; align-items: center; }
</style>
