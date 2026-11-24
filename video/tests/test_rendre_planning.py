import sys
import unittest
from pathlib import Path

VIDEO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VIDEO))

from controle_publication import DUREE_MIN
from rendre_planning import specifier


class RendusDuPlanning(unittest.TestCase):
    def test_six_categories_et_duree_minimale(self):
        ville = {"commune": "Marseille", "prix_litre": 1.99, "adresse": "171 boulevard Paul-Claudel, Marseille"}
        comparaison = {"carburant": "gazole", "indicateur": "minimum", "valeurs": [
            {"ville": "marseille"}, {"ville": "marseille"},
        ]}
        autre_ville = {**comparaison, "valeurs": [{"ville": "marseille"}, {"ville": "lyon"}]}
        fiches = {
            "ville_du_jour": ville,
            "astuce": {"titre": "Trois conseils", "points": ["Un", "Deux", "Trois"]},
            "fonctionnement": {"scenario": "rayon"},
            "avantage": {"scenario": "detour"},
            "ville_avant_maintenant": comparaison,
            "ville_contre_ville": autre_ville,
        }
        for categorie, fiche in fiches.items():
            with self.subTest(categorie=categorie):
                defs, creer, musiques = specifier(
                    {"categorie": categorie, "carburant": "gazole", "donnees": fiche}, Path("captures"))
                self.assertGreaterEqual(sum(d["min"] for d in defs), DUREE_MIN)
                self.assertTrue(callable(creer))
                self.assertNotEqual(*musiques)
