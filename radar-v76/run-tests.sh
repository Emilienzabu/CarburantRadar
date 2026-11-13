#!/bin/sh
# Lance toute la validation locale. Aucun accès réseau, aucun secret. Node >= 22.5 requis (node:sqlite).
set -e
cd "$(dirname "$0")"
node tools/build-browser.js prototype prototype        # bundles navigateur (générés, non versionnés)
echo "== prototype V76 (541 tests attendus)"
(cd prototype && node --test *.test.js)
echo "== V2 (snapshot, garage, intégration, manifeste)"
(cd v2 && node --test test/*.test.mjs)
echo "== audit d'intégration (releaseReady=false attendu tant que les preuves réelles manquent)"
(cd prototype && node integration-audit.js)
