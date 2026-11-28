import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {test} from 'node:test';
import {createHmac} from 'node:crypto';
import {PlusLedger} from '../src/ledger.mjs';
import {handleRequest} from '../src/http.mjs';
import {forwardPlus} from '../src/proxy.mjs';
import {deliverExtraAlerts} from '../src/scheduled-alerts.mjs';
import {nearby} from '../src/advanced.mjs';

const start = Date.parse('2026-11-26T22:59:59Z');
const tomorrow = start + 1000;
const adminToken = 'test-secret-with-more-than-32-characters';
const alertPreview = {PLUS_ALERTS_PREVIEW: '1', PLUS_ALERTS_DELIVERY: '1'};
const fixtureAlert = {
  name: 'Travail', lat: 48.8, lon: 2.3, carburant: 'E10', rayon: 5, seuil: 3,
  sub: {endpoint: 'https://fcm.googleapis.com/fcm/send/fixture',
    keys: {p256dh: 'A'.repeat(87), auth: 'B'.repeat(22)}},
};

function ledger(db = new DatabaseSync(':memory:')) {
  const sql = {
    exec(query, ...values) {
      if (query.startsWith('\n')) return db.exec(query);
      const statement = db.prepare(query);
      if (statement.columns().length) return {toArray: () => statement.all(...values)};
      return {rowsWritten: Number(statement.run(...values).changes)};
    },
  };
  return new PlusLedger(sql, callback => {
    db.exec('BEGIN');
    try {
      const value = callback();
      db.exec('COMMIT');
      return value;
    } catch (error) {
      db.exec('ROLLBACK');
      throw error;
    }
  });
}

function request(path, body, headers = {}) {
  return new Request('https://example.test' + path, {method: 'POST', headers, body: JSON.stringify(body)});
}

test('cinq crédits une fois et un seul crédit par jour à Paris', () => {
  const store = ledger();
  assert.equal(store.status('a', start, start).credits, 5);
  assert.equal(store.claim('a', start, start).claimed, false);
  assert.equal(store.claim('a', tomorrow, start).credits, 6);
  assert.equal(store.claim('a', tomorrow + 100, start).claimed, false);
  assert.equal(store.claim('a', tomorrow + 3 * 86400000, start).credits, 7);
  assert.equal(store.status('ancien', tomorrow, start).canClaimToday, true);
  const summer = Date.parse('2026-07-26T21:59:59Z');
  assert.equal(store.claim('été', summer, summer).claimed, false);
  assert.equal(store.claim('été', summer + 1000, summer).claimed, true);
});

test('deux demandes simultanées de crédit quotidien ne donnent qu’un crédit', async () => {
  const store = ledger();
  const claim = () => handleRequest(request('/claim', {account: 'a', created: start, credits: 100}), store, adminToken, tomorrow);
  const results = await Promise.all([claim(), claim()].map(async response => (await response).json()));
  assert.equal(results.filter(result => result.claimed).length, 1);
  assert.ok(results.every(result => result.credits === 6 && !result.canClaimToday));
  assert.equal(store.history('a').length, 1);
});

test('un code temporaire affiche son échéance puis expire sans changer le solde', async () => {
  const store = ledger();
  const today = Date.parse('2026-08-31T12:00:00Z');
  const {code} = await store.issue({months: 6, maxUses: 1}, today);
  const preview = await store.preview('a', code.toLowerCase(), today);
  const end = Date.parse('2027-02-28T12:00:00Z');
  assert.deepEqual(preview, {months: 6, lifetime: false, until: end});
  assert.equal(store.status('a', today).plus.active, false);
  assert.equal((await store.redeem('a', code, today)).plus.until, end);
  assert.equal(store.status('a', end - 1).plus.active, true);
  assert.equal(store.status('a', end).plus.active, false);
  assert.equal(store.status('a', end).credits, 5);
});

test('la dernière utilisation ne peut servir qu’une fois, même en parallèle', async () => {
  const store = ledger();
  const {code} = await store.issue({months: 12, maxUses: 1}, start);
  await Promise.all(['a', 'b'].map(account => store.preview(account, code, start)));
  const results = await Promise.allSettled(['a', 'b'].map(account => store.redeem(account, code, start)));
  assert.equal(results.filter(result => result.status === 'fulfilled').length, 1);
  assert.equal(results.find(result => result.status === 'rejected').reason.code, 'code_used_up');
  const winner = results[0].status === 'fulfilled' ? 'a' : 'b';
  await assert.rejects(store.redeem(winner, code, start), {code: 'code_used'});
});

