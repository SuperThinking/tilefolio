<script>
  // Shell: full-screen view + hidden gear (top-right) → settings drawer. Nothing else on screen,
  // so the page can be projected/left open on a monitor.
  import { onMount } from 'svelte';
  import { api } from './lib/api.js';
  import { handleRedirect } from './lib/brokers.js';
  import { enrich, TYPE_ORDER, viewModel } from './lib/portfolio.js';
  import { market, startPolling } from './lib/stores/quotes.js';
  import { customThemes, holdings, openSettings, settings, toast, ui } from './lib/stores/state.js';
  import { initAccount } from './lib/sync.js';
  import { applyTheme, findTheme } from './lib/themes.js';
  import { viewFor } from './lib/views/registry.js';
  import SettingsPanel from './lib/components/SettingsPanel.svelte';
  import ImportPreview from './lib/components/ImportPreview.svelte';
  import Summary from './lib/components/Summary.svelte';
  import QuickFilter from './lib/components/QuickFilter.svelte';
  import HotkeysOverlay from './lib/components/HotkeysOverlay.svelte';

  let config = $state(null);
  let idle = $state(false);
  let idleTimer;
  let showHotkeys = $state(false);

  const theme = $derived(findTheme($settings.theme, $customThemes));
  const enriched = $derived(enrich($holdings, $market, $settings.baseCurrency)); // all holdings (Holdings tab)
  const vm = $derived(viewModel(enriched.rows, $settings)); // filtered + merged (what's on screen)
  const View = $derived(viewFor($settings.view));
  const gearHidden = $derived($settings.autoHideGear && idle && !$ui.settingsOpen);

  $effect(() => applyTheme(theme));

  function poke() {
    idle = false;
    clearTimeout(idleTimer);
    idleTimer = setTimeout(() => (idle = true), 2500);
  }

  const GROUPS = ['none', 'assetClass', 'broker', 'sector'];

  // Hold Tab → cheat sheet. Only when no drawer or dialog is open, so Tab still moves focus inside forms.
  function onKeyUp(e) {
    if (e.key === 'Tab') showHotkeys = false;
  }

  function onKey(e) {
    if (e.key === 'Tab') {
      if ($ui.settingsOpen || $ui.importPreview || e.target.closest?.('input, textarea, select')) return;
      e.preventDefault();
      showHotkeys = true;
      return;
    }
    if (e.target.closest?.('input, textarea, select') || e.metaKey || e.ctrlKey || e.altKey) return;
    const k = e.key.toLowerCase();
    if (k === 'escape') ui.update((u) => ({ ...u, settingsOpen: false, importPreview: null }));
    else if (k === 's') ui.update((u) => ({ ...u, settingsOpen: !u.settingsOpen }));
    else if (k === 'h') settings.update((s) => ({ ...s, privacy: !s.privacy }));
    else if (k === '0') settings.update((s) => ({ ...s, visibleTypes: Object.fromEntries(TYPE_ORDER.map((t) => [t, true])), hiddenBrokers: [] }));
    else if (k >= '1' && k <= '4') {
      const t = TYPE_ORDER[Number(k) - 1];
      if (!$holdings.some((h) => h.type === t)) return;
      settings.update((s) => {
        const next = { IN_EQ: true, US_EQ: true, MF: true, OTHER: true, ...s.visibleTypes, [t]: !(s.visibleTypes?.[t] ?? true) };
        return TYPE_ORDER.some((x) => next[x] && $holdings.some((h) => h.type === x)) ? { ...s, visibleTypes: next } : s;
      });
    }
    else if (k === 'm') settings.update((s) => ({ ...s, mergeAccounts: !s.mergeAccounts }));
    else if (k === 'g') settings.update((s) => ({ ...s, groupBy: GROUPS[(GROUPS.indexOf(s.groupBy) + 1) % GROUPS.length] }));
    else if (k === 'f') {
      if (document.fullscreenElement) document.exitFullscreen?.();
      else document.documentElement.requestFullscreen?.().catch(() => {});
    }
  }

  onMount(async () => {
    poke();
    startPolling();
    try {
      config = await api.config();
      initAccount(config.googleClientId);
    } catch (e) {
      toast('Backend unreachable: ' + e.message, 'error');
    }
    try {
      const res = await handleRedirect();
      if (res) ui.update((u) => ({ ...u, importPreview: { ...res, label: res.source } }));
    } catch (e) {
      toast(e.message, 'error');
      openSettings('import');
    }
  });
