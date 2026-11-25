import {createInterface} from 'node:readline';
import {statistiques} from '../cloudflare/statistiques.mjs';

const objets = new Map();
const bucket = {
  async put(key, value, options) {
    if (options.onlyIf.get('if-none-match') === '*' && objets.has(key)) return null;
    objets.set(key, value);
    return {};
  },
  async get(key) { return objets.has(key) ? {json: async () => JSON.parse(objets.get(key))} : null; },
  async head(key) { return objets.has(key); },
  async list({prefix}) {
    return {objects: [...objets.keys()].filter(key => key.startsWith(prefix)).map(key => ({key})), truncated: false};
  }
};

for await (const ligne of createInterface({input: process.stdin})) {
  const {methode, url, body, headers, instant} = JSON.parse(ligne);
  const request = new Request(url, {method: methode, body: JSON.stringify(body), headers});
  const lire = async p => p.plateforme === 'youtube' ? {vues: 0} :
    {vues: 24, hashtags: ['#reel'], hashtags_source: 'plateforme'};
  const retour = await statistiques(request, {API_KEY: 'test', VIDEO_STATS: bucket}, lire, () => Date.parse(instant));
  console.log(JSON.stringify({status: retour.status, data: await retour.json()}));
}
