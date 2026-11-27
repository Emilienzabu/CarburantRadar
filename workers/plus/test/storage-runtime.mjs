import {DurableObject} from 'cloudflare:workers';
import {PlusLedger} from '../src/ledger.mjs';
import {nearby} from '../src/advanced.mjs';

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
  async fetch(request, env) {
    if (new URL(request.url).pathname === '/stations') {
      const stations = await nearby({lat: 48.8566, lon: 2.3522}, 5, (url, options) => {
        const outgoing = new Request(url, options);
        if (outgoing.redirect !== 'manual') throw new Error('Redirections externes interdites.');
        return Response.json({results: [{id: 94160001}]});
      });
      return Response.json({stations});
    }
    return env.STORAGE_CHECK.getByName('case').fetch(request);
  },
};