</script>

<svelte:window onmousemove={poke} onkeydown={onKey} onkeyup={onKeyUp} onblur={() => (showHotkeys = false)} ontouchstart={poke} />

<main class:nocursor={$settings.hideCursor && idle && !$ui.settingsOpen}>
  {#if $holdings.length}
    {#if vm.rows.length}
      <View rows={vm.rows} totals={vm.totals} settings={$settings} {theme} />
    {:else}
      <div class="empty"><p class="muted">Nothing matches the current filters.</p>
        <button class="btn" onclick={() => onKey({ key: '0', target: document.body })}>Show all (0)</button></div>
    {/if}
  {:else}
    <div class="empty">
      <div class="logo" aria-hidden="true"><span></span><span></span><span></span></div>
      <p>No holdings yet.</p>
      <button class="btn primary" onclick={() => openSettings('import')}>Import holdings</button>
      <p class="muted small">Zerodha · Groww · Upstox · INDmoney · CSV · CAS PDF · or add holdings manually</p>
    </div>
  {/if}

  {#if $settings.showSummary && $holdings.length}
    <Summary totals={vm.totals} filtered={vm.filtered} settings={$settings} market={$market} />
  {/if}

  {#if $holdings.length}<QuickFilter holdings={$holdings} hidden={gearHidden} />{/if}

  <button class="gear" class:hidden={gearHidden} onclick={() => openSettings()} aria-label="Settings" title="Settings (s)">
    <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  </button>

  {#if $ui.settingsOpen}
    <SettingsPanel {config} {enriched} />
  {/if}
  {#if $ui.importPreview}
    <ImportPreview preview={$ui.importPreview} />
  {/if}
  {#if showHotkeys}
    <HotkeysOverlay />
  {/if}
  {#if $ui.toast}
    <div class="toast" class:err={$ui.toast.kind === 'error'} role="status">{$ui.toast.msg}</div>
  {/if}
</main>

<style>
  main { position: fixed; inset: 0; }
  main.nocursor, main.nocursor :global(*) { cursor: none !important; }
  .gear {
    position: fixed; top: 8px; right: 8px; z-index: 25; width: 36px; height: 36px; display: grid; place-items: center;
    border-radius: 50%; border: none; color: var(--text);
    background: color-mix(in srgb, var(--bg) 65%, transparent); backdrop-filter: blur(6px);
    opacity: .85; transition: opacity .4s ease;
  }
  .gear:hover { opacity: 1; }
  .gear.hidden { opacity: 0; pointer-events: none; }
  .empty { height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 10px; text-align: center; padding: 16px; }
  .logo { display: grid; grid-template-columns: 3fr 2fr; grid-template-rows: 1fr 1fr; gap: 3px; width: 72px; height: 56px; margin-bottom: 8px; }
  .logo span { background: var(--profit); border-radius: var(--radius); }
  .logo span:first-child { grid-row: span 2; }
  .logo span:nth-child(2) { background: var(--loss); }
  .toast {
    position: fixed; left: 50%; top: 14px; transform: translateX(-50%); z-index: 50; padding: 8px 14px;
    background: var(--surface); color: var(--text); border-left: 3px solid var(--accent); border-radius: var(--radius);
    box-shadow: 0 8px 24px rgba(0, 0, 0, .35); max-width: calc(100vw - 32px);
  }
  .toast.err { border-left-color: var(--loss); }
</style>
