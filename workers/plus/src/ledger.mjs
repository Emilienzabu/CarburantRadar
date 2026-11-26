import { extraAlert, EXTRA_ALERT_LIMIT, EXTRA_ALERT_WEEK, LedgerError, operationId } from './features.mjs';
export { LedgerError } from './features.mjs';

const parisDate = new Intl.DateTimeFormat('sv-SE', {
  timeZone: 'Europe/Paris', year: 'numeric', month: '2-digit', day: '2-digit',
});

function normalizedCode(value) {
  const code = typeof value === 'string' ? value.trim().toUpperCase().replaceAll('-', '') : '';
  if (!/^[0-9A-F]{24}$/.test(code)) throw new LedgerError('code_invalid', 404);
  return code;
}

async function digest(code) {
  const bytes = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(code));
  return Array.from(new Uint8Array(bytes), byte => byte.toString(16).padStart(2, '0')).join('');
}

function plusMonths(now, months) {
  const date = new Date(now);
  const day = date.getUTCDate();
  date.setUTCDate(1);
  date.setUTCMonth(date.getUTCMonth() + months);
  const end = new Date(date);
  end.setUTCMonth(end.getUTCMonth() + 1, 0);
  date.setUTCDate(Math.min(day, end.getUTCDate()));
  return date.getTime();
}

export class PlusLedger {
  constructor(sql, transaction) {
    this.sql = sql;
    this.transaction = transaction;
    this.subscriptionUpdates = new Map();
    sql.exec(`
      CREATE TABLE IF NOT EXISTS member (
        account TEXT PRIMARY KEY NOT NULL,
        credits INTEGER NOT NULL DEFAULT 5,
        last_claim TEXT NOT NULL,
        gift_until INTEGER,
        gift_lifetime INTEGER NOT NULL DEFAULT 0
      );
      CREATE TABLE IF NOT EXISTS gift_code (
        hash TEXT PRIMARY KEY NOT NULL,
        months INTEGER,
        deadline INTEGER,
        uses_left INTEGER NOT NULL
      );
      CREATE TABLE IF NOT EXISTS gift_use (
        hash TEXT NOT NULL,
        account TEXT NOT NULL,
        PRIMARY KEY (hash, account)
      );
      CREATE TABLE IF NOT EXISTS stripe_customer (
        account TEXT PRIMARY KEY NOT NULL,
        customer TEXT UNIQUE NOT NULL
      );
      CREATE TABLE IF NOT EXISTS stripe_checkout (
        account TEXT PRIMARY KEY NOT NULL,
        attempt TEXT NOT NULL,
        plan TEXT NOT NULL,
        expires INTEGER NOT NULL
      );
      CREATE TABLE IF NOT EXISTS stripe_subscription (
        id TEXT PRIMARY KEY NOT NULL,
        account TEXT NOT NULL,
        paid_until INTEGER NOT NULL,
        status TEXT NOT NULL
      );
      CREATE INDEX IF NOT EXISTS stripe_subscription_account ON stripe_subscription(account);
      CREATE TABLE IF NOT EXISTS credit_access (
        account TEXT NOT NULL,
        feature TEXT NOT NULL,
        expires INTEGER NOT NULL,
        PRIMARY KEY (account, feature)
      );
      CREATE TABLE IF NOT EXISTS ad_reward (
        event TEXT PRIMARY KEY NOT NULL,
        account TEXT NOT NULL
      );
      CREATE TABLE IF NOT EXISTS trip_receipt (
        account TEXT NOT NULL, comparison TEXT NOT NULL,
        PRIMARY KEY (account, comparison)
      );
      CREATE TABLE IF NOT EXISTS extra_alert (
        account TEXT NOT NULL, id TEXT NOT NULL, data TEXT NOT NULL, until INTEGER, removed INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (account, id)
      );
      CREATE TABLE IF NOT EXISTS extra_alert_delivery (
        account TEXT NOT NULL, id TEXT NOT NULL, day TEXT NOT NULL,
        PRIMARY KEY (account, id)
      );
    `);
  }

