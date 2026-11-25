import json
import sys
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import synchroniser_stats as sync


class ImportRecu(unittest.TestCase):
    def test_reprise_apres_import_partiel(self):
        contenu = BytesIO()
        with ZipFile(contenu, "w") as z:
            z.writestr("matin.publications.json", json.dumps([{"video_id":"yt"}, {"video_id":"ig"}]))
        marqueurs = set()
        envois = []
        def envoyer(session, methode, route, json):
            if route == "importe":
                marqueurs.add(json["id"])
            else:
                envois.append(json["video_id"])
                if envois == ["yt", "ig"]:
                    raise RuntimeError("service indisponible")
        with patch.object(sync, "pages", side_effect=lambda *_: iter(marqueurs)), \
             patch.object(sync, "artefacts", return_value=[{"id":22,"workflow_run":{"id":17}}]), \
             patch.object(sync, "github", return_value=json.dumps({"path":".github/workflows/video-du-jour.yml",
                 "event":"schedule","head_branch":"main"})), \
             patch.object(sync.subprocess, "check_output", return_value=contenu.getvalue()), \
             patch.object(sync, "appel", side_effect=envoyer):
            self.assertTrue(sync.importer(None,"a/b","main"))
            self.assertFalse(marqueurs)
            self.assertFalse(sync.importer(None,"a/b","main"))
            self.assertFalse(sync.importer(None,"a/b","main"))
            self.assertEqual(envois, ["yt", "ig", "yt", "ig"])
            self.assertEqual(marqueurs, {"22"})

    def test_liste_paginee(self):
        with patch.object(sync, "appel", side_effect=[{"lignes":[1],"curseur":"suite"},
                                                      {"lignes":[2],"curseur":None}]) as api:
            self.assertEqual(list(sync.pages(None, "mesures")), [1,2])
            self.assertEqual(api.call_args.kwargs["params"], {"cursor":"suite"})
