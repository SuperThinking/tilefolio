<script>
  import { api, apiUrl } from '../api.js';
  import { CONNECTORS, forgetKeys, redirectUri, savedKeys, startConnect } from '../brokers.js';
  import { brokerKeys, toast, ui } from '../stores/state.js';

  let { config } = $props();

  let selected = $state(null);       // broker preset id | 'cas' | 'request'
  let busy = $state(false);
  let dragging = $state(false);
  let casPassword = $state('');
  let casFile = $state(null);
  let reqName = $state('');
  let reqNote = $state('');
  let keys = $state({});
  let remember = $state(false);
  let showKeys = $state(false);

  const brokers = $derived(config?.brokers || []);
  const preset = $derived(brokers.find((b) => b.id === selected));

  function select(id) {
    selected = selected === id ? null : id;
    showKeys = false;
    const p = brokers.find((b) => b.id === id);
    const c = p?.connect?.[0];
    keys = c ? { ...(savedKeys(c) || {}) } : {};
    remember = !!(c && $brokerKeys[c]);
  }

  function preview(result, label) {
    ui.update((u) => ({ ...u, importPreview: { ...result, label } }));
  }

  async function uploadFile(file) {
    if (!file || !selected) return;
    busy = true;
    try {
      preview(await api.importFile(file, selected), preset?.label || 'File');
    } catch (e) { toast(e.message, 'error'); }
    finally { busy = false; }
  }

  function onDrop(e) {
    e.preventDefault();
    dragging = false;
    const f = e.dataTransfer?.files?.[0];
    if (selected === 'cas') casFile = f; else uploadFile(f);
  }

  async function uploadCas() {
    if (!casFile) return toast('Choose your CAS PDF first', 'error');
    busy = true;
    try {
      preview(await api.importCas(casFile, casPassword), 'CAS statement');
      casPassword = '';
    } catch (e) { toast(e.message, 'error'); }
    finally { busy = false; }
  }

  async function sendRequest() {
    if (!reqName.trim()) return toast('Which broker?', 'error');
    try {
      await api.requestBroker(reqName.trim(), reqNote.trim());
      toast('Thanks — request recorded');
      reqName = ''; reqNote = ''; selected = null;
    } catch (e) { toast(e.message, 'error'); }
  }

  function connect(id) {
    try { startConnect(id, keys, remember); } catch (e) { toast(e.message, 'error'); }
  }

  function copy(text) {
    navigator.clipboard?.writeText(text).then(() => toast('Copied'), () => {});
  }
</script>