  row(query, ...values) {
    return this.sql.exec(query, ...values).toArray()[0];
  }

  member(account, now, created = null) {
    const existing = this.row('SELECT * FROM member WHERE account = ?', account);
    if (existing) return existing;
    const start = created > 0 && created <= now ? created : now;
    this.sql.exec('INSERT INTO member(account, last_claim) VALUES (?, ?)', account, parisDate.format(start));
    return this.row('SELECT * FROM member WHERE account = ?', account);
  }

  status(account, now, created) {
    const member = this.member(account, now, created);
    return {
      credits: member.credits, canClaimToday: member.last_claim < parisDate.format(now),
      plus: this.access(account, now, member),
    };
  }

  access(account, now, member = this.row('SELECT gift_lifetime, gift_until FROM member WHERE account = ?', account)) {
    if (!member) return {active: false, lifetime: false, until: null};
    const lifetime = member.gift_lifetime === 1;
    const paid = this.row('SELECT MAX(paid_until) AS until FROM stripe_subscription WHERE account = ?', account).until;
    const until = lifetime ? null : Math.max(member.gift_until || 0, paid || 0) || null;
    return {active: lifetime || (until !== null && until > now), lifetime, until};
  }

  debit(state, account, credits) {
    if (state.credits < credits) throw new LedgerError('credits_insufficient', 409);
    this.sql.exec('UPDATE member SET credits = credits - ? WHERE account = ?', credits, account);
  }

  unlockTrip(account, comparison, now, created) {
    operationId(comparison);
    return this.transaction(() => {
      const state = this.status(account, now, created);
      if (state.plus.active) return {charged: false};
      const receipt = this.row('SELECT 1 FROM trip_receipt WHERE account = ? AND comparison = ?', account, comparison);
      if (receipt) return {charged: false};
      this.debit(state, account, 1);
      this.sql.exec('INSERT INTO trip_receipt VALUES (?, ?)', account, comparison);
      return {charged: true};
    });
  }

  alerts(account, now, created) {
    const state = this.status(account, now, created);
    return this.sql.exec('SELECT * FROM extra_alert WHERE account = ? AND removed = 0 ORDER BY id', account)
      .toArray().map(row => {
        const {sub, ...settings} = JSON.parse(row.data);
        return {...settings, id: row.id, until: row.until,
          active: state.plus.active || row.until > now};
      });
  }

  addAlert(account, id, value, now, created) {
    operationId(id);
    const settings = extraAlert(value);
    return this.transaction(() => {
      const existing = this.row('SELECT removed FROM extra_alert WHERE account = ? AND id = ?', account, id);
      if (existing?.removed) throw new LedgerError('extra_alert_missing', 404);
      if (existing) return;
      const state = this.status(account, now, created);
      const current = this.sql.exec('SELECT data FROM extra_alert WHERE account = ? AND removed = 0', account).toArray();
      if (current.length >= EXTRA_ALERT_LIMIT) throw new LedgerError('extra_alert_limit', 409);
      if (current.some(row => {
        const other = JSON.parse(row.data);
        return ['lat', 'lon', 'carburant', 'rayon', 'seuil'].every(key => other[key] === settings[key]);
      })) throw new LedgerError('extra_alert_duplicate', 409);
      if (!state.plus.active) this.debit(state, account, 2);
      this.sql.exec('INSERT INTO extra_alert(account, id, data, until) VALUES (?, ?, ?, ?)',
        account, id, JSON.stringify(settings), state.plus.active ? null : now + EXTRA_ALERT_WEEK);
    });
  }

  renewAlert(account, id, now, created) {
    operationId(id);
    return this.transaction(() => {
      const alert = this.row('SELECT until FROM extra_alert WHERE account = ? AND id = ? AND removed = 0', account, id);
      if (!alert) throw new LedgerError('extra_alert_missing', 404);
      const state = this.status(account, now, created);
      if (state.plus.active || alert.until > now) return;
      this.debit(state, account, 2);
      this.sql.exec('UPDATE extra_alert SET until = ? WHERE account = ? AND id = ?', now + EXTRA_ALERT_WEEK, account, id);
    });
  }

