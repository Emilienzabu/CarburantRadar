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

        def rendre(s, slot, chemin, captures, **options):
            fiche = {**{k: s[k] for k in ("categorie", "sujet", "villes", "carburant")},
                     "id_video": slot, "sha256": "a" * 64}
            chemin.with_suffix(".creation.json").write_text(json.dumps(fiche), encoding="utf-8")

        def reserver(session, methode, route, json):
            self.assertEqual((methode, route), ("POST", "editorial"))
            reservations.append(json)
            return {"reserve": True}

        def worker(session, methode, route, **options):
            if (methode, route) == ("GET", "decisions"):
                return {"experiences": []}
            return reserver(session, methode, route, **options)

        with TemporaryDirectory() as dossier, \
                patch.object(q, "pages", side_effect=lambda _, route: iter(reservations if route == "editorial" else [])), \
                patch.object(q, "preparer", return_value=[sujet]) as preparer, \
                patch.object(q, "rendre", side_effect=rendre), \
                patch.object(q, "appel", side_effect=worker), \
                patch.object(q, "publier", return_value={"etat": "incertain"}) as publier:
            sortie = Path(dossier) / "matin.mp4"
            with self.assertRaisesRegex(RuntimeError, "incertain"):
                q.executer(None, "test", jour, "matin", sortie, instant)
            self.assertEqual(reservations[0]["id_video"], f"{jour}:matin")
            self.assertEqual(publier.call_args.kwargs["url"], q.URL_EDITORIALE)
            q.executer(None, "test", jour, "matin", sortie, instant)
            publier.assert_called_once()
            preparer.assert_called_once()

    def test_paires_fermees_avant_changement_de_facteur(self):
        sujet = {"categorie": "ville_du_jour"}
        premier = q.experience_du_jour(sujet, [], [])
        second = q.experience_du_jour(sujet, [{"experience": premier}], [])
        self.assertEqual(premier["paire"], second["paire"])
        self.assertEqual({premier["bras"], second["bras"]}, {"temoin", "variante"})
        self.assertEqual(premier["facteur"], "musique")
        troisieme = q.experience_du_jour(sujet, [{"experience": premier}, {"experience": second}], [])
        self.assertEqual(troisieme["facteur"], "hashtag")
        preuve = dict(horizon_jours=30, facteur="musique", contexte="ville_du_jour",
                      temoin=3, variante=8, retenu=True, paires=30, gain=.30, p=.01)
        yt = dict(preuve, plateforme="youtube")
        ig = dict(preuve, plateforme="instagram")
        self.assertEqual(q.experience_du_jour(sujet, [], [yt])["facteur"], "musique")
        self.assertEqual(q.experience_du_jour(sujet, [], [yt, ig])["facteur"], "hashtag")

    def test_hashtag_favorise_seulement_sur_la_plateforme_confirmee(self):
        sujet = {"categorie": "ville_du_jour", "carburant": "e10", "donnees": dict(
            commune="Lyon", prix_litre=1.62, adresse="10 rue Test", stations=4)}
        preuve = dict(horizon_jours=30, facteur="hashtag", contexte="ville_du_jour",
                      temoin="", variante=q.HASHTAG_VILLE, retenu=True, paires=30, gain=.30, p=.01,
                      plateforme="instagram")
        slot = next(str(i) for i in range(10) if not q.garder_temoin(f"{i}/hashtag"))
        _, yt, ig = q.textes_publication(sujet, slot, [preuve])
        self.assertNotIn(q.HASHTAG_VILLE, yt)
        self.assertIn(q.HASHTAG_VILLE, ig)
        _, yt, ig = q.textes_publication(sujet, slot, [preuve],
                                       {"facteur": "musique", "bras": "variante"})
        self.assertNotIn(q.HASHTAG_VILLE, yt)
        self.assertNotIn(q.HASHTAG_VILLE, ig)