test('les codes respectent date limite, durée et accès à vie', async () => {
  const store = ledger();
  await assert.rejects(store.issue({months: 0, maxUses: 2}, start), {code: 'gift_settings_invalid'});
  const timed = await store.issue({months: 12, maxUses: 2, deadline: tomorrow}, start);
  await assert.rejects(store.redeem('a', timed.code, tomorrow), {code: 'code_expired'});
  const other = await store.issue({months: 6, maxUses: 2}, start);
  const first = await store.redeem('a', other.code, start);
  const extended = await store.redeem('a', timed.code, start);
  assert.equal(extended.plus.until, Date.parse('2028-05-26T22:59:59Z'));
  assert.ok(extended.plus.until > first.plus.until);
  const forever = await store.issue({months: null, maxUses: 1}, start);
  await store.redeem('a', forever.code, start);
  assert.deepEqual(store.status('a', Date.parse('2050-01-01')).plus, {active: true, lifetime: true, until: null});
  await assert.rejects(store.redeem('a', other.code, start), {code: 'code_used'});
});

test('le proxy ne fait confiance qu’à la session et contrôle la création des codes', async () => {
  const store = ledger();
  const kv = new Map([
    ['session:one', 'a@example.test'], ['session:two', 'a@example.test'],
    ['session:missing', 'missing@example.test'],
    ['user:a@example.test', JSON.stringify({cree: start})],
  ]);
  const env = {
    PLUS_ADMIN_TOKEN: adminToken,
    USERS: {get: async key => kv.get(key)},
    PLUS: {fetch: (url, init) => handleRequest(new Request(url, init), store, adminToken, tomorrow)},
  };
  const auth = (req, env) => env.USERS.get('session:' + req.headers.get('authorization'));
  const isAdmin = req => req.headers.get('x-admin-key') === 'authorized-test';
  const call = (path, body, headers) => forwardPlus(request('/plus/' + path, body, headers), env, {}, auth, isAdmin);
  assert.equal((await call('claim', {account: 'a', created: 1})).status, 401);
  assert.equal((await call('status', {}, {authorization: 'missing'})).status, 401);
  assert.equal((await call('issue', {months: null, maxUses: 1}, {authorization: 'one'})).status, 403);
  assert.equal((await handleRequest(request('/issue', {months: null, maxUses: 1}), store, adminToken, start)).status, 403);
  const {code} = await (await call('issue', {months: null, maxUses: 1}, {'x-admin-key': 'authorized-test'})).json();
  const claimed = await (await call('claim', {account: 'forged', created: 1}, {authorization: 'one'})).json();
  assert.equal(claimed.credits, 6);
  const redeemed = await call('redeem', {code}, {authorization: 'one'});
  assert.equal(redeemed.headers.get('cache-control'), 'no-store');
  assert.deepEqual(await (await call('status', {}, {authorization: 'two'})).json(), {
    credits: 6, canClaimToday: false, plus: {active: true, lifetime: true, until: null},
    history: [{id: 1, amount: 1, reason: 'daily', time: tomorrow}],
  });
});

