<script>
  import { allThemes, findTheme, makeColorScale, newThemeFrom, sanitizeTheme, textOn, THEME_KEYS } from '../themes.js';
  import { customThemes, settings, toast } from '../stores/state.js';

  const themes = $derived(allThemes($customThemes));
  const active = $derived(findTheme($settings.theme, $customThemes));
  let importText = $state('');

  const pick = (id) => settings.update((s) => ({ ...s, theme: id }));

  function duplicate(t) {
    const n = newThemeFrom(t);
    customThemes.update((c) => [...c, n]);
    pick(n.id);
  }

  function edit(key, value) {
    customThemes.update((c) => c.map((t) => (t.id === active.id ? { ...t, [key]: value } : t)));
  }

  function remove(t) {
    if (!confirm(`Delete theme "${t.name}"?`)) return;
    customThemes.update((c) => c.filter((x) => x.id !== t.id));
    if ($settings.theme === t.id) pick('terminal');
  }

  function exportTheme() {
    const { id, preset, ...t } = active;
    navigator.clipboard?.writeText(JSON.stringify(t, null, 2)).then(() => toast('Theme JSON copied'));
  }

  function importTheme() {
    try {
      const t = sanitizeTheme(JSON.parse(importText));
      customThemes.update((c) => [...c, t]);
      pick(t.id);
      importText = '';
      toast(`Imported "${t.name}"`);
    } catch (e) { toast('Invalid theme JSON: ' + e.message, 'error'); }
  }

  function swatches(t) {
    const s = makeColorScale(t, 3);
    return [-3, -1.5, -0.5, 0, 0.5, 1.5, 3].map((p) => s(p));
  }
</script>

<div class="stack">
  <div class="grid">
    {#each themes as t (t.id)}
      <button class="theme" class:sel={t.id === active.id} style="background:{t.bg};color:{t.text};font-family:{t.font}" onclick={() => pick(t.id)}>
        <div class="sw">{#each swatches(t) as c}<span style="background:{c}"></span>{/each}</div>
        <div class="tn">{t.name}</div>
      </button>
    {/each}
  </div>

  <div class="row">
    <button class="btn" onclick={() => duplicate(active)}>Duplicate "{active.name}" to customize</button>
    <button class="btn" onclick={exportTheme}>Copy JSON</button>
  </div>

  {#if !active.preset}
    <section class="card stack">
      <div class="row">
        <input class="ctl" style="flex:1" value={active.name} onchange={(e) => edit('name', e.currentTarget.value)} />
        <button class="btn danger" onclick={() => remove(active)}>Delete</button>
      </div>
      <div class="colors">
        {#each THEME_KEYS as [k, label]}
          <label class="color"><input type="color" value={active[k]} oninput={(e) => edit(k, e.currentTarget.value)} /> {label}</label>
        {/each}
      </div>
      <label class="f">Font stack <input class="ctl" value={active.font} onchange={(e) => edit('font', e.currentTarget.value)} /></label>
      <label class="f">Corner radius
        <select class="ctl" value={active.radius} onchange={(e) => edit('radius', e.currentTarget.value)}>
          {#each ['0px', '2px', '4px', '8px'] as r}<option>{r}</option>{/each}
        </select>
      </label>
      <div class="preview">
        {#each [-4, -1, -0.2, 0, 0.3, 1.2, 4] as p}
          {@const c = makeColorScale(active, 3)(p)}
          <div style="background:{c};color:{textOn(c)}">{p > 0 ? '+' : ''}{p}%</div>
        {/each}
      </div>
    </section>
  {:else}
    <p class="muted small">Preset themes are read-only. Duplicate one to make a custom theme.</p>
  {/if}

  <h3>Import theme</h3>
  <textarea class="ctl" rows="3" placeholder={'{"name":"My theme","bg":"#000000","profit":"#00ff00",...}'} bind:value={importText}></textarea>
  <div><button class="btn" onclick={importTheme} disabled={!importText.trim()}>Import</button></div>
</div>

<style>
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 8px; }
  .theme { border: 2px solid transparent; border-radius: 6px; padding: 10px; text-align: left; }
  .theme.sel { border-color: var(--accent); }
  .sw { display: flex; height: 22px; gap: 1px; margin-bottom: 6px; }
  .sw span { flex: 1; }
  .tn { font-size: 12px; font-weight: 600; }
  .card { padding: 12px; background: var(--surface-2); border-radius: var(--radius); }
  .colors { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
  .color { display: flex; align-items: center; gap: 8px; font-size: 12px; }
  .color input { width: 32px; height: 24px; padding: 0; border: none; background: none; }
  .f { display: flex; flex-direction: column; font-size: 11px; color: var(--muted); gap: 2px; }
  .preview { display: flex; gap: 2px; height: 40px; }
  .preview div { flex: 1; display: grid; place-items: center; font-size: 11px; font-weight: 600; }
</style>
