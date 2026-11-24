import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

VIDEO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VIDEO))
import quotidien as q


class CreneauEditorial(unittest.TestCase):
    def test_envoi_incertain_garde_son_sujet_a_la_relance(self):
        instant = datetime(2026, 11, 24, 11, tzinfo=timezone.utc)
        jour = instant.date()
        sujet = dict(creneau="matin", categorie="astuce", villes=[], carburant=None, sujet="Trajet",
                     donnees={"titre": "Trajet", "points": ["Prépare ton plein"]})
        reservations = []

        def rendre(s, slot, chemin, captures):
            fiche = {**{k: s[k] for k in ("categorie", "sujet", "villes", "carburant")},
                     "id_video": slot, "sha256": "a" * 64}
            chemin.with_suffix(".creation.json").write_text(json.dumps(fiche), encoding="utf-8")

        def reserver(session, methode, route, json):
            self.assertEqual((methode, route), ("POST", "editorial"))
            reservations.append(json)
            return {"reserve": True}

        with TemporaryDirectory() as dossier, \
                patch.object(q, "pages", side_effect=lambda _, route: iter(reservations if route == "editorial" else [])), \
                patch.object(q, "preparer", return_value=[sujet]) as preparer, \
                patch.object(q, "rendre", side_effect=rendre), \
                patch.object(q, "appel", side_effect=reserver), \
                patch.object(q, "publier", return_value={"etat": "incertain"}) as publier:
            sortie = Path(dossier) / "matin.mp4"
            with self.assertRaisesRegex(RuntimeError, "incertain"):
                q.executer(None, "test", jour, "matin", sortie, instant)
            self.assertEqual(reservations[0]["id_video"], f"{jour}:matin")
            self.assertEqual(publier.call_args.kwargs["url"], q.URL_EDITORIALE)
            q.executer(None, "test", jour, "matin", sortie, instant)
            publier.assert_called_once()
            preparer.assert_called_once()
