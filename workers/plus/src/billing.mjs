import { LedgerError } from './ledger.mjs';

const api = 'https://api.stripe.com/v1';
const encoder = new TextEncoder();
const subscriptionEvents = new Set([
  'customer.subscription.created', 'customer.subscription.updated', 'customer.subscription.deleted',
]);
const invoiceEvents = new Set(['invoice.paid', 'invoice.payment_failed']);

export function billingReady(env) {
  const returnUrl = URL.canParse(env.STRIPE_RETURN_URL) ? new URL(env.STRIPE_RETURN_URL) : null;
  return env.PLUS_BILLING_TEST === '1' && /^sk_test_/.test(env.STRIPE_SECRET_KEY || '') &&
    /^whsec_/.test(env.STRIPE_WEBHOOK_SECRET || '') &&
    /^price_[a-zA-Z0-9]+$/.test(env.STRIPE_MONTHLY_PRICE || '') &&
    /^price_[a-zA-Z0-9]+$/.test(env.STRIPE_YEARLY_PRICE || '') &&
    env.STRIPE_MONTHLY_PRICE !== env.STRIPE_YEARLY_PRICE &&
    returnUrl?.protocol === 'https:' && !returnUrl.username && !returnUrl.password &&
    !returnUrl.search && !returnUrl.hash;
}

async function stripe(method, path, env, fields, key) {
  const headers = {authorization: 'Bearer ' + env.STRIPE_SECRET_KEY, 'Stripe-Version': '2025-04-30.basil'};
  if (key) headers['Idempotency-Key'] = key;
  const response = await fetch(api + path, {
    method, headers, body: fields ? new URLSearchParams(fields) : undefined,
    signal: AbortSignal.timeout(8000),
  });
  if (!response.ok) throw new LedgerError('billing_unavailable', 503);
  return response.json();
}

export async function beginCheckout(ledger, env, account, plan, now, created) {
  if (!billingReady(env)) throw new LedgerError('billing_unavailable', 503);
  const prices = {month: env.STRIPE_MONTHLY_PRICE, year: env.STRIPE_YEARLY_PRICE};
  if (plan !== 'month' && plan !== 'year') throw new LedgerError('plan_invalid');
  if (ledger.status(account, now, created).plus.active || ledger.hasOpenSubscription(account)) {
    throw new LedgerError('plus_already_active', 409);
  }
  const price = await stripe('GET', '/prices/' + prices[plan], env);
  if (price.livemode !== false || price.currency !== 'eur' || price.unit_amount !== (plan === 'month' ? 100 : 1000) ||
      price.recurring?.interval !== plan || price.recurring.interval_count !== 1 || !price.active) {
    throw new LedgerError('billing_unavailable', 503);
  }

  const stripeCustomer = ledger.customer(account) || (await stripe('POST', '/customers', env,
    {'metadata[carburantradar_account]': account}, 'plus-customer-' + account)).id;
  const customer = ledger.saveCustomer(account, stripeCustomer);
  const existing = await stripe('GET', '/subscriptions?customer=' + customer + '&status=all&limit=100', env);
  if (existing.data.some(item => item.metadata?.carburantradar_account === account &&
      !['canceled', 'incomplete_expired', 'incomplete'].includes(item.status))) {
    throw new LedgerError('plus_already_active', 409);
  }
  const attempt = ledger.checkoutAttempt(account, plan, now);
  const session = await stripe('POST', '/checkout/sessions', env, {
    mode: 'subscription',
    customer,
    client_reference_id: account,
    'line_items[0][price]': prices[plan],
    'line_items[0][quantity]': '1',
    'payment_method_types[0]': 'card',
    'subscription_data[metadata][carburantradar_account]': account,
    success_url: env.STRIPE_RETURN_URL + '?plus=retour',
    cancel_url: env.STRIPE_RETURN_URL + '?plus=annule',
    expires_at: String(Math.floor(attempt.expires / 1000)),
  }, 'plus-checkout-' + attempt.key);
  return {url: session.url};
}

