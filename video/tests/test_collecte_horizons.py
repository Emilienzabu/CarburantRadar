import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from requests import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import collecte_stats


class TestCollecteHorizons(unittest.TestCase):
    def setUp(self):
        self.parution = datetime(2026, 10, 1, 10, tzinfo=timezone.utc)
        self.pub = dict(plateforme="youtube", video_id="123", publie_le=self.parution.isoformat())
        self.lire = Mock(side_effect=[{"vues": 160}, {"vues": 280}])

    def releve(self, heures, mesures):
        return collecte_stats.collecter(
            [self.pub], mesures, {"youtube": "test"},
            self.parution + timedelta(hours=heures), lire=self.lire,
        )

    def test_deux_horizons_sans_doublon(self):
        mesures = []
        for heures in (168, 179, 720, 731):
            self.assertEqual(self.releve(heures, mesures), [])
        self.assertEqual(self.lire.call_count, 2)
        self.assertEqual([(m["horizon_jours"], m["vues"]) for m in mesures], [(7, 160), (30, 280)])

    def test_suit_la_meme_video_jusqu_a_j30(self):
        mesures = []
        jours = (1, 3, 7, 14, 30)
        self.lire.side_effect = [{"vues": j * 10} for j in jours]
        for j in jours:
            self.assertEqual(self.releve(j * 24 + 2, mesures), [])
        self.assertEqual([(r["horizon_jours"], r["vues"]) for r in mesures],
                         [(j, j * 10) for j in jours])

    def test_exclut_hors_fenetre(self):
        mesures = []
        for heures in (167, 180, 719, 732):
            self.assertEqual(self.releve(heures, mesures), [])
        self.lire.assert_not_called()
        self.assertEqual(mesures, [])

    def test_mesure_ancienne_a_j7_ne_bloque_pas_j30(self):
        ancienne = {**self.pub, "vues": 42, "mesure_le": (self.parution + timedelta(days=7)).isoformat()}
        mesures = [ancienne]
        self.assertEqual(self.releve(169, mesures), [])
        self.lire.assert_not_called()
        self.assertEqual(self.releve(721, mesures), [])
        self.assertEqual(mesures, [ancienne, {**self.pub, "vues": 160, "horizon_jours": 30,
                         "mesure_le": (self.parution + timedelta(hours=721)).isoformat()}])

    def test_identifiant_et_hashtags_sont_propres_a_la_plateforme(self):
        mesures = []
        publications = [
            {**self.pub, "hashtags": ["#youtube"], "duree_s": 17},
            {**self.pub, "plateforme": "instagram", "hashtags": ["#reels"], "duree_s": 17},
            {**self.pub, "plateforme": "tiktok", "hashtags": ["#tiktok"], "duree_s": 17},
        ]
        erreurs = collecte_stats.collecter(
            publications, mesures, {"youtube": "test", "instagram": "test"},
            self.parution + timedelta(days=30), lire=self.lire,
            plateformes=collecte_stats.PLATEFORMES_ACTIVES,
        )
        self.assertEqual(erreurs, [])
        self.assertEqual(self.lire.call_count, 2)
        self.assertEqual([m["hashtags"] for m in mesures], [["#youtube"], ["#reels"]])
        self.assertEqual([m["duree_s"] for m in mesures], [17, 17])

    def test_plateformes_du_cli(self):
        with TemporaryDirectory() as dossier:
            registre, sortie = Path(dossier) / "publications.json", Path(dossier) / "mesures.jsonl"
            registre.write_text(json.dumps([self.pub]), encoding="utf-8")
            for arguments, attendues in (
                ([], ("youtube", "instagram")),
                (["--plateformes", "youtube", "tiktok"], ("youtube", "tiktok")),
            ):
                argv = ["collecte_stats", str(registre), str(sortie), *arguments]
                with patch.object(sys, "argv", argv), patch.object(collecte_stats, "collecter", return_value=[]) as collecter:
                    collecte_stats.main()
                self.assertEqual(set(collecter.call_args.kwargs["plateformes"]), set(attendues))

    def test_le_cli_conserve_les_succes_en_cas_echec_partiel(self):
        j7 = dict(horizon_jours=7, vues=50)
        j30 = dict(horizon_jours=30, vues=70)
        with TemporaryDirectory() as dossier:
            registre, sortie = Path(dossier) / "publications.json", Path(dossier) / "mesures.jsonl"
            registre.write_text("[]", encoding="utf-8")
            sortie.write_text(json.dumps(j7) + "\n", encoding="utf-8")

            def collecte_partielle(publications, mesures, *args, **kwargs):
                mesures.append(j30)
                return ["youtube/123 indisponible"]

            argv = ["collecte_stats", str(registre), str(sortie)]
            with patch.object(sys, "argv", argv), patch.object(collecte_stats, "collecter", collecte_partielle):
                with self.assertRaisesRegex(SystemExit, "youtube/123"):
                    collecte_stats.main()
            self.assertEqual([json.loads(l) for l in sortie.read_text(encoding="utf-8").splitlines()], [j7, j30])


class TestHashtagsPublies(unittest.TestCase):
    def test_youtube_demande_titre_et_description(self):
        appeler = Mock()
        appeler.return_value.json.return_value = {"items": [
            {"id": "123", "statistics": {"viewCount": "180"},
             "snippet": {"title": "Le détour #gazole", "description": "Un test #shorts"}},
        ]}
        stats = collecte_stats.compteurs("youtube", "123", "test", appeler)
        self.assertEqual(stats, {"vues": 180, "hashtags": ["#gazole", "#shorts"], "hashtags_source": "plateforme"})
        self.assertEqual(appeler.call_args.kwargs["params"]["part"], "statistics,snippet")

    def test_tiktok_demande_description(self):
        appeler = Mock()
        appeler.return_value.json.return_value = {"error": {"code": "ok"}, "data": {"videos": [
            {"id": "123", "view_count": 180, "video_description": "Un essai #tiktok"},
        ]}}
        stats = collecte_stats.compteurs("tiktok", "123", "test", appeler)
        self.assertEqual(stats["hashtags"], ["#tiktok"])
        self.assertIn("video_description", appeler.call_args.kwargs["params"]["fields"])

    def test_instagram_legende_optionnelle(self):
        appeler = Mock()
        insights, media = Mock(), Mock()
        insights.json.return_value = {"data": [{"name": "views", "values": [{"value": 180}]}]}
        media.json.return_value = {"id": "123", "caption": "Une vidéo #reels"}
        appeler.side_effect = [insights, media]
        stats = collecte_stats.compteurs("instagram", "123", "test", appeler, "v25.0")
        self.assertEqual(stats["hashtags"], ["#reels"])
        self.assertEqual(appeler.call_args.kwargs["params"], {"fields": "caption"})

        appeler.side_effect = [insights, HTTPError()]
        stats = collecte_stats.compteurs("instagram", "123", "test", appeler, "v25.0")
        self.assertEqual(stats, {"vues": 180})

    def test_une_description_sans_hashtag_remplace_les_hashtags_envoyes(self):
        appeler = Mock()
        appeler.return_value.json.return_value = {"items": [
            {"id": "123", "statistics": {"viewCount": "180"},
             "snippet": {"title": "Le détour", "description": ""}},
        ]}
        stats = collecte_stats.compteurs("youtube", "123", "test", appeler)
        self.assertEqual(stats, {"vues": 180, "hashtags": [], "hashtags_source": "plateforme"})