test('Analyse renvoie les données côté serveur et débite après un résultat exploitable', async t => {
  const store = ledger();
  const preview = {PLUS_ANALYSIS_PREVIEW: '1'};
  const params = {fuel: 'E10', stationId: '75000001', radius: 5, period: 30};
  let upstream = [];
  t.mock.method(globalThis, 'fetch', async url => {
    const target = new URL(url);
    assert.equal(target.hostname, 'public.opendatasoft.com');
    assert.equal(target.searchParams.get('group_by'), "date_format(update,'yyyy-MM-dd') AS date");
    assert.equal(target.searchParams.get('select'), 'avg(price_e10) AS price');
    return Response.json({results: upstream});
  });
  const call = (account, confirm, now = start, env = preview) =>
    handleRequest(request('/analysis', {account, params, confirm}), store, adminToken, now, env);
  assert.equal((await call('a', true, start, {})).status, 503);
  assert.equal((await call('a', false)).status, 409);
  assert.equal((await call('a', true)).status, 422);
  assert.equal(store.status('a', start).credits, 5);
  upstream = [{date: '2026-11-26', price: 1.8}];
  const result = await (await call('a', true)).json();
  assert.equal(result.credits, 4);
  assert.equal(result.result.prices.at(-1), 1.8);
  assert.deepEqual(result.analysis, {unlocked: true, expires: start + 86400000});
  assert.equal((await (await call('a', false)).json()).credits, 4);
  assert.equal((await call('a', false, start + 86400000)).status, 409);
  store.saveStripeSubscription('sub_Analysis', 'b', {plan: 'month', status: 'active',
    until: start + 86400000, periodEnd: start + 86400000, cancelAtPeriodEnd: false}, null, start);
  assert.equal((await (await call('b', false)).json()).credits, 5);
  for (let day = 1; day <= 4; day++) store.unlockAnalysis('a', start + day * 86400000);
  assert.equal((await call('a', true, start + 5 * 86400000)).status, 409);
});

test('les stations arrivent en JSON et toute redirection du fournisseur est refusée', async () => {
  const point = {lat: 48.8566, lon: 2.3522};
  const fixtures = [{id: 94160001, geom: point, e10_prix: 1.79}];
  const result = await nearby(point, 5, async (url, options) => {
    assert.equal(new URL(url).searchParams.get('where'), "within_distance(geom,geom'POINT(2.3522 48.8566)',5000m)");
    assert.equal(options.redirect, 'manual');
    return Response.json({results: fixtures});
  });
  assert.deepEqual(result, fixtures);
  await assert.rejects(nearby(point, 5, async () => Response.redirect('https://example.test/')),
    {code: 'advanced_service_unavailable', status: 503});
});

test('une recharge confirmée vaut deux crédits et un identifiant ne compte qu’une fois', async () => {
  const store = ledger();
  const grant = (account, event, headers) =>
    handleRequest(request('/reward', {account, event}, headers), store, adminToken, start);
  assert.equal((await grant('a', 'test-1')).status, 403);
  const headers = {authorization: 'Bearer ' + adminToken};
  const parallel = await Promise.all([grant('a', 'test-1', headers), grant('a', 'test-1', headers)]);
  const sameAccount = await Promise.all(parallel.map(response => response.json()));
  const wrongAccount = await (await grant('b', 'test-1', headers)).json();
  assert.deepEqual([...sameAccount.map(result => result.credits), wrongAccount.credits], [7, 7, 5]);
  assert.equal(sameAccount.filter(result => result.rewarded).length, 1);
  assert.equal(wrongAccount.rewarded, false);
  assert.deepEqual(store.history('a').map(entry => ({...entry})), [{id: 1, amount: 2, reason: 'reward', time: start}]);
  assert.deepEqual(store.history('b'), []);
});

