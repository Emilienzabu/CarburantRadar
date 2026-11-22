import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from performance import (analyser, choisir_musique, decrire, decrire_durees,
                         decrire_hashtags, experience_musique, horizon_mesure)


PARUTION = datetime(2026, 10, 1, 10, tzinfo=timezone.utc)


def mesure(plateforme, video, heures=720, vues=300, **champs):
    return dict(plateforme=plateforme, video_id=video, publie_le=PARUTION.isoformat(),
                mesure_le=(PARUTION + timedelta(hours=heures)).isoformat(),
                organique=True, vues=vues, **champs)


class HorizonsTest(unittest.TestCase):
    def test_bornes_mesure_en_temps_ecoule(self):
        attendus = {23.99: None, 24: 1, 36: None, 72: 3, 84: None,
                    167.99: None, 168: 7, 179.99: 7, 180: None, 336: 14, 348: None,
                    719.99: None, 720: 30, 731.99: 30, 732: None}
        for heures, horizon in attendus.items():
            with self.subTest(heures=heures):
                precise = PARUTION + timedelta(hours=heures)
                self.assertEqual(horizon_mesure(PARUTION, precise.isoformat()), horizon)

    def test_categorie_garde_les_deux_horizons_pour_une_video(self):
        j7 = mesure("youtube", "video", heures=168, vues=300, categorie="ville-du-jour")
        j30 = mesure("youtube", "video", heures=720, vues=520, categorie="ville-du-jour",
                     horizon_jours=30)
        resultat = decrire([j7, j30])
        self.assertEqual([(r["horizon_jours"], r["vues_medianes"]) for r in resultat],
                         [(7, 300), (30, 520)])
        self.assertNotIn("horizon_jours", j7)
        with self.assertRaisesRegex(ValueError, "Plusieurs mesures"):
            decrire([j7, j7])
        with self.assertRaisesRegex(ValueError, "Horizon incompatible"):
            decrire([dict(j30, horizon_jours=7)])

    def test_hashtags_normalises_sans_melanger_plateformes_ou_horizons(self):
        lignes = [
            mesure("instagram", "video", hashtags=["#Radar", " #RADAR ", "Éco", "E\u0301CO"]),
            mesure("tiktok", "video", hashtags=["#RADAR"], vues=990),
            mesure("instagram", "video", heures=168, hashtags=["#radar"], vues=100),
        ]
        resultat = {(r["plateforme"], r["horizon_jours"], r["hashtag"]):
                    (r["videos"], r["vues_medianes"]) for r in decrire_hashtags(lignes)}
        self.assertEqual(resultat, {
            ("instagram", 7, "#radar"): (1, 100),
            ("instagram", 30, "#radar"): (1, 300),
            ("instagram", 30, "#éco"): (1, 300),
            ("tiktok", 30, "#radar"): (1, 990),
        })

    def test_durees_reparties_par_plateforme(self):
        lignes = [
            mesure("instagram", "court", duree_s=14.9),
            mesure("instagram", "moyen", duree_s=15),
            mesure("instagram", "long", duree_s=30),
            mesure("instagram", "aussi-long", duree_s=59.9),
            mesure("instagram", "minute", duree_s=60),
            mesure("youtube", "court", duree_s=10),
            mesure("instagram", "invalide", duree_s=float("nan")),
            mesure("instagram", "manquante"),
        ]
        groupes = {(r["plateforme"], r["tranche_duree"]): r["videos"] for r in decrire_durees(lignes)}
        self.assertEqual(groupes, {
            ("instagram", "moins de 15 s"): 1,
            ("instagram", "15 à moins de 30 s"): 1,
            ("instagram", "30 à moins de 60 s"): 2,
            ("instagram", "60 s et plus"): 1,
            ("youtube", "moins de 15 s"): 1,
        })

    def test_apprentissage_exige_j30_et_les_plateformes_actives(self):
        lignes = []
        for plateforme in ("youtube", "instagram"):
            for i in range(35):
                for ordre in (1, 2):
                    essai = experience_musique("detour", 3, 8, str(i), ordre)
                    vues = 180 if essai["bras"] == "variante" else 100
                    for heures in (168, 720):
                        lignes.append(mesure(plateforme, f"{i}-{ordre}", heures,
                                             vues=vues, experience=essai))
        decisions = analyser(lignes)
        self.assertEqual(len(decisions), 4)
        self.assertTrue(all(d["paires"] == 35 for d in decisions))
        self.assertEqual(choisir_musique([8], 3, decisions, "1", "detour"), 8)
        j7 = [r for r in decisions if r["horizon_jours"] == 7]
        self.assertFalse(any(r["retenu"] for r in j7))
        self.assertEqual(choisir_musique([8], 3, j7, "1", "detour"), 3)
        self.assertEqual(choisir_musique([8], 3, decisions, "1", "detour",
                                       plateformes={"youtube", "instagram", "tiktok"}), 3)
