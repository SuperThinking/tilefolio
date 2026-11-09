<script>
  // Quick filter chips (top-right, next to the gear; auto-hides with it).
  // Click toggles a chip; Shift+click shows only that one. Hotkeys: 1–4 toggle types, 0 resets.
  import { TYPE_ORDER, TYPE_SHORT } from '../portfolio.js';
  import { settings } from '../stores/state.js';

  let { holdings, hidden = false } = $props();

  const types = $derived(TYPE_ORDER.filter((t) => holdings.some((h) => h.type === t)));
  const brokers = $derived([...new Set(holdings.map((h) => h.broker || 'Unassigned'))].sort());
  const vt = $derived($settings.visibleTypes || {});
  const hb = $derived(new Set($settings.hiddenBrokers || []));

  function toggleType(t, solo) {
    settings.update((s) => {
      const cur = { IN_EQ: true, US_EQ: true, MF: true, OTHER: true, ...s.visibleTypes };
      const next = solo ? Object.fromEntries(TYPE_ORDER.map((x) => [x, x === t])) : { ...cur, [t]: !cur[t] };
      // never filter everything out
      if (!types.some((x) => next[x])) return { ...s, visibleTypes: Object.fromEntries(TYPE_ORDER.map((x) => [x, true])) };
      return { ...s, visibleTypes: next };
    });
  }

  function toggleBroker(b, solo) {
    settings.update((s) => {
      let next = new Set(s.hiddenBrokers || []);
      if (solo) next = new Set(brokers.filter((x) => x !== b));
      else if (next.has(b)) next.delete(b);
      else next.add(b);
      if (brokers.every((x) => next.has(x))) next = new Set();
      return { ...s, hiddenBrokers: [...next] };
    });
  }
</script>

{#if types.length > 1 || brokers.length > 1}
  <div class="qf" class:hidden role="toolbar" aria-label="Quick filters">
    {#if types.length > 1}
      {#each types as t, i}
        <button class:off={vt[t] === false} onclick={(e) => toggleType(t, e.shiftKey)} title="{TYPE_SHORT[t]} · key {TYPE_ORDER.indexOf(t) + 1} · shift-click = only">
          {TYPE_SHORT[t]}
        </button>
      {/each}
    {/if}
    {#if brokers.length > 1 && brokers.length <= 8}
      <span class="sep"></span>
      {#each brokers as b}
        <button class:off={hb.has(b)} onclick={(e) => toggleBroker(b, e.shiftKey)} title="{b} · shift-click = only">{b}</button>
      {/each}
    {/if}
  </div>
{/if}

<style>
  .qf {
    position: fixed; top: 8px; right: 52px; z-index: 25; display: flex; gap: 4px; align-items: center; flex-wrap: wrap;
    justify-content: flex-end; max-width: calc(100vw - 70px); padding: 4px; border-radius: 18px;
    background: color-mix(in srgb, var(--bg) 65%, transparent); backdrop-filter: blur(6px);
    transition: opacity .4s ease;
  }
  .qf.hidden { opacity: 0; pointer-events: none; }
  button {
    border: 1px solid color-mix(in srgb, var(--muted) 40%, transparent); background: var(--surface-2); color: var(--text);
    border-radius: 999px; padding: 3px 10px; font-size: 12px; white-space: nowrap;
  }
  button.off { opacity: .4; text-decoration: line-through; background: transparent; }
  button:hover { border-color: var(--accent); }
  .sep { width: 1px; height: 16px; background: color-mix(in srgb, var(--muted) 40%, transparent); margin: 0 2px; }
</style>
