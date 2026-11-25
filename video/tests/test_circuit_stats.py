import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch
from zipfile import ZipFile

VIDEO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VIDEO))
import metadonnees_video as meta
import performance
import synchroniser_stats as sync


class CircuitStatistiques(unittest.TestCase):
    def test_du_recu_au_rapport_j30(self):
        publication = datetime(2026, 1, 1, tzinfo=timezone.utc)
        instant = publication + timedelta(days=30)
        with tempfile.TemporaryDirectory() as dossier:
            mp4 = Path(dossier) / "pilote.mp4"
            references = meta.references_confirmees("#Shorts", "", "#initial",
                {"success": True, "videoId": "abcdefghijk"}, {"success": True, "mediaId": "12345"})
            fiche = dict(id_video="pilote", categorie="ville_du_jour", carburant="e10", musique=0, duree_s=23)
            meta.ecrire_recu(mp4, fiche, references, publication)
            recu = mp4.with_suffix(".publications.json")
            archive = io.BytesIO()
            with ZipFile(archive, "w") as zipfile:
                zipfile.write(recu, recu.name)

            with subprocess.Popen(["node", str(VIDEO / "tests/worker_stats_local.mjs")],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding="utf-8") as worker:
                def transport(methode, url, **options):
                    msg = dict(methode=methode, url=url, headers={"Authorization":"Bearer test"},
                               instant=instant.isoformat())
                    if "json" in options:
                        msg["body"] = options["json"]
                    worker.stdin.write(json.dumps(msg) + "\n")
                    worker.stdin.flush()
                    reponse = json.loads(worker.stdout.readline())
                    return Mock(status_code=reponse["status"], json=lambda: reponse["data"])

                session = Mock()
                session.request.side_effect = transport
                try:
                    with patch.object(sync, "artefacts", return_value=[{"id":1,"workflow_run":{"id":2}}]), \
                         patch.object(sync, "github", return_value=json.dumps(dict(path=".github/workflows/video-du-jour.yml",
                             event="schedule", head_branch="main"))), \
                         patch.object(sync.subprocess, "check_output", return_value=archive.getvalue()), \
                         patch.object(sync, "datetime") as horloge:
                        horloge.now.return_value = instant
                        for _ in range(2):
                            sync.synchroniser(session, "test/test", "main")
                    mesures = list(sync.pages(session, "mesures"))
                finally:
                    worker.stdin.close()
            self.assertEqual(worker.returncode, 0)
            self.assertEqual(len(mesures), 2)
            fichier = Path(dossier) / "mesures.jsonl"
            fichier.write_text("".join(json.dumps(m) + "\n" for m in mesures), encoding="utf-8")
            sortie = io.StringIO()
            with patch.object(sys, "argv", ["performance.py", str(fichier)]), redirect_stdout(sortie):
                performance.main()
            rapport = json.loads(sortie.getvalue())
            for rubrique, champ, valeur in (("categories","categorie","ville_du_jour"), ("musiques","musique","0"),
                    ("carburants","carburant","e10"), ("durees","tranche_duree","15 à moins de 30 s")):
                self.assertEqual([(r["plateforme"], r[champ], r["vues_medianes"], r["horizon_jours"], r["videos"])
                                  for r in rapport[rubrique]], [("instagram", valeur, 24, 30, 1), ("youtube", valeur, 0, 30, 1)])
            self.assertEqual([(r["plateforme"],r["hashtag"]) for r in rapport["hashtags"]],
                             [("instagram","#reel"),("youtube","#shorts")])
            self.assertEqual(rapport["experiences"], [])
