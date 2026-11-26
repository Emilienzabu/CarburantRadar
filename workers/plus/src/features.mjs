export class LedgerError extends Error {
  constructor(code, status = 400) {
    super(code);
    this.code = code;
    this.status = status;
  }
}

const week = 7 * 86400000;
const fuels = ['Gazole', 'SP95', 'SP98', 'E10', 'E85', 'GPLc'];
const pushHosts = new Set(['fcm.googleapis.com', 'updates.push.services.mozilla.com', 'web.push.apple.com']);

export function extraAlert(value) {
  const {name, lat, lon, carburant, rayon, seuil, sub} = value || {};
  const endpoint = URL.canParse(sub?.endpoint) ? new URL(sub.endpoint) : null;
  const keys = sub?.keys;
  if (typeof name !== 'string' || !name.trim() || name.length > 80 ||
      !Number.isFinite(lat) || Math.abs(lat) > 90 || !Number.isFinite(lon) || Math.abs(lon) > 180 ||
      !fuels.includes(carburant) || ![5, 10, 20, 50].includes(rayon) || ![2, 3, 5, 8].includes(seuil) ||
      endpoint?.protocol !== 'https:' || !(pushHosts.has(endpoint.hostname) || endpoint.hostname.endsWith('.notify.windows.com')) || endpoint.port ||
      endpoint.username || endpoint.password || endpoint.hash || endpoint.href.length > 2000 ||
      !/^[\w-]{87}$/.test(keys?.p256dh || '') || !/^[\w-]{22}$/.test(keys?.auth || '')) {
    throw new LedgerError('extra_alert_invalid');
  }
  return {name: name.trim(), lat, lon, carburant, rayon, seuil,
    sub: {endpoint: endpoint.href, keys: {p256dh: keys.p256dh, auth: keys.auth}}};
}

export const EXTRA_ALERT_WEEK = week;
export const EXTRA_ALERT_LIMIT = 12;

export function operationId(value) {
  if (typeof value !== 'string' || !/^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/.test(value)) {
    throw new LedgerError('operation_invalid');
  }
  return value;
}
