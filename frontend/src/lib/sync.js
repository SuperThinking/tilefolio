import { get, writable } from 'svelte/store';
import { api, setSessionToken } from './api.js';
import { holdings, restore, snapshot, toast, updatedAt } from './stores/state.js';

/** Optional Google sign-in + last-write-wins backup of {holdings, settings, customThemes}. */
export const account = writable({ user: null, clientId: null, syncing: false, lastSync: 0, conflict: null });

let pushTimer = null;
let unsub = null;

export async function initAccount(clientId) {
  account.update((a) => ({ ...a, clientId }));
  try {
    const { user } = await api.me();
    if (user) await onSignedIn(user);
  } catch { /* offline or no backend */ }
}

export function loadGoogleScript() {
  return new Promise((resolve, reject) => {
    if (window.google?.accounts?.id) return resolve();
    const s = document.createElement('script');
    s.src = 'https://accounts.google.com/gsi/client';
    s.async = true;
    s.onload = () => resolve();
    s.onerror = () => reject(new Error('Could not load Google sign-in'));
    document.head.appendChild(s);
  });
}

export async function renderGoogleButton(el) {
  const { clientId } = get(account);
  if (!clientId || !el) return;
  await loadGoogleScript();
  window.google.accounts.id.initialize({
    client_id: clientId,
    callback: async ({ credential }) => {
      try {
        const { user, token } = await api.googleLogin(credential);
        setSessionToken(token);
        await onSignedIn(user);
        toast(`Signed in as ${user.email}`);
      } catch (e) { toast(e.message, 'error'); }
    },
  });
  window.google.accounts.id.renderButton(el, { theme: 'outline', size: 'medium', text: 'signin_with' });
}

async function onSignedIn(user) {
  account.update((a) => ({ ...a, user }));
  const remote = await api.getState().catch(() => null);
  const localHas = get(holdings).length > 0;
  if (remote?.state && !localHas) {
    restore(remote.state);
    updatedAt.set(remote.updatedAt);
  } else if (remote?.state && remote.updatedAt !== get(updatedAt)) {
    // Both sides have data and they differ: let the user choose (Account tab shows the prompt).
    account.update((a) => ({ ...a, conflict: remote }));
  } else {
    await push();
  }
  watch();
}

function watch() {
  unsub?.();
  unsub = updatedAt.subscribe(() => {
    clearTimeout(pushTimer);
    pushTimer = setTimeout(push, 2000);
  });
}

export async function push() {
  const a = get(account);
  if (!a.user || a.conflict) return;
  account.update((x) => ({ ...x, syncing: true }));
  try {
    await api.putState(snapshot(), get(updatedAt) || Date.now());
    account.update((x) => ({ ...x, syncing: false, lastSync: Date.now() }));
  } catch (e) {
    account.update((x) => ({ ...x, syncing: false }));
    if (e.status === 409) {
      const remote = await api.getState().catch(() => null);
      account.update((x) => ({ ...x, conflict: remote }));
    }
  }
}

export async function resolveConflict(useRemote) {
  const { conflict } = get(account);
  account.update((a) => ({ ...a, conflict: null }));
  if (useRemote && conflict?.state) {
    restore(conflict.state);
    updatedAt.set(conflict.updatedAt);
  } else {
    updatedAt.set(Math.max(Date.now(), (conflict?.updatedAt || 0) + 1));
    await push();
  }
}

export async function signOut() {
  await api.logout().catch(() => {});
  setSessionToken(null);
  unsub?.();
  window.google?.accounts?.id?.disableAutoSelect?.();
  account.update((a) => ({ ...a, user: null, conflict: null }));
}
