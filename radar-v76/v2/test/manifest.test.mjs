// Intégrité de l'import : chaque fichier de prototype/ == fichier de l'archive d'origine (SHA-256),
// et les 3 bundles navigateur (non versionnés) se reconstruisent à l'identique.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync, mkdtempSync, existsSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const manifest = JSON.parse(readFileSync(join(root, 'MANIFEST.sha256.json'), 'utf8'));
const sha = (p) => createHash('sha256').update(readFileSync(p)).digest('hex');

test('prototype/ : tous les fichiers non générés correspondent au SHA-256 de l’archive', () => {
  let checked = 0;
  for (const [name, hash] of Object.entries(manifest.files)) {
    if (manifest.generated.includes(name)) continue;
    assert.ok(existsSync(join(root, 'prototype', name)), 'manquant : ' + name);
    assert.equal(sha(join(root, 'prototype', name)), hash, name); checked++;
  }
  assert.ok(checked >= 70);
});
test('prototype/ : aucun fichier en plus ou en moins (hors bundles générés)', () => {
  const present = readdirSync(join(root, 'prototype')).filter((n) => !manifest.generated.includes(n)).sort();
  assert.deepEqual(present, Object.keys(manifest.files).filter((n) => !manifest.generated.includes(n)).sort());
});
test('bundles navigateur : reconstruits par tools/build-browser.js à l’identique de l’archive', () => {
  const out = mkdtempSync(join(tmpdir(), 'bundles-'));
  execFileSync('node', [join(root, 'tools', 'build-browser.js'), join(root, 'prototype'), out]);
  for (const name of manifest.generated) assert.equal(sha(join(out, name)), manifest.files[name], name);
});
