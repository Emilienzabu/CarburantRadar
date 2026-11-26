import { LedgerError } from './ledger.mjs';
import { beginCheckout, billingPortal, billingReady, stripeWebhook } from './billing.mjs';
import { detailedAnalysis, detailedTrip } from './advanced.mjs';

const advancedInFlight = new WeakMap();

async function prepareAdvanced(ledger, account, work) {
  if (!advancedInFlight.has(ledger)) advancedInFlight.set(ledger, new Set());
  const pending = advancedInFlight.get(ledger);
  if (pending.has(account)) throw new LedgerError('advanced_in_progress', 409);
  pending.add(account);
  try { return await work(); }
  finally { pending.delete(account); }
}

function reply(payload, status = 200) {
  return Response.json(payload, {status, headers: {'cache-control': 'no-store'}});
}

function accountStatus(ledger, env, account, now, created) {
  const status = ledger.status(account, now, created);
  const analysis = ledger.analysis(account, now);
  if (env.PLUS_ANALYSIS_PREVIEW === '1') status.analysis = analysis;
  if (env.PLUS_TRIP_PREVIEW === '1') status.trip = true;
  if (env.PLUS_ALERTS_PREVIEW === '1') status.alerts = ledger.alerts(account, now, created);
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
  if (['/issue', '/reward', '/scheduled/alerts', '/scheduled/reserve', '/scheduled/remove'].includes(pathname) &&
      !(await adminAuthorized(request, adminToken))) {
    return reply({error: 'admin_required'}, 403);
  }
  try {
    if (pathname === '/stripe/webhook') return reply(await stripeWebhook(request, ledger, billingEnv, now));
    const data = await request.json().catch(() => null);
    if (!data || typeof data !== 'object' || Array.isArray(data)) return reply({error: 'invalid_request'}, 400);
    if (pathname === '/issue') return reply(await ledger.issue(data, now), 201);
    if (pathname.startsWith('/scheduled/') && billingEnv.PLUS_ALERTS_DELIVERY !== '1') {
      throw new LedgerError('extra_alert_unavailable', 503);
    }
    if (pathname === '/scheduled/alerts') {
      const after = data.cursor ?? '';
      if (typeof after !== 'string' || after.length > 300) throw new LedgerError('invalid_request');
      return reply(ledger.scheduledAlerts(after, now));
    }
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
      case '/analysis': {
        if (billingEnv.PLUS_ANALYSIS_PREVIEW !== '1') throw new LedgerError('analysis_unavailable', 503);
        const state = ledger.status(account, now, created);
        const hasAccess = state.plus.active || ledger.analysis(account, now).unlocked;
        if (!hasAccess && data.confirm !== true) throw new LedgerError('confirmation_required', 409);
        if (!hasAccess && state.credits < 1) throw new LedgerError('credits_insufficient', 409);
        const result = await prepareAdvanced(ledger, account, () => detailedAnalysis(data.params, now));
        if (data.confirm === true) ledger.unlockAnalysis(account, now, created);
        else if (!ledger.status(account, now, created).plus.active && !ledger.analysis(account, now).unlocked) {
          throw new LedgerError('confirmation_required', 409);
        }
        return reply({...accountStatus(ledger, billingEnv, account, now, created), result});
      }
      case '/trip': {
        if (billingEnv.PLUS_TRIP_PREVIEW !== '1') throw new LedgerError('trip_unavailable', 503);
        const encoded = new TextEncoder().encode(JSON.stringify(data.params ?? null));
        const params = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', encoded)),
          byte => byte.toString(16).padStart(2, '0')).join('');
        const existing = ledger.tripResult(account, data.id, params, now);
        if (existing) return reply({...accountStatus(ledger, billingEnv, account, now, created), result: existing});
        const state = ledger.status(account, now, created);
        if (!state.plus.active && data.confirm !== true) throw new LedgerError('confirmation_required', 409);
        if (!state.plus.active && state.credits < 1) throw new LedgerError('credits_insufficient', 409);
        const result = await prepareAdvanced(ledger, account, () => detailedTrip(data.params, billingEnv.PLUS_OSRM_URL));
        const saved = ledger.saveTripResult(account, data.id, params, result, now, created, data.confirm === true);
        return reply({...accountStatus(ledger, billingEnv, account, now, created), result: saved});
      }
      case '/alerts/add':
      case '/alerts/renew':
      case '/alerts/remove':
        if (billingEnv.PLUS_ALERTS_PREVIEW !== '1') throw new LedgerError('extra_alert_unavailable', 503);
        if (pathname === '/alerts/add') ledger.addAlert(account, data.id, data.settings, now, created);
        if (pathname === '/alerts/renew') ledger.renewAlert(account, data.id, now, created);
        if (pathname === '/alerts/remove') ledger.removeAlert(account, data.id);
        return reply(accountStatus(ledger, billingEnv, account, now, created));
      case '/reward': return reply(ledger.reward(account, data.event, now, created));
      case '/scheduled/reserve': return reply({reserved: ledger.reserveAlertDelivery(account, data.id, now)});
      case '/scheduled/remove':
        ledger.removeAlert(account, data.id);
        return reply({removed: true});
      default: return reply({error: 'not_found'}, 404);
    }
  } catch (error) {
    if (error instanceof LedgerError) return reply({error: error.code}, error.status);
    if (pathname === '/analysis' || pathname === '/trip') return reply({error: 'advanced_service_unavailable'}, 503);
    throw error;
  }
}
