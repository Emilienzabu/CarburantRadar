#!/usr/bin/env python3
"""Validation SEO/technique du site généré. Usage : python3 generator/validate.py [--root DIR]  (code 1 si erreurs)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audit  # noqa: E402

if __name__ == "__main__":
    root = sys.argv[sys.argv.index("--root") + 1] if "--root" in sys.argv else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    r = audit.audit(root)
    for w in r["warnings"]:
        print("AVERTISSEMENT", w)
    for e in r["errors"]:
        print("ERREUR", e)
    print(f"{len(r['info'])} pages auditées : {len(r['errors'])} erreur(s), {len(r['warnings'])} avertissement(s)")
    sys.exit(1 if r["errors"] else 0)