  removeAlert(account, id) {
    operationId(id);
    this.sql.exec("UPDATE extra_alert SET removed = 1, data = '{}', until = NULL WHERE account = ? AND id = ?", account, id);
  }

  scheduledAlerts(after, now) {
    const rows = this.sql.exec(`SELECT account, id, data, until FROM extra_alert
      WHERE removed = 0 AND (account || ':' || id) > ? ORDER BY account || ':' || id LIMIT 100`, after)
      .toArray();
    return {
      alerts: rows.filter(row => row.until > now || this.access(row.account, now).active)
        .map(row => ({account: row.account, id: row.id, ...JSON.parse(row.data)})),
      cursor: rows.length === 100 ? rows.at(-1).account + ':' + rows.at(-1).id : null,
    };
  }

  reserveAlertDelivery(account, id, now) {
    operationId(id);
    return this.transaction(() => {
      const row = this.row('SELECT until FROM extra_alert WHERE account = ? AND id = ? AND removed = 0', account, id);
      if (!row || !(row.until > now || this.access(account, now).active)) return false;
      const day = parisDate.format(now);
      const {rowsWritten} = this.sql.exec(`INSERT INTO extra_alert_delivery VALUES (?, ?, ?)
        ON CONFLICT(account, id) DO UPDATE SET day = excluded.day WHERE day < excluded.day`, account, id, day);
      return rowsWritten === 1;
    });
  }

  customer(account) {
    return this.row('SELECT customer FROM stripe_customer WHERE account = ?', account)?.customer;
  }

  hasOpenSubscription(account) {
    return !!this.row(`SELECT 1 FROM stripe_subscription
      WHERE account = ? AND status IN ('active', 'past_due', 'unpaid', 'trialing', 'paused') LIMIT 1`, account);
  }

  saveCustomer(account, customer) {
    if (!/^cus_[a-zA-Z0-9]+$/.test(customer || '')) throw new LedgerError('billing_unavailable', 503);
    this.sql.exec('INSERT OR IGNORE INTO stripe_customer VALUES (?, ?)', account, customer);
    return this.customer(account);
  }

  checkoutAttempt(account, plan, now) {
    const current = this.row('SELECT * FROM stripe_checkout WHERE account = ?', account);
    if (current?.expires > now) {
      if (current.plan !== plan) throw new LedgerError('checkout_other_plan_pending', 409);
      return {key: current.attempt, expires: current.expires};
    }
    // Stripe requires at least thirty minutes of validity when the session is created.
    const expires = now + 60 * 60 * 1000;
    const key = crypto.randomUUID();
    this.sql.exec('INSERT OR REPLACE INTO stripe_checkout VALUES (?, ?, ?, ?)', account, key, plan, expires);
    return {key, expires};
  }

  async syncSubscription(id, update) {
    const previous = this.subscriptionUpdates.get(id) || Promise.resolve();
    const pending = previous.catch(() => {}).then(update);
    this.subscriptionUpdates.set(id, pending);
    try { return await pending; }
    finally {
      if (this.subscriptionUpdates.get(id) === pending) this.subscriptionUpdates.delete(id);
    }
  }

  saveSubscription(id, account, until, status) {
    const previous = this.row('SELECT paid_until FROM stripe_subscription WHERE id = ?', id)?.paid_until || 0;
    const paidUntil = status === 'past_due' ? Math.min(previous, until) : until;
    this.sql.exec('INSERT OR REPLACE INTO stripe_subscription VALUES (?, ?, ?, ?)', id, account, paidUntil, status);
  }

