"""Synchronise les reçus GitHub avec le registre privé du Worker, puis mesure les vidéos dues."""
import argparse
from datetime import datetime, timezone
from io import BytesIO
import json
import os
from pathlib import Path
import subprocess
from zipfile import BadZipFile, ZipFile

import requests
from performance import horizon_mesure, rapport

BASE = "https://video-automation.emilienzabukovec09.workers.dev/api/stats"


def github(*args):
    return subprocess.check_output(["gh", *args], text=True, encoding="utf-8")


def artefacts(repo, branche):
    route = f"repos/{repo}/actions/artifacts?name=references-publication&per_page=100"
    pages = json.loads(github("api", "--paginate", "--slurp", route))
    for page in pages:
        for a in page["artifacts"]:
            run = a.get("workflow_run") or {}
            if not a["expired"] and run.get("head_branch") == branche and run.get("head_repository_id") == run.get("repository_id"):
                yield a


def appel(session, methode, route, **kwargs):
    r = session.request(methode, f"{BASE}/{route}", timeout=45, allow_redirects=False, **kwargs)
    if r.status_code != 200:
        raise RuntimeError(f"{route} : HTTP {r.status_code}")
    return r.json()


def pages(session, route):
    curseur = None
    while True:
        page = appel(session, "GET", route, params={"cursor": curseur})
        yield from page["lignes"]
        curseur = page["curseur"]
        if not curseur:
            return


def importer(session, repo, branche):
    faits = set(pages(session, "artefacts"))
    erreurs = []
    for a in artefacts(repo, branche):
        identifiant = str(a["id"])
        if identifiant in faits:
            continue
        run = str(a["workflow_run"]["id"])
        try:
            detail = json.loads(github("api", f"repos/{repo}/actions/runs/{run}"))
            if (detail["path"] != ".github/workflows/video-du-jour.yml" or detail["event"] not in
                    ("schedule", "workflow_dispatch") or detail["head_branch"] != branche):
                continue
            contenu = subprocess.check_output(["gh", "api", f"repos/{repo}/actions/artifacts/{identifiant}/zip"])
            with ZipFile(BytesIO(contenu)) as archive:
                fichiers = [f for f in archive.infolist() if f.filename.endswith(".publications.json")]
                if not fichiers:
                    raise ValueError("Reçu introuvable")
                for f in fichiers:
                    lignes = json.loads(archive.read(f).decode("utf-8-sig"))
                    if not isinstance(lignes, list) or not lignes:
                        raise ValueError("Reçu vide ou illisible")
                    for pub in lignes:
                        appel(session, "POST", "recu", json=pub)
            appel(session, "POST", "importe", json={"id": identifiant})
        except (OSError, ValueError, RuntimeError, BadZipFile, subprocess.SubprocessError) as e:
            erreurs.append(f"Artefact {identifiant} : {e}")
    return erreurs


def synchroniser(session, repo, branche):
    erreurs = []
    try:
        erreurs.extend(importer(session, repo, branche))
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as e:
        erreurs.append(f"Import : {e}")
    maintenant = datetime.now(timezone.utc)
    for pub in pages(session, "publications"):
        if horizon_mesure(pub["publie_le"], maintenant) is not None:
            try:
                appel(session, "POST", "relever", json={k: pub[k] for k in ("plateforme", "video_id")})
            except (OSError, RuntimeError) as e:
                erreurs.append(f"{pub['plateforme']}/{pub['video_id']} : {e}")
    if erreurs:
        raise SystemExit("\n".join(erreurs))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    export = parser.add_mutually_exclusive_group()
    export.add_argument("--export", type=Path, help="Exporter les observations privées au format JSONL")
    export.add_argument("--export-publications", type=Path, help="Exporter les reçus privés du planificateur au format JSON")
    args = parser.parse_args()
    with requests.Session() as session:
        session.headers["Authorization"] = "Bearer " + os.environ["VIDEO_API_KEY"]
        if args.export_publications:
            lignes = list(pages(session, "publications"))
            args.export_publications.write_text(json.dumps(lignes, ensure_ascii=False) + "\n", encoding="utf-8")
        elif args.export:
            with args.export.open("w", encoding="utf-8") as f:
                for mesure in pages(session, "mesures"):
                    f.write(json.dumps(mesure, ensure_ascii=False) + "\n")
        else:
            synchroniser(session, os.environ["GITHUB_REPOSITORY"], os.environ["BRANCHE_PUBLICATION"])
            mesures_j30 = [m for m in pages(session, "mesures") if m.get("horizon_jours") == 30]
            appel(session, "POST", "decisions", json=rapport(mesures_j30))


if __name__ == "__main__":
    main()
