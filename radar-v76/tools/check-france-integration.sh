#!/bin/sh
# Contrôles de france/index.html, sans réseau.
# Usage : sh radar-v76/tools/check-france-integration.sh [chemin/vers/index.html]
# Code de sortie non nul au moindre échec. Node >= 22 et Python 3 requis.
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PAGE="${1:-$ROOT/france/index.html}"
FAIL=0
echo "== page : $PAGE ($(wc -c < "$PAGE") octets)"
echo "== 1. syntaxe des scripts en ligne"
node -e '
const fs=require("fs");const h=fs.readFileSync(process.argv[1],"utf8");
const re=/<script([^>]*)>([\s\S]*?)<\/script>/g;let m,n=0,bad=0;
while((m=re.exec(h))){if(/src=|ld\+json/.test(m[1]))continue;n++;try{new Function(m[2])}catch(e){bad++;console.log("  ERREUR :",e.message)}}
console.log("  scripts en ligne :",n,"; en erreur :",bad);process.exit(bad||!n?1:0)' "$PAGE" || FAIL=1
echo "== 2. compatibilité avec generator/app_patches.py (injection véhicules au déploiement)"
python3 - "$ROOT/generator" "$PAGE" <<'PY' || FAIL=1
import sys
sys.path.insert(0, sys.argv[1])
import app_patches as a
t = open(sys.argv[2], encoding="utf-8", newline="").read()
new, st = a.patch_text("france", t)
print("  statut :", st)
ok = st.startswith("appliqué") or st.startswith("déjà intégré")
print("  résultat :", "OK" if ok else "ÉCHEC (la fonction multi-véhicules serait perdue au déploiement)")
sys.exit(0 if ok else 1)
PY
echo "== 3. marqueurs et doublons"
python3 - "$PAGE" <<'PY' || FAIL=1
import sys, re
t = open(sys.argv[1], encoding="utf-8").read()
need = ["radarFetchOSRM", "fetchOSRM", "chargerStationsRadar", "SNAPSHOT_V2_URL", "radarVehicleConfig"]
bad = 0
for k in need:
    n = len(re.findall(r"\b" + k + r"\b", t))
    print("  %-22s %s" % (k, n)); bad += (n == 0)
for fn in ["load", "render", "fetchOSRM", "radarFetchOSRM", "chargerStationsRadar", "crRankStations", "crGetVehicles"]:
    n = len(re.findall(r"function\s+" + fn + r"\s*\(", t))
    if n > 1: print("  DOUBLON : function %s défini %d fois" % (fn, n)); bad += 1
sys.exit(1 if bad else 0)
PY
echo "== 4. test de contrat V2 de la page"
if [ -f "$ROOT/france/v2-ui-contract.test.cjs" ]; then
  TMP="$(mktemp -d)"; cp "$ROOT/france/v2-ui-contract.test.cjs" "$TMP/"; cp "$PAGE" "$TMP/index.html"
  (cd "$TMP" && node --test v2-ui-contract.test.cjs 2>&1 | grep -E "^# (tests|pass|fail)") ; node --test "$TMP/v2-ui-contract.test.cjs" >/dev/null 2>&1 || FAIL=1
elif [ -f "$ROOT/radar-v76/pending-france/v2-ui-contract.test.cjs" ]; then
  TMP="$(mktemp -d)"; cp "$ROOT/radar-v76/pending-france/v2-ui-contract.test.cjs" "$TMP/"; cp "$PAGE" "$TMP/index.html"
  (cd "$TMP" && node --test v2-ui-contract.test.cjs 2>&1 | grep -E "^# (tests|pass|fail)"); node --test "$TMP/v2-ui-contract.test.cjs" >/dev/null 2>&1 || FAIL=1
else echo "  test de contrat introuvable"; FAIL=1; fi
[ "$FAIL" = 0 ] && echo "== RÉSULTAT : OK" || echo "== RÉSULTAT : ÉCHEC"
exit $FAIL
