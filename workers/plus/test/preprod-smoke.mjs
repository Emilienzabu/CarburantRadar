import assert from 'node:assert/strict';
import {setTimeout} from 'node:timers/promises';

const origin = 'http://127.0.0.1:8789';
let index;
for (let retry = 0; retry < 30; retry++) {
  try { index = await fetch(origin + '/france/', {signal: AbortSignal.timeout(1500)}); }
  catch { await setTimeout(1000); }
  if (index?.ok) break;
}
assert.equal(index?.status, 200);
assert.match(index.headers.get('x-robots-tag'), /noindex/);
const html = await index.text();
assert.match(html, /var PROXY=location.origin;/);
assert.doesNotMatch(html, /googlesyndication\.com|googletagmanager\.com|track\.js|google-adsense-account/);
assert.equal((await fetch(origin + '/manifest.json').then(response => response.json())).start_url, './france/');
const post = (path, body = {}, token) => fetch(origin + path, {method: 'POST',
  body: JSON.stringify(body), headers: {'Content-Type': 'application/json', ...(token && {Authorization: 'Bearer ' + token})}});
assert.equal((await post('/plus/status')).status, 401);
assert.equal((await post('/login', {email: 'real@example.com', password: 'local-fixture-never-used-elsewhere'})).status, 401);
const login = await post('/login', {email: 'monthly@carburantradar.invalid', password: 'local-fixture-never-used-elsewhere'});
assert.equal(login.status, 200);
const {token} = await login.json();
const status = await post('/plus/status', {credits: 999, plus: {active: true}}, token).then(response => response.json());
assert.equal(status.credits, 5);
assert.equal(status.plus.active, false);
assert.deepEqual(status.rewards, {mode: 'simulation'});
assert.equal(status.billing, undefined);
assert.equal((await post('/plus/reward', {}, token)).status, 404);
assert.equal((await post('/plus/stripe/webhook')).status, 400);
assert.equal((await post('/logout', {token})).status, 200);
assert.equal((await post('/plus/status', {}, token)).status, 401);
console.log('Préproduction locale vérifiée : PWA, comptes de test, Plus, webhook et simulation fermée.');
