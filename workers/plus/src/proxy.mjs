const routes = new Set(['/status', '/claim', '/preview', '/redeem', '/issue']);

export async function forwardPlus(request, env, headers, authenticate, isAdmin) {
  const action = new URL(request.url).pathname.slice('/plus'.length);
  const responseHeaders = {...headers, 'Cache-Control': 'no-store'};
  const fail = (error, status) => Response.json({error}, {status, headers: responseHeaders});
  if (!routes.has(action)) return fail('not_found', 404);
  if (request.method !== 'POST') return fail('method_not_allowed', 405);
  if (!env.PLUS) return fail('plus_unavailable', 503);
  const forwardedHeaders = {'Content-Type': 'application/json'};
  let payload = {};
  if (action === '/issue') {
    if (!isAdmin(request, env)) return fail('admin_required', 403);
    if (!env.PLUS_ADMIN_TOKEN) return fail('plus_unavailable', 503);
    forwardedHeaders.authorization = 'Bearer ' + env.PLUS_ADMIN_TOKEN;
    payload = await request.json().catch(() => null);
    if (!payload || Array.isArray(payload) || typeof payload !== 'object') return fail('invalid_request', 400);
  } else {
    const email = await authenticate(request, env);
    const raw = email && await env.USERS.get('user:' + email.trim().toLowerCase());
    if (!raw) return fail('account_required', 401);
    const account = JSON.parse(raw);
    const created = Number.isSafeInteger(account.cree) && account.cree > 0 ? account.cree : null;
    const key = new TextEncoder().encode(JSON.stringify([email.trim().toLowerCase(), created]));
    const hash = new Uint8Array(await crypto.subtle.digest('SHA-256', key));
    payload = {account: Array.from(hash, byte => byte.toString(16).padStart(2, '0')).join(''), created};
    if (action === '/preview' || action === '/redeem') {
      const body = await request.json().catch(() => null);
      if (typeof body?.code !== 'string' || body.code.length > 64) return fail('code_invalid', 400);
      payload.code = body.code;
    }
  }
  try {
    const result = await env.PLUS.fetch('https://plus.internal' + action, {
      method: 'POST', headers: forwardedHeaders, body: JSON.stringify(payload),
    });
    if (result.status >= 500) return fail('plus_unavailable', 503);
    return new Response(result.body, {status: result.status, headers: responseHeaders});
  } catch {
    return fail('plus_unavailable', 503);
  }
}
