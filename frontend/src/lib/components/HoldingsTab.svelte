<script>
  import { api } from '../api.js';
  import { money, pct, price as fmtPrice } from '../format.js';
  import { addHoldings, holdings, removeHolding, settings, toast, updateHolding } from '../stores/state.js';
  import { refreshQuotes } from '../stores/quotes.js';

  let { enriched } = $props();

  let filter = $state('');
  let typeFilter = $state('');
  let adding = $state(false);
  let q = $state('');
  let results = $state([]);
  let pick = $state(null);
  let form = $state({ qty: '', avgPrice: '', broker: '', type: 'OTHER', name: '', currency: 'INR' });
  let searchTimer;

  const rowsById = $derived(Object.fromEntries(enriched.rows.map((r) => [r.id, r])));
  const shown = $derived(
    $holdings
      .filter((h) => !typeFilter || h.type === typeFilter)
      .filter((h) => !filter || `${h.symbol} ${h.name} ${h.broker} ${h.sector}`.toLowerCase().includes(filter.toLowerCase()))
      .sort((a, b) => (rowsById[b.id]?.value || 0) - (rowsById[a.id]?.value || 0))
  );
  const masked = $derived($settings.privacy);

  function onSearch() {
    clearTimeout(searchTimer);
    pick = null;
    if (q.trim().length < 2) { results = []; return; }
    searchTimer = setTimeout(async () => {
      try { results = (await api.search(q.trim())).results; } catch (e) { results = []; toast(e.message, 'error'); }
    }, 250);
  }

  function choose(r) {
    pick = r;
    results = [];
    q = `${r.symbol} — ${r.name}`;
  }

  function add() {
    const qty = Number(form.qty);
    if (!qty || qty <= 0) return toast('Quantity must be > 0', 'error');
    const base = pick
      ? { type: pick.type, symbol: pick.symbol, exchange: pick.exchange === 'US' ? '' : pick.exchange, name: pick.name, sector: pick.sector, isin: pick.isin, currency: pick.type === 'US_EQ' ? 'USD' : 'INR' }
      : { type: 'OTHER', symbol: form.name || q, name: form.name || q, currency: form.currency };
    if (!base.symbol) return toast('Pick an instrument or enter a name', 'error');
    if (!pick && !Number(form.avgPrice)) return toast('Manual assets need a price', 'error');
    addHoldings([{ ...base, qty, avgPrice: Number(form.avgPrice) || 0, broker: form.broker, priceOverride: pick ? null : Number(form.avgPrice) }]);
    toast(`Added ${base.symbol}`);
    adding = false; pick = null; q = ''; form = { qty: '', avgPrice: '', broker: '', type: 'OTHER', name: '', currency: 'INR' };
    refreshQuotes();
  }

  function num(v) { return v === '' || v == null ? null : Number(v); }

  function exportJson() {
    const blob = new Blob([JSON.stringify($holdings, null, 2)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'tilefolio-holdings.json';
    a.click();
    URL.revokeObjectURL(a.href);
  }

  function clearAll() {
    if (confirm(`Delete all ${$holdings.length} holdings from this device?`)) holdings.set([]);
  }
</script>

<div class="stack">
  <div class="row">
    <input class="ctl grow" placeholder="Filter holdings…" bind:value={filter} />
    <select class="ctl" bind:value={typeFilter} aria-label="Filter by type">
      <option value="">All types</option><option value="IN_EQ">IN stocks</option><option value="US_EQ">US stocks</option>
      <option value="MF">Mutual funds</option><option value="OTHER">Other</option>
    </select>
    {#if shown.length && (filter || typeFilter)}
      <button class="btn danger" onclick={() => { if (confirm(`Delete the ${shown.length} holdings shown?`)) { const ids = new Set(shown.map((h) => h.id)); holdings.update((hs) => hs.filter((h) => !ids.has(h.id))); } }}>Delete shown</button>
    {/if}
    <button class="btn primary" onclick={() => (adding = !adding)}>{adding ? 'Cancel' : '+ Add'}</button>
  </div>

  {#if adding}
    <div class="card stack">
      <div class="search">
        <input class="ctl" style="width:100%" placeholder="Search stock / fund (e.g. INFY, Parag Parikh, AAPL) or type a manual asset name" bind:value={q} oninput={onSearch} />
        {#if results.length}
          <ul class="results">
            {#each results as r (r.type + r.symbol)}
              <li><button onclick={() => choose(r)}><b>{r.symbol}</b> <span class="muted">{r.name}</span> <span class="badge">{r.type}</span></button></li>
            {/each}
          </ul>
        {/if}
      </div>
      {#if !pick && q.length > 1}<div class="muted small">No pick → added as a manual asset (no live price; you set the price).</div>{/if}
      <div class="row">
        <label class="f">Qty<input class="ctl" type="number" min="0" step="any" bind:value={form.qty} /></label>
        <label class="f">{pick ? 'Avg buy price' : 'Price'}<input class="ctl" type="number" min="0" step="any" bind:value={form.avgPrice} /></label>
        <label class="f">Broker<input class="ctl" placeholder="optional" bind:value={form.broker} /></label>
        {#if !pick}
          <label class="f">Ccy<select class="ctl" bind:value={form.currency}><option>INR</option><option>USD</option></select></label>
        {/if}
      </div>
      <div><button class="btn primary" onclick={add}>Add holding</button></div>
    </div>
  {/if}

  {#if !$holdings.length}
    <p class="muted">No holdings yet. Use <b>Import</b> to pull from a broker export / CAS, or add manually.</p>
  {:else}
    <div class="muted small">
      {$holdings.length} holdings · {masked ? '••••' : money(enriched.totals.value, $settings.baseCurrency)} ·
      Price field overrides the live quote (leave blank for live).
    </div>
    <div class="list">
      {#each shown as h (h.id)}
        {@const r = rowsById[h.id]}
        <div class="item">
          <div class="top">
            <div class="ident">
              <b>{h.type === 'MF' ? h.name || h.symbol : h.symbol}</b>
              <span class="badge">{h.type}</span>
              {#if h.broker}<span class="muted small">{h.broker}</span>{/if}
              <div class="muted small ell">{h.type === 'MF' ? `AMFI ${h.symbol}` : h.name}</div>
            </div>
            <div class="nums small">
              <div>{masked ? '••••' : money(r?.value, $settings.baseCurrency)}</div>
              <div><span class={r?.dayPct > 0 ? 'pos' : r?.dayPct < 0 ? 'neg' : ''}>{pct(r?.dayPct)}</span> / <span class={r?.totalPct > 0 ? 'pos' : r?.totalPct < 0 ? 'neg' : ''}>{pct(r?.totalPct)}</span></div>
            </div>
          </div>
          <div class="row edit">
            <label class="f">Qty<input class="ctl" type="number" step="any" value={h.qty} onchange={(e) => updateHolding(h.id, { qty: Number(e.currentTarget.value) })} /></label>
            <label class="f">Avg<input class="ctl" type="number" step="any" value={h.avgPrice} onchange={(e) => updateHolding(h.id, { avgPrice: Number(e.currentTarget.value) })} /></label>
            <label class="f">Price
              <input class="ctl" type="number" step="any" value={h.priceOverride ?? ''}
                placeholder={r?.price != null && h.priceOverride == null ? fmtPrice(r.price, h.currency) : 'live'}
                onchange={(e) => updateHolding(h.id, { priceOverride: num(e.currentTarget.value) })} />
            </label>
            <label class="f">Broker<input class="ctl" value={h.broker} onchange={(e) => updateHolding(h.id, { broker: e.currentTarget.value })} /></label>
            <label class="f">Sector<input class="ctl" value={h.sector} onchange={(e) => updateHolding(h.id, { sector: e.currentTarget.value })} /></label>
            <button class="btn danger del" title="Delete" onclick={() => removeHolding(h.id)}>✕</button>
          </div>
        </div>
      {/each}
    </div>
    <div class="row">
      <button class="btn" onclick={exportJson}>Export JSON</button>
      <button class="btn danger" onclick={clearAll}>Delete all</button>
    </div>
  {/if}
</div>

<style>
  .grow { flex: 1; }
  .card { padding: 12px; background: var(--surface-2); border-radius: var(--radius); }
  .search { position: relative; }
  .results {
    position: absolute; z-index: 5; left: 0; right: 0; max-height: 260px; overflow-y: auto; margin: 2px 0 0;
    padding: 0; list-style: none; background: var(--surface); border: 1px solid color-mix(in srgb, var(--muted) 35%, transparent);
  }
  .results button { width: 100%; text-align: left; background: none; border: none; padding: 6px 8px; }
  .results button:hover { background: var(--surface-2); }
  .badge { font-size: 10px; padding: 1px 4px; border-radius: 3px; background: color-mix(in srgb, var(--muted) 25%, transparent); color: var(--muted); }
  .f { display: flex; flex-direction: column; font-size: 11px; color: var(--muted); gap: 2px; flex: 1; min-width: 70px; }
  .list { display: flex; flex-direction: column; gap: 6px; }
  .item { padding: 8px 10px; background: var(--surface-2); border-radius: var(--radius); }
  .top { display: flex; justify-content: space-between; gap: 8px; }
  .ident { min-width: 0; }
  .ell { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 300px; }
  .nums { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
  .edit { margin-top: 6px; align-items: flex-end; }
  .edit .ctl { width: 100%; padding: 4px 6px; }
  .del { padding: 4px 8px; }
</style>
