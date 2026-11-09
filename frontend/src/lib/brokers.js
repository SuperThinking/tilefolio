import { get } from 'svelte/store';
import { api } from './api.js';
import { readStorage, writeStorage } from './stores/persisted.js';
import { brokerKeys } from './stores/state.js';

/**
 * Bring-your-own-key broker sync. Each user registers their own developer app with the broker
 * (multi-user broker apps need broker approval) and sets the redirect URL to
 * `${origin}/connect/<broker>`. Keys stay in this browser: localStorage if "remember" is ticked,
 * otherwise sessionStorage just long enough to survive the OAuth redirect.
 */
export const CONNECTORS = {
  kite: {
    label: 'Zerodha Kite Connect',
    fields: [['api_key', 'API key'], ['api_secret', 'API secret']],
    help: 'Create a free "Personal" app at developers.kite.trade → set its Redirect URL to the value below.',
    loginUrl: (k) => `https://kite.zerodha.com/connect/login?v=3&api_key=${encodeURIComponent(k.api_key)}`,
    async exchange(params, k) {
      if (params.get('status') && params.get('status') !== 'success') throw new Error('Kite login was cancelled');
      return api.kiteHoldings({ api_key: k.api_key, api_secret: k.api_secret, request_token: params.get('request_token') || '' });
    },
  },
  upstox: {
    label: 'Upstox API',
    fields: [['client_id', 'API key (client id)'], ['client_secret', 'API secret']],
    help: 'Create an app at account.upstox.com/developer/apps → set its Redirect URL to the value below.',
    loginUrl: (k) =>
      `https://api.upstox.com/v2/login/authorization/dialog?response_type=code&client_id=${encodeURIComponent(k.client_id)}&redirect_uri=${encodeURIComponent(redirectUri('upstox'))}`,
    async exchange(params, k) {
      const code = params.get('code');
      if (!code) throw new Error('Upstox login was cancelled');
      return api.upstoxHoldings({ client_id: k.client_id, client_secret: k.client_secret, code, redirect_uri: redirectUri('upstox') });
    },
  },
};

// BASE_URL is '/' normally, '/<repo>/' on GitHub Pages (set via VITE_BASE at build time).
const BASE_PATH = import.meta.env.BASE_URL || '/';
export const redirectUri = (id) => `${location.origin}${BASE_PATH}connect/${id}`;

export function savedKeys(id) {
  return get(brokerKeys)[id] || readStorage(`tf.pendingKeys.${id}`, 'session') || null;
}

export function startConnect(id, keys, remember) {
  const c = CONNECTORS[id];
  for (const [f, label] of c.fields) if (!keys[f]?.trim()) throw new Error(`${label} is required`);
  if (remember) brokerKeys.update((b) => ({ ...b, [id]: keys }));
  else {
    brokerKeys.update((b) => { const { [id]: _, ...rest } = b; return rest; });
    writeStorage(`tf.pendingKeys.${id}`, keys, 'session');
  }
  location.href = c.loginUrl(keys);
}

export function forgetKeys(id) {
  brokerKeys.update((b) => { const { [id]: _, ...rest } = b; return rest; });
  writeStorage(`tf.pendingKeys.${id}`, null, 'session');
}

/** Called on app load. If we're on /connect/<id>?..., finish the OAuth exchange. */
export async function handleRedirect() {
  const rel = location.pathname.startsWith(BASE_PATH) ? location.pathname.slice(BASE_PATH.length - 1) : location.pathname;
  const m = rel.match(/^\/connect\/(\w+)/);
  if (!m || !CONNECTORS[m[1]]) return null;
  const id = m[1];
  const params = new URLSearchParams(location.search);
  history.replaceState(null, '', BASE_PATH);  // drop one-time tokens from the URL bar & history
  const keys = savedKeys(id);
  writeStorage(`tf.pendingKeys.${id}`, null, 'session');
  if (!keys) throw new Error('Broker keys not found in this browser — enter them again in Settings → Import.');
  return CONNECTORS[id].exchange(params, keys);
}
