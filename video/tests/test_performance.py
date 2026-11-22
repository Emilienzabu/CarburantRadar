import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collecte_stats import collecter, compteurs
from performance import analyser, choisir_musique, experience_musique
from planning_editorial import Sujet, choisir


class TestPerformance(unittest.TestCase):
    def lignes(self, nb):
        for plateforme in ("youtube", "instagram", "tiktok"):
            for i in range(nb):
                for ordre in (1, 2):
                    essai = experience_musique("detour", 3, 8, str(i), ordre)
                    yield dict(plateforme=plateforme, video_id=f"{i}-{ordre}",
                               publie_le="2026-10-01T10:00:00+00:00", mesure_le="2026-10-08T10:00:00+00:00",
                               organique=True, vues=180 if essai["bras"] == "variante" else 100,
                               experience=essai)

    def test_preuve_sur_les_trois_plateformes_et_temoin_conserve(self):
        decisions = analyser(self.lignes(35))
        self.assertEqual(len(decisions), 3)
        self.assertTrue(all(d["retenu"] for d in decisions))
        valeurs = {choisir_musique([8], 3, decisions, str(i), "detour") for i in range(100)}
        self.assertEqual(valeurs, {3, 8})
        self.assertEqual(choisir_musique([8], 3, decisions[:2], "1", "detour"), 3)
        self.assertEqual(choisir_musique([8], 3, decisions, "1", "rayon"), 3)

    def test_trop_peu_donnees_ou_mauvais_age(self):
        self.assertFalse(any(d["retenu"] for d in analyser(self.lignes(29))))
        self.assertEqual(analyser([{**l, "mesure_le": l["publie_le"]} for l in self.lignes(35)]), [])

    def test_doublon_refuse(self):
        ligne = next(self.lignes(1))
        with self.assertRaises(ValueError):
            analyser([ligne, ligne])

    def test_collecte_j7_sans_doublon(self):
        maintenant = datetime(2026, 11, 12, 12, tzinfo=timezone.utc)
        lire = Mock(return_value={"vues": 160})
        mesures = []
        publications = [dict(plateforme="tiktok", video_id="123",
                             publie_le=(maintenant - timedelta(days=7)).isoformat())]
        for _ in range(2):
            self.assertEqual(collecter(publications, mesures, {"tiktok": "test"}, maintenant, lire=lire), [])
        lire.assert_called_once()
        self.assertEqual(mesures[0]["vues"], 160)

    def test_adaptateurs_normalisent_les_compteurs(self):
        reponses = {
            "youtube": {"items": [{"id": "123", "statistics": {"viewCount": "150"}}]},
            "tiktok": {"error": {"code": "ok"}, "data": {"videos": [{"id": "123", "view_count": 150}]}},
            "instagram": {"data": [{"name": "views", "values": [{"value": 150}]}]},
        }
        for plateforme, payload in reponses.items():
            appeler = Mock()
            appeler.return_value.json.return_value = payload
            self.assertEqual(compteurs(plateforme, "123", "test", appeler, "v25.0"), {"vues": 150})
            self.assertEqual(appeler.call_args.kwargs["headers"]["Authorization"], "Bearer test")


class TestPlanning(unittest.TestCase):
    def test_unicite_commune_et_rotation_par_categorie(self):
        historique = [(date(2026, 10, 31), Sujet("ville_du_jour", ("45234",), "gazole"))]
        candidats = [Sujet("ville_contre_ville", ("45234", "35238"), "sp98"),
                     Sujet("ville_du_jour", ("35238",), "gazole"),
                     Sujet("ville_du_jour", ("49007",), "e10"),
                     Sujet("ville_du_jour", ("75056",), "sp98")]
        choisis = choisir(date(2026, 11, 1), candidats, historique)
        self.assertEqual([s.carburant for s in choisis], ["e10", "sp98"])

    def test_plafond_et_idempotence_pour_jour_complet(self):
        jour = date(2026, 11, 8)
        historique = [(date(2026, 11, 2), Sujet("astuce", sujet="a")),
                      (date(2026, 11, 5), Sujet("astuce", sujet="b"))]
        candidats = [Sujet("astuce", sujet="c"), Sujet("fonctionnement", sujet="radar"),
                     Sujet("fonctionnement", sujet="radar"), Sujet("ville_du_jour", ("35238",), "e10")]
        choix = choisir(jour, candidats, historique)
        self.assertEqual([s.categorie for s in choix], ["fonctionnement", "ville_du_jour"])
        self.assertEqual(choisir(jour, candidats, historique + [(jour, s) for s in choix]), [])
