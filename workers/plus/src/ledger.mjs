const parisDate = new Intl.DateTimeFormat('sv-SE', {
  timeZone: 'Europe/Paris', year: 'numeric', month: '2-digit', day: '2-digit',
});

export class LedgerError extends Error {
  constructor(code, status = 400) {
    super(code);
    this.code = code;
    this.status = status;
  }
}

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
    const lifetime = member.gift_lifetime === 1;
    return {
      credits: member.credits,
      canClaimToday: member.last_claim < parisDate.format(now),
      plus: {active: lifetime || (member.gift_until !== null && member.gift_until > now), lifetime, until: member.gift_until},
    };
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
