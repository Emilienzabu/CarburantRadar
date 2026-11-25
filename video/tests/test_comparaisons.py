import sys
import unittest
from pathlib import Path

VIDEO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VIDEO))

from comparaisons import comparer


class TestComparaisons(unittest.TestCase):
    def test_compare_des_prix_archives_du_meme_carburant(self):
        historique = {"days": {
            "2026-11-18": {"a": {"e10": ["c", 2, 1.8, 1.7]}},
            "2026-11-19": {"a": {"e10": ["c", 2, 1.9, 1.85], "gazole": ["c", 3, 2.0, 1.95]}},
        }}
        resultat = comparer(historique, "e10", ("a", "2026-11-18"), ("a", "2026-11-19"))
        self.assertEqual(resultat["categorie"], "ville_avant_maintenant")
        self.assertEqual(resultat["valeurs"][-1]["prix"], 1.85)
        self.assertEqual(resultat["ecart"], .15)

    def test_comparaison_sans_portee_melangee_ni_date_differente(self):
        historique = {"days": {"2026-11-18": {"a": {"e10": ["c", 2, 1.8, 1.7]},
                                               "b": {"e10": ["r", 3, 1.9, 1.8]}}}}
        with self.assertRaisesRegex(ValueError, "Couverture communale"):
            comparer(historique, "e10", ("a", "2026-11-18"), ("b", "2026-11-18"))
        with self.assertRaisesRegex(ValueError, "même date"):
            comparer(historique, "e10", ("a", "2026-11-18"), ("b", "2026-11-19"))
