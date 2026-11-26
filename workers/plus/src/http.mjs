import { LedgerError } from './ledger.mjs';
import { beginCheckout, billingPortal, billingReady, stripeWebhook } from './billing.mjs';

function reply(payload, status = 200) {
  return Response.json(payload, {status, headers: {'cache-control': 'no-store'}});
}

function accountStatus(ledger, env, account, now, created) {
  const status = ledger.status(account, now, created);
  const analysis = ledger.analysis(account, now);
  if (env.PLUS_ANALYSIS_PREVIEW === '1') status.analysis = analysis;
  if (billingReady(env)) {
    status.billing = {test: true, hasCustomer: !!ledger.customer(account), canCheckout: !ledger.hasOpenSubscription(account)};
  }
  return status;
}

async function adminAuthorized(request, secret) {
  if (typeof secret !== 'string' || secret.length < 32) return false;
  const provided = request.headers.get('authorization');
  if (!provided?.startsWith('Bearer ')) return false;
  const encoder = new TextEncoder();
  const [expected, received] = await Promise.all([secret, provided.slice(7)].map(value =>
    crypto.subtle.digest('SHA-256', encoder.encode(value))));
  const reference = new Uint8Array(expected);
  const candidate = new Uint8Array(received);
  let mismatch = 0;
  for (let i = 0; i < reference.length; i++) mismatch |= reference[i] ^ candidate[i];
  return mismatch === 0;
}

export async function handleRequest(request, ledger, adminToken, now = Date.now(), billingEnv = {}) {
  const {pathname} = new URL(request.url);
  if (request.method !== 'POST') return reply({error: 'method_not_allowed'}, 405);
  if (['/issue', '/reward'].includes(pathname) && !(await adminAuthorized(request, adminToken))) {
    return reply({error: 'admin_required'}, 403);
  }
  try {
    if (pathname === '/stripe/webhook') return reply(await stripeWebhook(request, ledger, billingEnv, now));
    const data = await request.json().catch(() => null);
    if (!data || typeof data !== 'object' || Array.isArray(data)) return reply({error: 'invalid_request'}, 400);
    if (pathname === '/issue') return reply(await ledger.issue(data, now), 201);
    const {account, code, created} = data;
    if (typeof account !== 'string' || !account.trim() || account.length > 256) {
      return reply({error: 'account_required'}, 401);
    }
    switch (pathname) {
      case '/status': return reply(accountStatus(ledger, billingEnv, account, now, created));
      case '/claim': {
        const {claimed} = ledger.claim(account, now, created);
        return reply({...accountStatus(ledger, billingEnv, account, now, created), claimed});
      }
      case '/preview': return reply(await ledger.preview(account, code, now));
      case '/redeem':
        await ledger.redeem(account, code, now, created);
        return reply(accountStatus(ledger, billingEnv, account, now, created));
      case '/checkout': return reply(await beginCheckout(ledger, billingEnv, account, data.plan, now, created));
      case '/portal': return reply(await billingPortal(ledger, billingEnv, account));
      case '/unlock-analysis': {
        if (billingEnv.PLUS_ANALYSIS_PREVIEW !== '1') throw new LedgerError('analysis_unavailable', 503);
        ledger.unlockAnalysis(account, now, created);
        return reply(accountStatus(ledger, billingEnv, account, now, created));
      }
      case '/reward': return reply(ledger.reward(account, data.event, now, created));
      default: return reply({error: 'not_found'}, 404);
    }
  } catch (error) {
    if (error instanceof LedgerError) return reply({error: error.code}, error.status);
    throw error;
  }
}
