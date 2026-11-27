import {DurableObject} from 'cloudflare:workers';
import plus, {PlusState} from './index.mjs';
import {nearby} from './advanced.mjs';
import {forwardPlus} from './proxy.mjs';

export {PlusState};
const headers = {'Cache-Control': 'no-store', 'X-Robots-Tag': 'noindex, nofollow'};
const json = (body, status = 200) => Response.json(body, {status, headers});
const dataDefaults = () => ({favs: {}, names: {}, reps: [], prefs: {}});
const encoder = new TextEncoder();

async function passwordMatches(input, password) {
  if (typeof input !== 'string' || input.length > 200 || typeof password !== 'string' || password.length < 24) return false;
  const [a, b] = await Promise.all([input, password].map(value =>
    crypto.subtle.digest('SHA-256', encoder.encode(value)).then(hash => new Uint8Array(hash))));
  return a.reduce((difference, value, index) => difference | (value ^ b[index]), 0) === 0;
}

export class PreviewAccounts extends DurableObject {
  async fetch(request) {
    const storage = this.ctx.storage;
    const path = new URL(request.url).pathname;
    const now = Date.now();
    const {email, password, token, data} = await request.json();
    if (path === '/login') {
      if (!/^[a-z0-9._-]{1,48}@carburantradar\.invalid$/.test(email || '') ||
          !await passwordMatches(password, this.env.PREVIEW_LOGIN_PASSWORD)) {
        return json({error: 'Utilise une adresse de test @carburantradar.invalid et le mot de passe de préproduction.'}, 401);
      }
      const session = crypto.randomUUID();
      const account = await storage.transaction(async txn => {
        const key = 'user:' + email;
        const saved = await txn.get(key) || {email, cree: now, data: dataDefaults()};
        await txn.put(key, saved);
        await txn.put('session:' + session, {email, expires: now + 86400000});
        return saved;
      });
      if (!await storage.getAlarm()) await storage.setAlarm(now + 86400000);
      return json({ok: true, token: session, data: account.data});
    }
    if (path === '/user') return json(await storage.get('user:' + email) || null);
    if (typeof token !== 'string' || !/^[a-f0-9-]{36}$/.test(token)) return json({error: 'Connexion de test requise.'}, 401);
    const key = 'session:' + token;
    const session = await storage.get(key);
    if (!session || session.expires <= now) return json({error: 'Connexion de test requise.'}, 401);
    if (path === '/logout') {
      await storage.delete(key);
      return json({ok: true});
    }
    if (path === '/identity') return json({email: session.email});
    const accountKey = 'user:' + session.email;
    const account = await storage.get(accountKey);
    if (path === '/save') {
      if (!data || Array.isArray(data) || typeof data !== 'object' || JSON.stringify(data).length > 16000) {
        return json({error: 'Données invalides.'}, 400);
      }
      await storage.put(accountKey, {...account, data});
    }
    return json({ok: true, email: account.email, data: path === '/save' ? data : account.data});
  }

  async alarm() {
    const storage = this.ctx.storage;
    const now = Date.now();
    let startAfter;
    let next;
    for (;;) {
      const sessions = await storage.list({prefix: 'session:', startAfter, limit: 128});
      const expired = [];
      for (const [key, session] of sessions) {
        startAfter = key;
        if (session.expires <= now) expired.push(key);
        else next = Math.min(next ?? Infinity, session.expires);
      }
      if (expired.length) await storage.delete(expired);
      if (sessions.size < 128) break;
    }
    if (next) await storage.setAlarm(next);
  }
}

function tokenFrom(request) { return request.headers.get('Authorization')?.match(/^Bearer (.+)$/)?.[1]; }

export async function servePreview(request, env) {
  const url = new URL(request.url);
  const {pathname} = url;
  const call = (path, body) => env.PREVIEW_ACCOUNTS.getByName('test-only').fetch('https://accounts.internal' + path,
    {method: 'POST', body: JSON.stringify(body)});
  if (pathname.startsWith('/plus/')) {
    const bindings = {
      PLUS_ADMIN_TOKEN: env.PLUS_ADMIN_TOKEN,
      PLUS: {fetch: (input, init) => plus.fetch(new Request(input, init), env)},
      USERS: {async get(key) {
        const response = await call('/user', {email: key.slice(5)});
        const account = await response.json();
        return account && JSON.stringify(account);
      }},
    };
    const authenticate = async request => {
      const response = await call('/identity', {token: tokenFrom(request)});
      return (await response.json()).email || null;
    };
    return forwardPlus(request, bindings, headers, authenticate, () => false);
  }
  if (['/login', '/register', '/logout', '/account'].includes(pathname)) {
    const method = request.method;
    if (method === 'GET' && pathname === '/account') return call('/account', {token: tokenFrom(request)});
    if (method !== 'POST') return json({error: 'Méthode invalide.'}, 405);
    const body = await request.json().catch(() => null);
    if (!body) return json({error: 'Requête invalide.'}, 400);
    if (pathname === '/login' || pathname === '/register') {
      return call('/login', {email: typeof body.email === 'string' ? body.email.toLowerCase().trim() : '',
        password: body.password});
    }
    if (pathname === '/logout') return call('/logout', {token: body.token});
    return call('/save', {token: tokenFrom(request), data: body.data});
  }
  if (pathname === '/' && url.searchParams.has('lat') && url.searchParams.has('lon')) {
    const lat = Number(url.searchParams.get('lat'));
    const lon = Number(url.searchParams.get('lon'));
    const dist = Number(url.searchParams.get('dist') ?? 5);
    if (!Number.isFinite(lat) || Math.abs(lat) > 90 || !Number.isFinite(lon) || Math.abs(lon) > 180 ||
        !Number.isFinite(dist) || dist <= 0 || dist > 200) return json({error: 'Coordonnées invalides.'}, 400);
    try { return json({results: await nearby({lat, lon}, dist)}); }
    catch { return json({error: 'Source de prix indisponible.'}, 503); }
  }
  if (pathname === '/') return Response.redirect(new URL('/france/', url), 302);
  const asset = await env.ASSETS.fetch(request);
  const response = new Response(asset.body, asset);
  response.headers.set('X-Robots-Tag', headers['X-Robots-Tag']);
  return response;
}

export default {fetch: servePreview};