test('le serveur vérifie les détours, garde le résultat et refuse de débiter en cas d’échec', async t => {
  const store = ledger();
  const id = crypto.randomUUID();
  const params = {origin: {lat: 48.8, lon: 2.3}, destination: {lat: 48.9, lon: 2.4},
    fuel: 'E10', liters: 42, consumption: 6};
  let upstream = [];
  let routable = true;
  const roads = [];
  t.mock.method(globalThis, 'fetch', async url => {
    const target = new URL(url);
    if (target.hostname === 'data.economie.gouv.fr') return Response.json({results: upstream});
    roads.push(target);
    if (!routable) return Response.json({}, {status: 503});
    const best = {distance: 5000, duration: 600, geometry: {coordinates: [[2.3, 48.8], [2.4, 48.9]]}};
    return Response.json(target.hostname === 'data.geopf.fr' ? best : {routes: [best]});
  });
  const call = (account, operation, env = {PLUS_TRIP_PREVIEW: '1'}, values = {}) =>
    handleRequest(request('/trip', {account, id: operation, confirm: true, params, ...values}), store, adminToken, start, env);
  assert.equal((await call('a', id, {})).status, 503);
  assert.equal((await call('a', 'unknown')).status, 400);
  routable = false;
  assert.equal((await call('a', id)).status, 503);
  assert.equal(store.status('a', start).credits, 5);
  routable = true;
  assert.equal((await call('a', id)).status, 422);
  assert.equal(store.status('a', start).credits, 5);
  upstream = [
    {id: '1', adresse: 'A', geom: {lat: 48.81, lon: 2.31}, e10_prix: 1.7},
    {id: '2', adresse: 'B', geom: {lat: 48.85, lon: 2.35}, e10_prix: 1.8},
  ];
  assert.equal((await call('a', id, undefined, {confirm: false})).status, 409);
  const completed = await (await call('a', id)).json();
  assert.equal(completed.credits, 4);
  assert.equal(completed.result.verified, 2);
  assert.equal(completed.result.choices[0].station.id, '1');
  assert.equal(completed.result.choices.at(-1).station.id, '2');
  assert.equal(roads[0].origin, 'https://data.geopf.fr');
  assert.equal(roads[0].searchParams.get('start'), '2.3,48.8');
  assert.equal(roads[0].searchParams.get('end'), '2.4,48.9');
  assert.equal(roads[0].searchParams.get('timeUnit'), 'second');
  assert.ok(roads.some(url => url.searchParams.get('intermediates') === '2.31,48.81'));
  assert.deepEqual(await (await call('a', id, undefined, {confirm: false})).json(), completed);
  assert.equal((await call('a', id, undefined, {params: {...params, liters: 43}})).status, 409);
  store.saveStripeSubscription('sub_Trip', 'b', {plan: 'year', status: 'active',
    until: start + 86400000, periodEnd: start + 86400000, cancelAtPeriodEnd: false}, null, start);
  const configured = {PLUS_TRIP_PREVIEW: '1', PLUS_OSRM_URL: 'https://routes.example/route/v1/driving/'};
  assert.equal((await call('b', id, configured, {confirm: false})).status, 200);
  assert.ok(roads.some(url => url.hostname === 'routes.example' && url.pathname.includes('2.31,48.81')));
  assert.equal(store.status('b', start).credits, 5);
});

test('les alertes supplémentaires sont privées, renouvelables et expirent après sept jours', async () => {
  const store = ledger();
  const id = crypto.randomUUID();
  const endpoint = (action, account, now, body = {}, env = alertPreview) =>
    handleRequest(request('/alerts/' + action, {account, id, ...body}), store, adminToken, now, env);
  assert.equal((await endpoint('add', 'a', start, {settings: fixtureAlert}, {})).status, 503);
  const invalid = {...fixtureAlert, sub: {...fixtureAlert.sub, endpoint: 'https://unrelated.example.test/'}};
  assert.equal((await endpoint('add', 'a', start, {settings: invalid})).status, 400);
  assert.equal(store.status('a', start).credits, 5);
  assert.equal((await endpoint('add', 'a', start, {settings: fixtureAlert})).status, 409);
  assert.equal(store.status('a', start).credits, 5);
  const create = async () => (await endpoint('add', 'a', start, {settings: fixtureAlert, confirm: true})).json();
  const results = await Promise.all([create(), create()]);
  assert.equal(results[0].alerts.length, 1);
  assert.equal(results[1].credits, 3);
  assert.equal(results[0].alerts[0].sub, undefined);
  assert.equal((await endpoint('add', 'a', start, {id: crypto.randomUUID(), settings: fixtureAlert})).status, 409);
  assert.equal((await endpoint('renew', 'b', start)).status, 404);
  const ends = results[0].alerts[0].until;
  assert.equal(ends, start + 7 * 86400000);
  assert.equal(store.alerts('a', ends)[0].active, false);
  assert.equal((await (await endpoint('renew', 'a', ends - 1)).json()).credits, 3);
  assert.equal((await endpoint('renew', 'a', ends)).status, 409);
  assert.equal(store.status('a', ends).credits, 3);
  assert.equal((await (await endpoint('renew', 'a', ends, {confirm: true})).json()).credits, 1);
  assert.equal((await (await endpoint('renew', 'a', ends)).json()).credits, 1);
  assert.equal((await endpoint('remove', 'b', ends)).status, 200);
  assert.equal((await (await endpoint('remove', 'a', ends)).json()).alerts.length, 0);
  assert.equal((await endpoint('add', 'a', ends, {settings: fixtureAlert})).status, 404);
  const code = await store.issue({months: 6, maxUses: 1}, start);
  const access = await store.redeem('b', code.code, start);
  const plusAlert = await (await endpoint('add', 'b', start, {settings: fixtureAlert})).json();
  assert.equal(plusAlert.credits, 5);
  assert.equal(plusAlert.alerts[0].until, null);
  assert.equal(store.alerts('b', access.plus.until)[0].active, false);
});

