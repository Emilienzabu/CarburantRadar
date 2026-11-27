import {DurableObject} from 'cloudflare:workers';
import {PlusLedger} from '../src/ledger.mjs';

export class StorageCheck extends DurableObject {
  fetch() {
    const storage = this.ctx.storage;
    const sql = storage.sql;
    sql.exec(`CREATE TABLE IF NOT EXISTS stripe_event (id TEXT PRIMARY KEY NOT NULL, received INTEGER NOT NULL);
      CREATE INDEX IF NOT EXISTS stripe_event_received ON stripe_event(received)`);
    const now = Date.now();
    const event = 'evt_' + crypto.randomUUID();
    const {rowsWritten} = sql.exec('INSERT OR IGNORE INTO stripe_event (id, received) VALUES (?, ?)', event, now);
    const ledger = new PlusLedger(sql, change => storage.transactionSync(change));
    const account = 'runtime-fixture';
    const id = 'sub_Runtime';
    const before = ledger.hasStripeEvent(event);
    ledger.saveStripeSubscription(id, account, {status: 'active', plan: 'month', periodEnd: now + 86400000,
      until: now + 86400000, cancelAtPeriodEnd: false}, event, now);
    return Response.json({rowsWritten, before, after: ledger.hasStripeEvent(event),
      active: ledger.status(account, now).plus.active, plan: ledger.billingDetails(account)?.plan});
  }
}

export default {
  fetch(request, env) {
    return env.STORAGE_CHECK.getByName('case').fetch(request);
  },
};
