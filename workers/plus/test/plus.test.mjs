import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {test} from 'node:test';
import {PlusLedger} from '../src/ledger.mjs';
import {handleRequest} from '../src/http.mjs';
import {forwardPlus} from '../src/proxy.mjs';

const start = Date.parse('2026-11-26T22:59:59Z');
const tomorrow = start + 1000;
const adminToken = 'test-secret-with-more-than-32-characters';

function ledger() {
  const db = new DatabaseSync(':memory:');
  const sql = {
    exec(query, ...values) {
      if (query.startsWith('\n')) return db.exec(query);
      const statement = db.prepare(query);
      if (query.startsWith('SELECT')) return {toArray: () => statement.all(...values)};
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
  });
});