test('le traitement planifié envoie une fois par jour et transmet la station cible', async () => {
  const store = ledger();
  const id = crypto.randomUUID();
  store.addAlert('a', id, fixtureAlert, start, null, true);
  let now = start;
  const env = {...alertPreview, PLUS_ADMIN_TOKEN: adminToken,
    PLUS: {fetch: (url, init) => handleRequest(new Request(url, init), store, adminToken, now, alertPreview)}};
  const sent = [];
  let expired = false;
  const send = async (...args) => {sent.push(args); return {expire: expired};};
  let rows = [{id: '75000', adresse: 'Station A', geom: {lat: 48.8, lon: 2.3}, e10_prix: 1.8}];
  const load = async () => rows;
  await deliverExtraAlerts(env, send, load);
  assert.equal(sent.length, 0);
  rows.push({id: '75001', adresse: 'Station B', geom: {lat: 48.81, lon: 2.31}, e10_prix: 2});
  await Promise.all([deliverExtraAlerts(env, send, load), deliverExtraAlerts(env, send, load)]);
  assert.equal(sent.length, 1);
  assert.deepEqual(sent[0][4], {stationId: '75000', lat: 48.8, lon: 2.3, carburant: 'E10', country: 'france'});
  now = tomorrow;
  expired = true;
  await deliverExtraAlerts(env, send, load);
  assert.equal(sent.length, 2);
  assert.equal(store.alerts('a', now).length, 0);
  assert.equal((await handleRequest(request('/scheduled/alerts', {}), store, adminToken, now, alertPreview)).status, 403);
});

