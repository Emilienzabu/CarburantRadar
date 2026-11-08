"""Générateur <-> Worker avec journal anti-doublon : champs envoyés, lecture des nouvelles réponses, aucun réessai.
Aucun accès réseau, aucune publication : le Worker est simulé. Les réponses simulées reprennent le format des tests
du Worker (workers/video-automation/test) ; les anciennes réponses (sans champ `etat`) restent couvertes par
test_integration_publication.py."""
import hashlib
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_integration_publication as base  # noqa: E402  (module importé, pas la classe : pas de doublon de tests)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import generate_video as gv  # noqa: E402


def setUpModule():
    base._CACHE.clear()          # le cache de MP4 de test est partagé avec test_integration_publication : repartir de zéro


def tearDownModule():
    base.tearDownModule()        # supprime les MP4 temporaires de ce module
    base._CACHE.clear()          # et que le module suivant n'en réutilise aucun


def worker(corps, statut=200):
    return lambda url, **kw: base.Reponse(corps, statut)


YT = {"success": True, "remote_id": "yt1", "videoId": "yt1", "url": "https://youtu.be/yt1"}
IG = {"success": True, "remote_id": "ig1", "mediaId": "ig1"}


@unittest.skipUnless(base.FFMPEG, "ffmpeg/ffprobe absents")
class ProtocoleWorker(unittest.TestCase):
    lancer = base.FluxDePublication.lancer

    def un_envoi(self, corps, statut=200):
        code, appels, log, resume, _ = self.lancer(post=worker(corps, statut))
        self.assertEqual(len(appels), 1, "un seul envoi : jamais de réessai")
        return code, appels, log, resume

    def test_la_requete_porte_slot_id_et_sha256_en_plus_des_champs_historiques(self):
        _, appels, _, _ = self.un_envoi({"etat": "complet", "rejoue": False, "youtube": YT, "instagram": IG})
        d = appels[0]
        self.assertRegex(d["slot_id"], r"^\d{4}-\d{2}-\d{2}:(matin|soir)$")
        self.assertRegex(d["sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(d["profile"], "carburant")
        self.assertTrue(d["title"] and d["description"] and d["caption"])

    def test_empreinte_sha256_streaming(self):
        with tempfile.TemporaryDirectory() as t:
            f = Path(t) / "x.mp4"
            f.write_bytes(b"abc" * 1_000_000)
            self.assertEqual(gv.empreinte_sha256(str(f)), hashlib.sha256(b"abc" * 1_000_000).hexdigest())

    def test_complet(self):
        code, _, log, resume = self.un_envoi({"etat": "complet", "rejoue": False, "youtube": YT, "instagram": IG})
        self.assertEqual(code, 0, log)
        self.assertIn("**complet**", resume)

    def test_rejeu_d_un_creneau_deja_publie_est_un_succes_sans_nouvelle_publication(self):
        code, _, log, resume = self.un_envoi({"etat": "complet", "rejoue": True, "youtube": YT, "instagram": IG})
        self.assertEqual(code, 0, log)
        self.assertIn("rejeu en lecture seule", log)
        self.assertIn("lecture seule", resume)

    def test_creneau_bloque_n_est_pas_un_echec_de_publication_a_relancer(self):
        for corps in ({"etat": "bloque", "code": "creneau_en_cours"}, {"etat": "bloque", "code": "reconciliation_requise"},
                      {"etat": "bloque", "code": "creneau_clos_sans_publication"}):
            with self.subTest(code=corps["code"]):
                code, _, _, resume = self.un_envoi(corps, 409)
                self.assertIn("BLOQUÉ", str(code))
                self.assertIn(corps["code"], str(code))
                self.assertIn("aucun envoi automatique", str(code))
                self.assertIn("doublon", resume)

    def test_refus_avant_publication(self):
        for corps, http in (({"etat": "refuse", "code": "sha256_different_du_contenu"}, 400),
                            ({"etat": "refuse", "code": "ledger_non_configure"}, 503),
                            ({"etat": "refuse", "code": "stockage_indisponible"}, 500)):
            with self.subTest(code=corps["code"]):
                code, _, _, resume = self.un_envoi(corps, http)
                self.assertIn("avant toute publication", str(code))
                self.assertIn("rien n'est publié", str(code))
                self.assertIn("rien n'a été publié", resume)

    def test_tentative_non_confirmee_avec_une_plateforme_confirmee_est_partielle(self):
        corps = {"etat": "reconciliation_requise", "rejoue": False, "youtube": YT,
                 "instagram": {"success": False, "remote_id": None, "enregistre": True, "tentee": True}}
        code, _, log, resume = self.un_envoi(corps, 502)
        self.assertEqual(code, 0)
        self.assertIn("::warning::Publication PARTIELLE (YouTube=True, Instagram=False)", log)
        self.assertIn("**partiel**", resume)

    def test_tentative_non_confirmee_sans_aucune_confirmation_bloque_le_creneau(self):
        corps = {"etat": "reconciliation_requise", "rejoue": False, "youtube": {"success": False, "remote_id": None},
                 "instagram": {"success": False, "tentee": False}}
        code, _, _, _ = self.un_envoi(corps, 502)
        self.assertIn("BLOQUÉ", str(code))

    def test_incertain_du_worker_et_etat_inconnu_ne_sont_jamais_relances(self):
        for corps in ({"etat": "incertain", "code": "erreur_interne"}, {"etat": "inventé"}):
            with self.subTest(etat=corps["etat"]):
                code, _, _, _ = self.un_envoi(corps, 500)
                self.assertIn("INCERTAIN", str(code))
                self.assertIn("AVANT de relancer", str(code))

    def test_complet_declare_sans_les_deux_confirmations_n_est_pas_un_succes(self):
        code, _, _, _ = self.un_envoi({"etat": "complet", "youtube": YT, "instagram": {"success": False}})
        self.assertIn("INCERTAIN", str(code))


class Interpretation(unittest.TestCase):
    def test_ancien_worker_sans_champ_etat_est_ignore_par_l_interpreteur(self):
        self.assertIsNone(gv.interpreter_reponse_worker({"youtube": {"success": True}, "instagram": {"success": True}}, 200))


if __name__ == "__main__":
    unittest.main()
