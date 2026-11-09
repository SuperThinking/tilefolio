<script>
  // Transparent cheat sheet shown while Tab is held (see App.svelte).
  import { HOTKEYS } from '../hotkeys.js';
</script>

<div class="overlay" role="dialog" aria-label="Keyboard shortcuts">
  <div class="sheet">
    <h2>Keyboard shortcuts</h2>
    <div class="cols">
      {#each HOTKEYS as [section, keys]}
        <section>
          <h3>{section}</h3>
          {#each keys as [key, label]}
            <div class="row"><kbd>{key}</kbd><span>{label}</span></div>
          {/each}
        </section>
      {/each}
    </div>
    <p class="hint">Release Tab to close</p>
  </div>
</div>

<style>
  .overlay {
    position: fixed; inset: 0; z-index: 60; display: grid; place-items: center; padding: 16px;
    background: color-mix(in srgb, var(--bg) 35%, transparent); pointer-events: none;
    animation: fade .12s ease-out;
  }
  @keyframes fade { from { opacity: 0; } }
  .sheet {
    width: min(720px, 100%); max-height: calc(100vh - 32px); overflow: auto; padding: 20px 24px;
    background: color-mix(in srgb, var(--surface) 72%, transparent); backdrop-filter: blur(10px);
    border: 1px solid color-mix(in srgb, var(--muted) 30%, transparent); border-radius: calc(var(--radius) + 6px);
    box-shadow: 0 20px 60px rgba(0, 0, 0, .35); color: var(--text);
  }
  h2 { margin: 0 0 12px; font-size: 16px; }
  .cols { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 8px 28px; }
  section { margin-bottom: 8px; }
  .row { display: flex; gap: 12px; align-items: baseline; padding: 3px 0; font-size: 13px; }
  kbd {
    flex: 0 0 auto; min-width: 28px; text-align: center; padding: 2px 7px; font-family: var(--font); font-size: 12px;
    border-radius: 4px; border: 1px solid color-mix(in srgb, var(--muted) 50%, transparent);
    border-bottom-width: 2px; background: color-mix(in srgb, var(--surface-2) 80%, transparent);
  }
  .hint { margin: 10px 0 0; font-size: 11px; color: var(--muted); text-align: center; }
</style>