test('Stripe de test vérifie les prix, évite les doublons et réserve l’accès aux paiements confirmés', async t => {
  const store = ledger();
  const account = 'a'.repeat(64);
  const annualAccount = 'b'.repeat(64);
  const settings = {PLUS_BILLING_TEST: '1', STRIPE_SECRET_KEY: 'sk_test_fixture', STRIPE_WEBHOOK_SECRET: 'whsec_fixture',
    STRIPE_MONTHLY_PRICE: 'price_Month', STRIPE_YEARLY_PRICE: 'price_Year',
    STRIPE_RETURN_URL: 'https://preprod.example.test/france/'};
  const calls = [];
  let existing = [];
  let subscription = {id: 'sub_Test', livemode: false, customer: 'cus_Test', status: 'active',
    metadata: {carburantradar_account: account}, latest_invoice: {status: 'paid'},
    items: {data: [{price: {id: 'price_Month'}, current_period_end: Math.floor(start / 1000) + 3600}]}};
  t.mock.method(globalThis, 'fetch', async (uri, options) => {
    const path = new URL(uri).pathname;
    calls.push({path, ...options});
    if (path === '/v1/prices/price_Month') return Response.json({livemode: false, active: true, currency: 'eur',
      unit_amount: 100, recurring: {interval: 'month', interval_count: 1}});
    if (path === '/v1/prices/price_Year') return Response.json({livemode: false, active: true, currency: 'eur',
      unit_amount: 1000, recurring: {interval: 'year', interval_count: 1}});
    if (path === '/v1/customers') return Response.json({
      id: options.body.get('metadata[carburantradar_account]') === account ? 'cus_Test' : 'cus_Second',
    });
    if (path === '/v1/subscriptions') return Response.json({data: existing});
    if (path === '/v1/checkout/sessions') return Response.json({url: 'https://checkout.stripe.com/test'});
    if (path === '/v1/billing_portal/sessions') return Response.json({url: 'https://billing.stripe.com/test'});
    if (path === '/v1/subscriptions/' + subscription.id) return Response.json(subscription);
    throw new Error('Stripe route inattendue : ' + path);
  });
  const call = (path, payload = {}, env = settings) =>
    handleRequest(request(path, {account, ...payload}), store, adminToken, start, env);
  assert.equal((await call('/checkout', {plan: 'month'}, {...settings, PLUS_BILLING_TEST: '0'})).status, 503);
  assert.equal((await call('/checkout', {plan: 'month'}, {...settings, STRIPE_SECRET_KEY: 'sk_live_fixture'})).status, 503);
  assert.equal((await call('/checkout', {plan: 'month'})).status, 200);
  assert.equal((await call('/checkout', {plan: 'month'})).status, 200);
  assert.equal((await call('/checkout', {plan: 'year'})).status, 409);
  const attempts = calls.filter(item => item.path === '/v1/checkout/sessions');
  assert.equal(attempts[0].headers['Idempotency-Key'], attempts[1].headers['Idempotency-Key']);
  assert.equal(attempts[0].body.get('line_items[0][price]'), 'price_Month');
  assert.equal(attempts[0].body.get('success_url'), settings.STRIPE_RETURN_URL + '?plus=retour');
  assert.equal(store.status(account, start).plus.active, false);
  existing = [{id: 'sub_Test', metadata: {carburantradar_account: account}, status: 'active'}];
  assert.equal((await call('/checkout', {plan: 'month'})).status, 409);
  assert.equal(store.status(account, start).plus.active, true);
  const monthlyDetails = (await (await call('/status')).json()).billing.subscription;
  assert.equal(monthlyDetails.plan, 'month');
  existing = [];
  let eventSequence = 0;
  const event = (type, object, {live = false, skew = 0, tampered = false, id = 'evt_' + ++eventSequence} = {}) => {
    const raw = JSON.stringify({id, api_version: '2026-11-18.endive', livemode: live, type, data: {object}}, null, 2);
    const timestamp = Math.floor(start / 1000) + skew;
    const hmac = createHmac('sha256', settings.STRIPE_WEBHOOK_SECRET).update(timestamp + '.' + raw).digest('hex');
    return new Request('https://example.test/plus/stripe/webhook', {method: 'POST',
      headers: {'Stripe-Signature': 't=' + timestamp + ',v1=' + hmac}, body: tampered ? raw + ' ' : raw});
  };
  const bindings = {PLUS: {fetch: (url, init) => handleRequest(new Request(url, init), store, adminToken, start, settings)}};
  const webhook = (type, object, options) =>
    forwardPlus(event(type, object, options), bindings, {});
  const invoice = id => ({object: 'invoice', parent: {
    type: 'subscription_details', subscription_details: {subscription: id},
  }});
  for (const options of [{live: true}, {skew: 301}, {tampered: true}]) {
    assert.equal((await webhook('customer.subscription.created', subscription, options)).status, 400);
  }
  subscription.latest_invoice.status = 'open';
  await webhook('customer.subscription.created', subscription);
  assert.equal(store.status(account, start).plus.active, true);
  subscription.latest_invoice.status = 'paid';
  const duplicate = () => webhook('checkout.session.completed', {mode: 'subscription', subscription: 'sub_Test'}, {id: 'evt_checkout'});
  const before = calls.length;
  assert.deepEqual((await Promise.all([duplicate(), duplicate()])).map(response => response.status), [200, 200]);
  assert.equal(calls.length - before, 1);
  assert.equal(store.status(account, start).plus.active, true);
  const paidUntil = store.status(account, start).plus.until;
  assert.equal((await call('/portal')).status, 200);
  assert.equal(calls.at(-1).body.get('return_url'), settings.STRIPE_RETURN_URL + '?plus=gestion');
  assert.equal((await call('/portal', {account: annualAccount, customer: 'cus_Test'})).status, 404);
  subscription.cancel_at_period_end = true;
  await webhook('customer.subscription.updated', subscription);
  assert.equal(store.status(account, start).plus.until, paidUntil);
  subscription = {...subscription, status: 'past_due', items: {data: [{
    price: {id: 'price_Month'}, current_period_end: Math.floor(start / 1000) + 7200,
  }]}};
  assert.equal((await webhook('invoice.payment_failed', invoice('sub_Test'))).status, 200);
  assert.equal(store.status(account, start).plus.until, paidUntil);
  assert.equal(store.status(account, paidUntil).plus.active, false);
  subscription.status = 'active';
  assert.equal((await webhook('invoice.paid', invoice('sub_Test'))).status, 200);
  assert.ok(store.status(account, start).plus.until > paidUntil);
  subscription.status = 'canceled';
  await webhook('customer.subscription.deleted', subscription);
  await webhook('customer.subscription.created', {id: 'sub_Test'});
  assert.equal(store.status(account, start).plus.active, false);
  assert.equal((await call('/checkout', {account: annualAccount, plan: 'year'})).status, 200);
  assert.equal(calls.at(-1).body.get('line_items[0][price]'), 'price_Year');
  assert.equal(store.status(annualAccount, start).plus.active, false);
  const annualExpiry = Math.floor(start / 1000) + 365 * 86400;
  subscription = {id: 'sub_Annual', livemode: false, customer: 'cus_Second', status: 'active',
    metadata: {carburantradar_account: annualAccount}, latest_invoice: {status: 'paid'},
    items: {data: [{price: {id: 'price_Year'}, current_period_end: annualExpiry}]}};
  assert.equal((await webhook('invoice.paid', invoice('sub_Annual'))).status, 200);
  assert.deepEqual(store.status(annualAccount, start).plus, {active: true, lifetime: false, until: annualExpiry * 1000});
  assert.equal(store.status(annualAccount, start).credits, 5);
  assert.equal(store.status(account, start).plus.active, false);
  assert.ok(calls.every(({headers}) => headers['Stripe-Version'] === '2025-04-30.basil'));
});

