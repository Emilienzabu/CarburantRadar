import json
import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

VIDEO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VIDEO))

from planning_editorial import Sujet, choisir
from planning_quotidien import fiches_communes, fiches_comparaisons, historique_editorial, planifier


JOUR = date(2026, 11, 24)
INSTANT = datetime(2026, 11, 24, 8, tzinfo=timezone.utc)
LYON = dict(slug="lyon", nom="Lyon", lat=45.764, lon=4.8357)


def station(identifiant, prix, *, ville="Lyon 3ème", lat=45.76, age=1, disponible=True):
    return dict(id=identifiant, ville=ville, lat=lat, lon=4.8357, adr=f"{identifiant} rue Test", cp="69003",
                p={"e10": prix}, m={"e10": (INSTANT - timedelta(days=age)).isoformat()},
                dispo=["e10"] if disponible else [])


class PlanQuotidien(unittest.TestCase):
    def test_minimum_du_carburant_dans_la_commune_avec_adresse(self):
        releves = [station("1", 1.65), station("2", 1.69), station("1", 1.3, age=2),
                   station("3", 1.1, ville="Villeurbanne"), station("4", 1.2, age=6),
                   station("5", 1.3, disponible=False), station("6", 1.4, lat=48.2),
                   station("7", 1.5, age=-1), station("8", 1.3, lat=float("nan"))]
        [(sujet, fiche)] = list(fiches_communes([LYON], releves, INSTANT))
        self.assertEqual((sujet.villes, sujet.carburant), (("lyon",), "e10"))
        self.assertEqual((fiche["prix_litre"], fiche["stations"]), (1.65, 2))
        self.assertIn("1 rue Test", fiche["adresse"])

    def test_deux_sujets_et_exclusion_des_communes_deja_utilisees(self):
        releves = [station("1", 1.65), station("2", 1.69)]
        plan = planifier(JOUR, [LYON], releves, {"days": {}}, [], INSTANT)
        self.assertEqual([s["categorie"] for s in plan], ["ville_du_jour", "astuce"])
        passe = [(JOUR - timedelta(days=1), Sujet("ville_contre_ville", ("lyon", "lille"), "sp98"))]
        plan = planifier(JOUR, [LYON], releves, {"days": {}}, passe, INSTANT)
        self.assertTrue(all("lyon" not in s["villes"] for s in plan))

    def test_comparaisons_verifiables_dans_l_archive_du_depot(self):
        archive = json.loads((VIDEO.parent / "france/prix-carburant/history.json").read_text(encoding="utf-8"))
        jour = date.fromisoformat(max(archive["days"]))
        fiches = list(fiches_comparaisons(archive, jour, set()))
        self.assertEqual({s.categorie for s, _ in fiches}, {"ville_contre_ville", "ville_avant_maintenant"})
        self.assertGreater(len({s.carburant for s, _ in fiches}), 1)

    def test_plafond_comparaison_sauf_ville_du_jour(self):
        passe = [(date(2026, 11, i), Sujet("ville_contre_ville", (f"a{i}", f"b{i}"), "sp98"))
                 for i in (1, 2)]
        passe += [(date(2026, 11, i), Sujet("ville_du_jour", (f"c{i}",), "e10")) for i in (1, 2)]
        comparaison = Sujet("ville_contre_ville", ("d", "e"), "sp98")
        etape = Sujet("ville_du_jour", ("lyon",), "e85")
        self.assertEqual(choisir(JOUR, [comparaison, etape], passe), [etape])

    def test_change_de_fonctionnalite_et_respecte_le_plafond(self):
        passe = [(JOUR - timedelta(days=i), Sujet("astuce", sujet=f"Astuce {i}")) for i in (1, 2)]
        passe.append((JOUR - timedelta(days=1), Sujet("fonctionnement", sujet="rayon")))
        plan = planifier(JOUR, [], [], {"days": {}}, passe, INSTANT)
        self.assertIn(("fonctionnement", "analyse"), [(s["categorie"], s["sujet"]) for s in plan])
        self.assertNotIn(("fonctionnement", "rayon"), [(s["categorie"], s["sujet"]) for s in plan])
        passe.append((JOUR - timedelta(days=2), Sujet("fonctionnement", sujet="analyse")))
        plan = planifier(JOUR, [], [], {"days": {}}, passe, INSTANT)
        self.assertNotIn("fonctionnement", {s["categorie"] for s in plan})

    def test_reconstruit_le_creneau_depuis_deux_recus(self):
        commun = dict(id_video=f"{JOUR}:matin", categorie="ville", ville="Saint-Étienne", carburant="e85")
        lignes = [{**commun, "plateforme": p} for p in ("youtube", "instagram")]
        historique, occupes = historique_editorial(lignes, JOUR)
        self.assertEqual(historique, [(JOUR, Sujet("ville_du_jour", ("saint-etienne",), "e85"))])
        self.assertEqual(occupes, {"matin"})
        with self.assertRaises(ValueError):
            historique_editorial([lignes[0], {**lignes[1], "carburant": "e10"}], JOUR)
