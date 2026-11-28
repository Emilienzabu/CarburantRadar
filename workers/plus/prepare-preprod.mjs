import {copyFile, mkdir, readFile, writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {fileURLToPath} from 'node:url';

const root = fileURLToPath(new URL('../../', import.meta.url));
const out = fileURLToPath(new URL('.preprod-assets/', import.meta.url));
const files = [
  'france/plus.js', 'france/plus.css', 'france/plus-rewarded.mjs', 'service-worker.js',
  'icons/icon-192.png', 'icons/icon-512.png', 'icons/icon-512-maskable.png', 'icons/icon-96.png',
];
await Promise.all(['france', 'icons'].map(directory => mkdir(resolve(out, directory), {recursive: true})));
await Promise.all(files.map(file => copyFile(resolve(root, file), resolve(out, file))));

const input = await readFile(resolve(root, 'france/index.html'), 'utf8');
const html = input
  .replace(/<script\b[^>]*\bsrc=["'][^"']*(?:googlesyndication\.com|googletagmanager\.com|track\.js)[^"']*["'][^>]*>\s*<\/script>/gi, '')
  .replace(/<meta\b[^>]*name=["']google-adsense-account["'][^>]*>/gi, '')
  .replace(/<script>\s*window\.dataLayer\b[\s\S]*?<\/script>/, '')
  .replace(/var PROXY='https:\/\/carburant-proxy\.[^']+';/, 'var PROXY=location.origin;');
if (!html.includes('var PROXY=location.origin;') ||
    /googlesyndication\.com|googletagmanager\.com|googletagservices\.com|securepubads\.g\.doubleclick\.net|gtag\(/i.test(html)) {
  throw new Error('La page de préproduction contient encore une intégration publicitaire ou analytique, ou le proxy historique.');
}
await writeFile(resolve(out, 'france/index.html'), html.replace(/<title>/, '<title>Préproduction · '));
const manifest = JSON.parse(await readFile(resolve(root, 'manifest.json'), 'utf8'));
Object.assign(manifest, {name: 'CarburantRadar Plus · Préproduction', short_name: 'CR Test', start_url: './france/'});
await writeFile(resolve(out, 'manifest.json'), JSON.stringify(manifest));