test('le statut réconcilie un paiement existant et une ancienne livraison non appliquée peut être rejouée', async t => {
  const db = new DatabaseSync(':memory:');
  db.exec(`CREATE TABLE stripe_event (id TEXT PRIMARY KEY NOT NULL, received INTEGER NOT NULL);
    INSERT INTO stripe_event VALUES ('evt_old', 1795733999000)`);
  const store = ledger(db);
  const account = 'c'.repeat(64);
  const end = Math.floor(start / 1000) + 2592000;
  const settings = {PLUS_BILLING_TEST: '1', STRIPE_SECRET_KEY: 'sk_test_fixture', STRIPE_WEBHOOK_SECRET: 'whsec_fixture',
    STRIPE_MONTHLY_PRICE: 'price_Month', STRIPE_YEARLY_PRICE: 'price_Year',
    STRIPE_RETURN_URL: 'https://preprod.example.test/france/'};
  store.saveCustomer(account, 'cus_Existing');
  assert.equal(store.hasStripeEvent('evt_old'), false);
  const record = {id: 'sub_Existing', livemode: false, customer: 'cus_Existing', status: 'active',
    metadata: {carburantradar_account: account}, latest_invoice: {status: 'paid'},
    items: {data: [{price: {id: 'price_Month'}, current_period_end: end}]}};
  let reads = 0;
  t.mock.method(globalThis, 'fetch', async (uri, {method}) => {
    assert.equal(method, 'GET');
    reads++;
    return Response.json(new URL(uri).pathname === '/v1/subscriptions' ? {data: [record]} : record);
  });
  const status = () => handleRequest(request('/status', {account, refresh: true}), store, adminToken, start, settings);
  const [left, right] = await Promise.all([status(), status()]);
  for (const response of [left, right]) {
    const result = await response.json();
    assert.equal(result.plus.active, true);
    assert.deepEqual(result.billing.subscription, {status: 'active', plan: 'month', periodEnd: end * 1000,
      paidUntil: end * 1000, cancelAtPeriodEnd: false});
    assert.equal(result.billing.canCheckout, false);
  }
  assert.equal(reads, 2);
  assert.equal(store.hasStripeEvent('evt_old'), false);
  store.saveStripeSubscription(record.id, account, {until: end * 1000, periodEnd: end * 1000, plan: 'month', status: 'active',
    cancelAtPeriodEnd: true}, 'evt_old', start);
  assert.equal(store.hasStripeEvent('evt_old'), true);
  assert.equal(store.billingDetails(account).cancelAtPeriodEnd, true);
});