  claim(account, now, created) {
    return this.transaction(() => {
      this.member(account, now, created);
      const today = parisDate.format(now);
      const {rowsWritten} = this.sql.exec(
        'UPDATE member SET credits = credits + 1, last_claim = ? WHERE account = ? AND last_claim < ?',
        today, account, today,
      );
      return {...this.status(account, now), claimed: rowsWritten === 1};
    });
  }

  analysis(account, now) {
    const expires = this.row('SELECT expires FROM credit_access WHERE account = ? AND feature = ?', account, 'analysis')?.expires;
    return {unlocked: Boolean(expires > now), expires: expires > now ? expires : null};
  }

  unlockAnalysis(account, now, created) {
    return this.transaction(() => {
      const state = this.status(account, now, created);
      const access = this.analysis(account, now);
      if (state.plus.active || access.unlocked) return;
      this.debit(state, account, 1);
      const expires = now + 86400000;
      this.sql.exec('INSERT OR REPLACE INTO credit_access VALUES (?, ?, ?)', account, 'analysis', expires);
    });
  }

  reward(account, event, now, created) {
    if (typeof event !== 'string' || !/^[a-zA-Z0-9._:-]{1,160}$/.test(event)) throw new LedgerError('reward_invalid');
    return this.transaction(() => {
      const {rowsWritten} = this.sql.exec('INSERT OR IGNORE INTO ad_reward VALUES (?, ?)', event, account);
      if (rowsWritten === 1) {
        this.member(account, now, created);
        this.sql.exec('UPDATE member SET credits = credits + 2 WHERE account = ?', account);
      }
      return {...this.status(account, now, created), rewarded: rowsWritten === 1};
    });
  }

  async issue({months, deadline = null, maxUses}, now) {
    if (![6, 12, null].includes(months) || !Number.isSafeInteger(maxUses) || maxUses < 1 || maxUses > 10000 ||
        (deadline !== null && (!Number.isSafeInteger(deadline) || deadline <= now || deadline > 253402300799999))) {
      throw new LedgerError('gift_settings_invalid');
    }
    const bytes = crypto.getRandomValues(new Uint8Array(12));
    const code = Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('').toUpperCase();
    const hash = await digest(code);
    this.sql.exec('INSERT INTO gift_code VALUES (?, ?, ?, ?)', hash, months, deadline, maxUses);
    return {code: code.match(/.{4}/g).join('-'), months, deadline, maxUses};
  }

  gift(hash, account, now) {
    const code = this.row('SELECT * FROM gift_code WHERE hash = ?', hash);
    if (!code) throw new LedgerError('code_invalid', 404);
    if (this.row('SELECT 1 FROM gift_use WHERE hash = ? AND account = ?', hash, account)) {
      throw new LedgerError('code_used', 409);
    }
    if (code.deadline !== null && code.deadline <= now) throw new LedgerError('code_expired', 409);
    if (code.uses_left < 1) throw new LedgerError('code_used_up', 409);
    const member = this.row('SELECT gift_lifetime, gift_until FROM member WHERE account = ?', account);
    if (member?.gift_lifetime) throw new LedgerError('plus_lifetime_already_active', 409);
    const start = Math.max(member?.gift_until ?? now, now);
    return {months: code.months, lifetime: code.months === null, until: code.months === null ? null : plusMonths(start, code.months)};
  }

  async preview(account, value, now) {
    return this.gift(await digest(normalizedCode(value)), account, now);
  }

  async redeem(account, value, now, created) {
    const hash = await digest(normalizedCode(value));
    return this.transaction(() => {
      const gift = this.gift(hash, account, now);
      this.member(account, now, created);
      this.sql.exec('INSERT INTO gift_use VALUES (?, ?)', hash, account);
      this.sql.exec('UPDATE gift_code SET uses_left = uses_left - 1 WHERE hash = ?', hash);
      this.sql.exec('UPDATE member SET gift_until = ?, gift_lifetime = ? WHERE account = ?', gift.until, Number(gift.lifetime), account);
      return this.status(account, now);
    });
  }
}