export async function billingPortal(ledger, env, account) {
  if (!billingReady(env)) throw new LedgerError('billing_unavailable', 503);
  const customer = ledger.customer(account);
  if (!customer) throw new LedgerError('billing_account_missing', 404);
  const session = await stripe('POST', '/billing_portal/sessions', env, {
    customer, return_url: env.STRIPE_RETURN_URL + '?plus=gestion',
  });
  return {url: session.url};
}

export async function verifyStripeEvent(raw, signature, secret, now) {
  const values = (signature || '').split(',').map(field => field.trim().split('='));
  const value = values.find(([name]) => name === 't')?.[1];
  if (!/^\d{1,12}$/.test(value || '') || Math.abs(now / 1000 - Number(value)) > 300) return null;
  const signatures = values.filter(([name, hash]) => name === 'v1' && /^[a-f0-9]{64}$/i.test(hash || ''));
  if (!signatures.length) return null;
  const key = await crypto.subtle.importKey('raw', encoder.encode(secret), {name: 'HMAC', hash: 'SHA-256'}, false, ['verify']);
  const prefix = encoder.encode(value + '.');
  const buffer = new Uint8Array(prefix.length + raw.byteLength);
  buffer.set(prefix);
  buffer.set(raw, prefix.length);
  for (const [, hash] of signatures) {
    const bytes = Uint8Array.from(hash.match(/../g), pair => parseInt(pair, 16));
    if (await crypto.subtle.verify('HMAC', key, bytes, buffer)) {
      try { return JSON.parse(new TextDecoder('utf-8', {fatal: true}).decode(raw)); } catch { return null; }
    }
  }
  return null;
}

export async function stripeWebhook(request, ledger, env, now) {
  if (!billingReady(env)) throw new LedgerError('billing_unavailable', 503);
  const raw = new Uint8Array(await request.arrayBuffer());
  const event = await verifyStripeEvent(raw, request.headers.get('Stripe-Signature'), env.STRIPE_WEBHOOK_SECRET, now);
  if (!event || event.livemode !== false) throw new LedgerError('stripe_signature_invalid');
  const object = event.data?.object;
  const id = subscriptionEvents.has(event.type) ? object?.id
    : invoiceEvents.has(event.type) ? (object?.parent?.subscription_details?.subscription || object?.subscription)
    : event.type === 'checkout.session.completed' && object?.mode === 'subscription' ? object.subscription : null;
  if (!id) return {received: true};
  if (!/^sub_[a-zA-Z0-9]+$/.test(id) || !/^evt_[a-zA-Z0-9_]+$/.test(event.id || '')) {
    throw new LedgerError('stripe_event_invalid');
  }
  // Relire la version actuelle pour que l'ordre de livraison des événements n'ait pas d'effet.
  return ledger.syncSubscription(id, async () => {
    if (ledger.hasStripeEvent(event.id)) return {received: true};
    const subscription = await stripe('GET', '/subscriptions/' + id + '?expand%5B%5D=latest_invoice', env);
    const account = subscription.metadata?.carburantradar_account;
    if (subscription.livemode !== false || !/^[a-f0-9]{64}$/.test(account || '') ||
        ledger.customer(account) !== subscription.customer) return {received: true};
    const prices = [env.STRIPE_MONTHLY_PRICE, env.STRIPE_YEARLY_PRICE];
    const until = ['active', 'past_due'].includes(subscription.status)
      ? Math.max(0, ...subscription.items.data.filter(item => prices.includes(item.price.id) &&
          Number.isSafeInteger(item.current_period_end))
        .map(item => item.current_period_end * 1000))
      : 0;
    const paid = subscription.latest_invoice?.status === 'paid';
    ledger.saveStripeEvent(event.id, now, id, account, until,
      subscription.status === 'active' && !paid ? 'past_due' : subscription.status);
    return {received: true};
  });
}