<div class="stack">
  <p class="muted small" style="margin:0">
    Pick where your holdings live. Re-importing from the same broker <b>replaces</b> that broker's holdings (re-sync).
    Files are parsed on the server and not stored.
  </p>

  <div class="grid">
    {#each brokers as b (b.id)}
      <button class="tile" class:sel={selected === b.id} onclick={() => select(b.id)}>
        <span class="name">{b.label}</span>
        <span class="muted small">{b.connect.length ? 'File · API key' : 'File'}</span>
      </button>
    {/each}
    <button class="tile" class:sel={selected === 'cas'} onclick={() => select('cas')}>
      <span class="name">Mutual funds (CAS)</span>
      <span class="muted small">CAMS / KFintech PDF</span>
    </button>
    <button class="tile dashed" class:sel={selected === 'request'} onclick={() => select('request')}>
      <span class="name">+ Request a broker</span>
      <span class="muted small">Not listed? Tell us</span>
    </button>
  </div>

  {#if preset}
    <section class="card stack">
      <h3>{preset.label}: export &amp; upload</h3>
      <ol class="small">{#each preset.steps as s}<li>{s}</li>{/each}</ol>
      <p class="muted small" style="margin:0">Menu paths change from time to time. Treat these steps as approximate.</p>
      {#if selected === 'generic'}
        <a class="btn" href={apiUrl('/api/import/template.csv')} download>Download template CSV</a>
      {/if}
      <label
        class="drop" class:drag={dragging}
        ondragover={(e) => { e.preventDefault(); dragging = true; }}
        ondragleave={() => (dragging = false)}
        ondrop={onDrop}
      >
        <input type="file" accept=".csv,.xlsx,.xlsm,.txt" class="sr-only" disabled={busy} onchange={(e) => uploadFile(e.currentTarget.files[0])} />
        {busy ? 'Parsing…' : 'Drop CSV / XLSX here or click to choose'}
      </label>

      {#each preset.connect as cid}
        {@const c = CONNECTORS[cid]}
        <div class="byok stack">
          <button class="linklike" onclick={() => (showKeys = !showKeys)}>
            {showKeys ? '▾' : '▸'} Sync directly with your own {c.label} key (advanced)
          </button>
          {#if showKeys}
            <p class="small muted" style="margin:0">
              {c.help} Brokers require each user to have their own API app. Your keys stay in this browser.
              They only pass through our server for the token exchange and are never saved there.
              You'll need to log in again each day, because broker sessions expire overnight.
            </p>
            <div class="row small">
              Redirect URL: <code>{redirectUri(cid)}</code>
              <button class="btn small" onclick={() => copy(redirectUri(cid))}>Copy</button>
            </div>
            {#each c.fields as [f, label]}
              <label class="f">{label}
                <input class="ctl" type={f.includes('secret') ? 'password' : 'text'} autocomplete="off" bind:value={keys[f]} />
              </label>
            {/each}
            <label class="row small"><input type="checkbox" bind:checked={remember} /> Remember on this device (stored in localStorage)</label>
            <div class="row">
              <button class="btn primary" onclick={() => connect(cid)}>Connect &amp; sync</button>
              {#if $brokerKeys[cid]}<button class="btn danger" onclick={() => { forgetKeys(cid); keys = {}; remember = false; }}>Forget keys</button>{/if}
            </div>
          {/if}
        </div>
      {/each}
    </section>
  {:else if selected === 'cas'}
    <section class="card stack">
      <h3>Consolidated Account Statement</h3>
      <ol class="small">
        <li>Request a <b>Detailed</b> CAS from camsonline.com (CAS - CAMS+KFintech) or mfcentral.com. It covers every AMC.</li>
        <li>Set a password when requesting. It's often your PAN in capitals.</li>
        <li>Upload the PDF and enter the password. We read units and cost per scheme, then discard the file.</li>
      </ol>
      <p class="small warn" style="margin:0">A CAS contains your PAN and folio numbers. It is parsed in memory and never stored or logged.</p>
      <label class="drop" class:drag={dragging}
        ondragover={(e) => { e.preventDefault(); dragging = true; }}
        ondragleave={() => (dragging = false)}
        ondrop={onDrop}>
        <input type="file" accept="application/pdf,.pdf" class="sr-only" onchange={(e) => (casFile = e.currentTarget.files[0])} />
        {casFile ? casFile.name : 'Drop CAS PDF here or click to choose'}
      </label>
      <div class="row">
        <input class="ctl" type="password" placeholder="PDF password" autocomplete="off" bind:value={casPassword} />
        <button class="btn primary" disabled={busy} onclick={uploadCas}>{busy ? 'Parsing…' : 'Import funds'}</button>
      </div>
    </section>
  {:else if selected === 'request'}
    <section class="card stack">
      <h3>Request a broker</h3>
      <input class="ctl" placeholder="Broker / platform name (e.g. Angel One, Dhan, Vested)" bind:value={reqName} />
      <textarea class="ctl" rows="3" placeholder="Anything else? (optional)" bind:value={reqNote}></textarea>
      <div><button class="btn primary" onclick={sendRequest}>Send request</button></div>
      <p class="muted small" style="margin:0">Until then, use <b>Other / template</b>. Any CSV with symbol/ISIN, qty and avg price works.</p>
    </section>
  {/if}
</div>

<style>
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 8px; }
  .tile {
    display: flex; flex-direction: column; align-items: flex-start; gap: 2px; padding: 12px;
    background: var(--surface-2); border: 1px solid transparent; border-radius: var(--radius); text-align: left;
  }
  .tile:hover, .tile.sel { border-color: var(--accent); }
  .tile.dashed { border-style: dashed; border-color: color-mix(in srgb, var(--muted) 50%, transparent); }
  .name { font-weight: 600; }
  .card { padding: 12px; background: var(--surface-2); border-radius: var(--radius); }
  ol { margin: 0; padding-left: 18px; display: flex; flex-direction: column; gap: 4px; }
  .drop {
    display: block; padding: 22px; text-align: center; border: 1.5px dashed color-mix(in srgb, var(--muted) 55%, transparent);
    border-radius: var(--radius); cursor: pointer; color: var(--muted);
  }
  .drop.drag, .drop:hover { border-color: var(--accent); color: var(--text); }
  .byok { border-top: 1px solid color-mix(in srgb, var(--muted) 20%, transparent); padding-top: 10px; }
  .linklike { background: none; border: none; padding: 0; color: var(--accent); text-align: left; }
  .f { display: flex; flex-direction: column; font-size: 11px; color: var(--muted); gap: 2px; }
  code { background: var(--surface); padding: 2px 6px; border-radius: 3px; word-break: break-all; }
  a.btn { text-decoration: none; display: inline-block; width: fit-content; }
</style>
