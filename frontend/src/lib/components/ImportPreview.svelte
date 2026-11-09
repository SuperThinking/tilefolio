<script>
  import { addHoldings, holdings, replaceHoldings, replaceScope, toast, ui } from '../stores/state.js';
  import { refreshQuotes } from '../stores/quotes.js';
  import { TYPE_ORDER, TYPE_SHORT } from '../portfolio.js';
  import { price as fmtPrice } from '../format.js';

  let { preview } = $props();

  // Which asset types to keep from this import. Example: drop the MFs from a broker export when you
  // import funds through the CAS instead, so the same fund isn't counted twice.
  const counts = $derived(Object.fromEntries(TYPE_ORDER.map((t) => [t, preview.holdings.filter((h) => h.type === t).length])));
  let include = $state({ IN_EQ: true, US_EQ: true, MF: true, OTHER: true });
  let mode = $state('replace');

  const selected = $derived(preview.holdings.filter((h) => include[h.type]));
  const isCas = $derived(preview.source === 'cas');
  const scope = $derived(replaceScope(selected, preview.source));
  const replacing = $derived($holdings.filter(scope).length);
  const brokers = $derived([...new Set(selected.map((h) => h.broker).filter(Boolean))]);
  // Funds already present from a broker import would be double-counted next to CAS funds.
  const overlapMf = $derived(!isCas && include.MF && counts.MF > 0 && $holdings.some((h) => h.type === 'MF' && !brokers.includes(h.broker)));

  const close = () => ui.update((u) => ({ ...u, importPreview: null }));

  function confirmImport() {
    if (mode === 'replace' && replacing) replaceHoldings(selected, scope);
    else addHoldings(selected);
    toast(`Imported ${selected.length} holdings`);
    close();
    ui.update((u) => ({ ...u, tab: 'holdings' }));
    refreshQuotes();
  }
</script>

<div class="scrim" onclick={close} role="presentation"></div>
<div class="modal" role="dialog" aria-modal="true" aria-label="Import preview">
  <h3>Import from {preview.label}: {selected.length} of {preview.holdings.length} holdings</h3>

  <div class="row small">
    {#each TYPE_ORDER.filter((t) => counts[t]) as t}
      <label class="chip" class:off={!include[t]}>
        <input type="checkbox" bind:checked={include[t]} /> {TYPE_SHORT[t]} ({counts[t]})
      </label>
    {/each}
  </div>

  {#if preview.warnings?.length}
    <details class="warns" open={preview.warnings.length < 4}>
      <summary class="warn small">{preview.warnings.length} warning(s)</summary>
      <ul class="small">{#each preview.warnings as w}<li>{w}</li>{/each}</ul>
    </details>
  {/if}
  {#if overlapMf}
    <p class="small warn" style="margin:0">
      You already have mutual funds from another source, such as a CAS. Importing these too may count the same fund twice.
      Untick <b>Mutual funds</b> if you track funds through the CAS.
    </p>
  {/if}

  <div class="tbl">
    <table class="small">
      <thead><tr><th>Name</th><th>Type</th><th>Qty</th><th>Avg</th><th>Account</th></tr></thead>
      <tbody>
        {#each selected as h}
          <tr>
            <td title={h.name}>{h.type === 'MF' ? h.name || h.symbol : h.symbol}</td>
            <td>{h.type}</td>
            <td>{+Number(h.qty).toFixed(4)}</td>
            <td>{h.avgPrice > 0 ? fmtPrice(h.avgPrice, h.currency) : 'unknown'}</td>
            <td>{h.broker}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>

  {#if replacing}
    <label class="row small"><input type="radio" bind:group={mode} value="replace" />
      Replace {replacing} existing {isCas ? 'mutual fund holding(s). The CAS covers all platforms' : `holding(s) of the same type from ${brokers.join(', ')}`} (re-sync)
    </label>
    <label class="row small"><input type="radio" bind:group={mode} value="add" /> Add alongside existing holdings</label>
  {/if}
  <div class="row end">
    <button class="btn" onclick={close}>Cancel</button>
    <button class="btn primary" onclick={confirmImport} disabled={!selected.length}>Import {selected.length}</button>
  </div>
</div>

<style>
  .scrim { position: fixed; inset: 0; background: rgba(0, 0, 0, .5); z-index: 40; }
  .modal {
    position: fixed; z-index: 41; left: 50%; top: 50%; transform: translate(-50%, -50%);
    width: min(680px, calc(100vw - 32px)); max-height: calc(100vh - 64px); display: flex; flex-direction: column; gap: 10px;
    background: var(--surface); color: var(--text); padding: 16px; border-radius: var(--radius);
    box-shadow: 0 20px 60px rgba(0, 0, 0, .5);
  }
  .chip { display: inline-flex; gap: 6px; align-items: center; padding: 4px 10px; border-radius: 999px; background: var(--surface-2); cursor: pointer; }
  .chip.off { opacity: .5; }
  .tbl { overflow: auto; max-height: 45vh; }
  table { width: 100%; border-collapse: collapse; }
  th, td { text-align: left; padding: 4px 6px; border-bottom: 1px solid color-mix(in srgb, var(--muted) 15%, transparent); white-space: nowrap; }
  td:first-child { max-width: 260px; overflow: hidden; text-overflow: ellipsis; }
  th { color: var(--muted); font-weight: 500; }
  .warns ul { margin: 4px 0; padding-left: 18px; max-height: 140px; overflow: auto; }
  .end { justify-content: flex-end; }
</style>
