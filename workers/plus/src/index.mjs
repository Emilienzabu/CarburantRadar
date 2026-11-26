import { DurableObject } from 'cloudflare:workers';
import { PlusLedger } from './ledger.mjs';
import { handleRequest } from './http.mjs';

export class PlusState extends DurableObject {
  constructor(ctx, env) {
    super(ctx, env);
    this.ledger = new PlusLedger(ctx.storage.sql, callback => ctx.storage.transactionSync(callback));
  }

  fetch(request) { return handleRequest(request, this.ledger, this.env.PLUS_ADMIN_TOKEN, Date.now(), this.env); }
}

export default {
  fetch(request, env) {
    // Ce Worker n’a pas d’URL publique. L’identité arrive du service de connexion.
    return env.PLUS_STATE.getByName('credits-and-gifts').fetch(request);
  },
};
