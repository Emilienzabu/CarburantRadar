"""Tests de video/geo.py (fonctions pures, sans réseau). Cas réels : villes de donnees.VILLES."""
import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import donnees  # noqa: E402
import geo  # noqa: E402

MARSEILLE = donnees.VILLES_PAR_SLUG["marseille"]
WITTELSHEIM = {"lat": 47.8000, "lon": 7.2400}   # Alsace : ~ 600 km de Marseille (le cas de l'incident rapporté)


def st(lat, lon, ville="Marseille"):
    return {"geom": {"lat": lat, "lon": lon}, "ville": ville, "adresse": "1 rue test"}


class Distances(unittest.TestCase):
    def test_distances_connues(self):
        self.assertAlmostEqual(geo.distance_km(48.8566, 2.3522, 48.8566, 2.3522), 0.0, places=6)
        # Paris-Marseille ~ 660 km (orthodromie)
        d = geo.distance_km(48.8566, 2.3522, 43.2965, 5.3698)
        self.assertTrue(655 < d < 665, d)
        # symétrie
        self.assertAlmostEqual(d, geo.distance_km(43.2965, 5.3698, 48.8566, 2.3522), places=9)
        # 1 degré de latitude ~ 111,2 km
        self.assertAlmostEqual(geo.distance_km(0, 0, 1, 0), 111.19, delta=0.1)


class RayonEtCoordonnees(unittest.TestCase):
    def test_marseille_wittelsheim_rejete(self):
        self.assertFalse(geo.station_dans_rayon(st(WITTELSHEIM["lat"], WITTELSHEIM["lon"], "Wittelsheim"), MARSEILLE))

    def test_station_au_centre_et_dans_le_rayon(self):
        self.assertTrue(geo.station_dans_rayon(st(MARSEILLE["lat"], MARSEILLE["lon"]), MARSEILLE))
        self.assertTrue(geo.station_dans_rayon(st(43.30, 5.40), MARSEILLE))   # quelques km

    def test_limite_du_rayon(self):
        # ~ 0,0001 degré de latitude = 11 m ; on place la station à 8,9 km puis 9,2 km du centre (rayon 9 km, +1 % = 9,09 km)
        dlat = lambda km: km / 111.19  # noqa: E731
        self.assertTrue(geo.station_dans_rayon(st(MARSEILLE["lat"] + dlat(8.9), MARSEILLE["lon"]), MARSEILLE))
        self.assertFalse(geo.station_dans_rayon(st(MARSEILLE["lat"] + dlat(9.2), MARSEILLE["lon"]), MARSEILLE))

    def test_coordonnees_invalides_rejetees(self):
        for geom in (None, "x", {}, {"lat": None, "lon": 5.3}, {"lat": "43.2", "lon": 5.3}, {"lat": True, "lon": 5.3},
                     {"lat": float("nan"), "lon": 5.3}, {"lat": 91, "lon": 5.3}, {"lat": 43.2, "lon": 181}):
            with self.subTest(geom=geom):
                self.assertFalse(geo.station_dans_rayon({"geom": geom}, MARSEILLE))
        self.assertFalse(geo.station_dans_rayon({}, MARSEILLE))
        self.assertFalse(geo.station_dans_rayon(None, MARSEILLE))

    def test_longitude_latitude_inversees_rejetees(self):
        self.assertFalse(geo.station_dans_rayon(st(MARSEILLE["lon"], MARSEILLE["lat"]), MARSEILLE))

    def test_filtrer_ne_remplace_rien(self):
        liste = [st(43.30, 5.40), st(WITTELSHEIM["lat"], WITTELSHEIM["lon"]), {"ville": "Marseille"}]
        gardees, rejetees = geo.filtrer(liste, MARSEILLE)
        self.assertEqual(len(gardees), 1)
        self.assertEqual(len(rejetees), 2)

    def test_toutes_les_villes_du_catalogue_ont_un_rayon_coherent(self):
        for v in donnees.VILLES:
            with self.subTest(v=v["nom"]):
                self.assertTrue(geo.station_dans_rayon(st(v["lat"], v["lon"]), v))
                self.assertFalse(geo.station_dans_rayon(st(v["lat"] + 1.0, v["lon"]), v))   # ~ 111 km plus loin


class CommuneEtDates(unittest.TestCase):
    def test_commune_jamais_remplacee_par_la_ville_annoncee(self):
        self.assertEqual(geo.commune_affichable({"ville": " aubagne "}), "Aubagne")
        for s in ({}, {"ville": None}, {"ville": "  "}, {"ville": 12}, None):
            self.assertEqual(geo.commune_affichable(s), "")

    def test_dates(self):
        maintenant = dt.datetime(2026, 11, 7, 12, 0, tzinfo=dt.timezone.utc)
        h = dt.timedelta(hours=1)
        self.assertTrue(geo.date_plausible(maintenant - h, maintenant, 5))
        self.assertTrue(geo.date_plausible(maintenant + 0.41 * h, maintenant, 5))       # décalage d'horloge observé
        self.assertFalse(geo.date_plausible(maintenant + 2 * h, maintenant, 5))        # futur lointain
        self.assertFalse(geo.date_plausible(maintenant - dt.timedelta(days=6), maintenant, 5))
        self.assertFalse(geo.date_plausible(None, maintenant, 5))
        self.assertFalse(geo.date_plausible(dt.datetime(2026, 11, 7, 11, 0), maintenant, 5))   # sans fuseau : refusée

    def test_fuseau_paris_equivalent_utc(self):
        from zoneinfo import ZoneInfo
        maintenant = dt.datetime(2026, 11, 7, 12, 0, tzinfo=dt.timezone.utc)
        maj_paris = dt.datetime(2026, 11, 7, 12, 30, tzinfo=ZoneInfo("Europe/Paris"))   # = 11:30 UTC
        self.assertTrue(geo.date_plausible(maj_paris, maintenant, 5))


if __name__ == "__main__":
    unittest.main()
