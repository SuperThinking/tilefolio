<script>
  import { account, push, renderGoogleButton, resolveConflict, signOut } from '../sync.js';
  import { ago } from '../format.js';

  let btn = $state(null);

  $effect(() => {
    if (btn && !$account.user && $account.clientId) renderGoogleButton(btn).catch(() => {});
  });
</script>

<div class="stack">
  <p class="small muted" style="margin:0">
    Tilefolio works without an account. Your holdings, settings and themes are saved in this browser.
    Sign in to back them up and use them on other devices. Broker API keys are never synced.
  </p>

  {#if !$account.clientId}
    <p class="small warn">Sign-in isn't configured on this server. Set TF_GOOGLE_CLIENT_ID to enable it.</p>
  {:else if !$account.user}
    <div bind:this={btn}></div>
  {:else}
    <div class="card stack">
      <div><b>{$account.user.name || $account.user.email}</b> <span class="muted small">{$account.user.email}</span></div>
      <div class="small muted">
        {$account.syncing ? 'Syncing…' : `Last synced ${ago($account.lastSync)}`}
      </div>
      <div class="row">
        <button class="btn" onclick={push}>Sync now</button>
        <button class="btn danger" onclick={signOut}>Sign out</button>
      </div>
    </div>
  {/if}

  {#if $account.conflict}
    <div class="card stack">
      <b>This device and your cloud backup differ.</b>
      <span class="small muted">The cloud copy was saved {ago($account.conflict.updatedAt)} with {$account.conflict.state?.holdings?.length ?? 0} holdings.</span>
      <div class="row">
        <button class="btn primary" onclick={() => resolveConflict(true)}>Use cloud copy</button>
        <button class="btn" onclick={() => resolveConflict(false)}>Keep this device (overwrite cloud)</button>
      </div>
    </div>
  {/if}
</div>

<style>
  .card { padding: 12px; background: var(--surface-2); border-radius: var(--radius); }
</style>
