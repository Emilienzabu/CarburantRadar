#!/usr/bin/env python3
"""Raccourci racine : `python generate.py` lance generator/generate.py (mêmes options : --data, --root).

Repli ajouté : si la source espagnole/italienne est HS, qu'aucun cache n'existe et que les pages publiées ne sont pas
récupérables, on publie les pages historiques de ce pays au lieu de faire échouer tout le run (le reste du site est mis à jour).
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
GEN = os.path.join(ROOT, "generator")
sys.path.insert(0, GEN)

import generate as g  # noqa: E402  (generator/generate.py)

_orig_reuse = g.reuse_published


def _reuse_or_legacy(root, old_paths, prefix, hub):
    try:
        return _orig_reuse(root, old_paths, prefix, hub)
    except Exception as e:
        pays = prefix.strip("/")
        print(f"AVERTISSEMENT : pages {pays} publiées introuvables ({e}) ; repli sur les pages historiques.", file=sys.stderr)
        conf = json.load(open(os.path.join(GEN, "villes.json"), encoding="utf-8"))
        cfg = conf["pays"][pays]
        vs = [v for v in conf["villes"] if v["pays"] == pays]
        template = open(os.path.join(GEN, "template.html"), encoding="utf-8").read()
        entries = []
        html, _, _ = g.render_hub_simple(pays, vs, cfg)
        g.write(root, f"/{pays}/{cfg['dossier']}/", html)
        entries.append((f"{g.SITE_URL}/{pays}/{cfg['dossier']}/", "monthly", "0.6", None))
        for v in vs:
            g.write(root, f"/{pays}/{cfg['dossier']}/{v['slug']}/", g.legacy_page(v, cfg, template))
            entries.append((f"{g.SITE_URL}/{pays}/{cfg['dossier']}/{v['slug']}/", "monthly", "0.7", None))
        return entries


g.reuse_published = _reuse_or_legacy

if __name__ == "__main__":
    sys.exit(g.main())
