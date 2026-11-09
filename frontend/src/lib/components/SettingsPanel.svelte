<script>
  import { ui } from '../stores/state.js';
  import HoldingsTab from './HoldingsTab.svelte';
  import ImportTab from './ImportTab.svelte';
  import DisplayTab from './DisplayTab.svelte';
  import ThemesTab from './ThemesTab.svelte';
  import AccountTab from './AccountTab.svelte';

  let { config, enriched } = $props();

  const TABS = [
    ['holdings', 'Holdings', HoldingsTab],
    ['import', 'Import', ImportTab],
    ['display', 'Display', DisplayTab],
    ['themes', 'Themes', ThemesTab],
    ['account', 'Account', AccountTab],
  ];

  const close = () => ui.update((u) => ({ ...u, settingsOpen: false }));
  const setTab = (t) => ui.update((u) => ({ ...u, tab: t }));
  const Current = $derived((TABS.find((t) => t[0] === $ui.tab) || TABS[0])[2]);
</script>

<div class="scrim" onclick={close} role="presentation"></div>
<aside class="panel" aria-label="Settings">
  <header>
    <div class="tabs" role="tablist">
      {#each TABS as [id, label]}
        <button role="tab" class:active={$ui.tab === id} aria-selected={$ui.tab === id} onclick={() => setTab(id)}>{label}</button>
      {/each}
    </div>
    <button class="x" onclick={close} aria-label="Close settings">✕</button>
  </header>
  <div class="body">
    <Current {config} {enriched} />
  </div>
  <footer class="muted small">
    Hold <b>Tab</b> (with settings closed) for all shortcuts · <b>s</b> settings · <b>h</b> hide amounts · <b>1–4</b>/<b>0</b> filter · <b>Esc</b> close
  </footer>
</aside>

<style>
  .scrim { position: fixed; inset: 0; background: rgba(0, 0, 0, .35); z-index: 30; }
  .panel {
    position: fixed; top: 0; right: 0; bottom: 0; width: min(560px, 100vw); z-index: 31;
    background: var(--surface); color: var(--text); display: flex; flex-direction: column;
    border-left: 1px solid color-mix(in srgb, var(--muted) 25%, transparent);
    box-shadow: -12px 0 40px rgba(0, 0, 0, .35);
    animation: slide .18s ease-out;
  }
  @keyframes slide { from { transform: translateX(24px); opacity: 0; } }
  header { display: flex; align-items: center; border-bottom: 1px solid color-mix(in srgb, var(--muted) 20%, transparent); }
  .tabs { display: flex; flex: 1; overflow-x: auto; }
  .tabs button {
    background: none; border: none; padding: 14px 12px; color: var(--muted);
    border-bottom: 2px solid transparent; white-space: nowrap;
  }
  .tabs button.active { color: var(--text); border-bottom-color: var(--accent); }
  .x { background: none; border: none; padding: 12px 16px; color: var(--muted); font-size: 16px; }
  .body { flex: 1; overflow-y: auto; padding: 16px; }
  footer { padding: 8px 16px; border-top: 1px solid color-mix(in srgb, var(--muted) 20%, transparent); }
</style>
