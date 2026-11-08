"""Protocole anti-doublon (slot_id + sha256) : ordre transactionnel, réponses ambiguës, reprises après crash, concurrence.

Exécuté contre le schéma candidat réel 0001 sous SQLite, avec des DOUBLES de plateformes (aucun appel réseau, aucune
publication). Le Worker JavaScript réel n'a pas été lu : ces tests fixent le comportement ATTENDU, ils ne prouvent rien
sur Cloudflare D1 ni sur les API YouTube/Instagram.
"""
import hashlib
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path

from ledger_worker_reference import Crash, FauxClient, Worker, initialiser, ouvrir

SLOT = "2026-11-07:matin"
VIDEO = b"octets-du-mp4-de-test"
SHA = hashlib.sha256(VIDEO).hexdigest()
APRES = "2026-11-07T07:00:00Z"


class Base(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.addCleanup(self._t.cleanup)
        self.db = str(Path(self._t.name) / "d1.sqlite")
        initialiser(self.db)

    def worker(self, yt="succes", ig="succes", **kw):
        self.yt, self.ig = FauxClient("youtube", yt, **kw), FauxClient("instagram", ig, **kw)
        return Worker(self.db, self.yt, self.ig)

    def etat(self):
        c = ouvrir(self.db)
        try:
            r = c.execute("SELECT status, revision FROM video_slot_reservations WHERE slot_key=?", (SLOT,)).fetchone()
            obs = {p: (s, i) for p, s, i in c.execute(
                "SELECT platform, status, remote_id FROM video_platform_results WHERE slot_key=?", (SLOT,))}
            return r, obs
        finally:
            c.close()

    def appels(self):
        return self.yt.appels, self.ig.appels


class Contrat(Base):
    def test_entrees_invalides_refusees_avant_tout_acces(self):
        w = self.worker()
        for slot, sha in [(None, SHA), ("n-importe-quoi", SHA), ("2026-13-45:matin", SHA), ("2026-11-07:midi", SHA),
                          (SLOT, None), (SLOT, SHA.upper()), (SLOT, "a" * 64)]:
            with self.subTest(slot=slot, sha=str(sha)[:6]):
                self.assertEqual(w.traiter(slot, VIDEO, sha)[0], 400)
        self.assertEqual(self.appels(), (0, 0))
        self.assertIsNone(self.etat()[0], "aucune réservation ne doit naître d'une requête invalide")

    def test_requete_ancienne_sans_slot_id_refusee(self):
        self.assertEqual(self.worker().traiter(None, VIDEO, None)[0], 400)
        self.assertEqual(self.appels(), (0, 0))

    def test_limite_connue_le_schema_accepte_une_date_impossible(self):
        """Le GLOB du schéma 0001 ne contrôle pas le calendrier : la validation (slot_valide) doit rester côté Worker."""
        c = ouvrir(self.db)
        n = c.execute("INSERT INTO video_slot_reservations(slot_key,mp4_sha256,status,created_at,updated_at) "
                      "VALUES ('2026-13-45:matin',?,'reserved','t','t')", (SHA,)).rowcount
        self.assertEqual(n, 1)


class Nominal(Base):
    def test_deux_plateformes_confirmees_puis_rejeu_en_lecture_seule(self):
        w = self.worker()
        code, corps = w.traiter(SLOT, VIDEO, SHA)
        self.assertEqual((code, corps["etat"], corps["rejoue"]), (200, "complet", False))
        self.assertEqual(self.appels(), (1, 1))
        (statut, _), obs = self.etat()
        self.assertEqual(statut, "reported_complete")
        self.assertEqual(obs, {"youtube": ("reported_success", f"youtube-{SLOT}"),
                               "instagram": ("reported_success", f"instagram-{SLOT}")})
        code, corps = w.traiter(SLOT, VIDEO, SHA)
        self.assertEqual((code, corps["rejoue"], corps["youtube"]["remote_id"]), (200, True, f"youtube-{SLOT}"))
        self.assertEqual(self.appels(), (1, 1), "le rejeu ne doit appeler aucune plateforme")

    def test_meme_creneau_autre_video_refuse(self):
        w = self.worker()
        w.traiter(SLOT, VIDEO, SHA)
        autre = b"autre video"
        self.assertEqual(w.traiter(SLOT, autre, hashlib.sha256(autre).hexdigest())[0], 409)
        self.assertEqual(self.appels(), (1, 1))

    def test_matin_et_soir_independants(self):
        w = self.worker()
        self.assertEqual(w.traiter("2026-11-07:matin", VIDEO, SHA)[0], 200)
        self.assertEqual(w.traiter("2026-11-07:soir", VIDEO, SHA)[0], 200)
        self.assertEqual(self.appels(), (2, 2))


class ReponsesAmbigues(Base):
    def test_youtube_succes_instagram_timeout(self):
        """Cas demandé : YouTube publié, Instagram sans réponse -> bloqué, aucun réessai, jamais « complet »."""
        w = self.worker(ig="timeout")
        code, corps = w.traiter(SLOT, VIDEO, SHA)
        self.assertEqual((code, corps["etat"]), (502, "reconciliation_requise"))
        self.assertEqual((corps["youtube"]["success"], corps["youtube"]["remote_id"]), (True, f"youtube-{SLOT}"))
        self.assertEqual((corps["instagram"]["success"], corps["instagram"]["remote_id"]), (False, None))
        (statut, _), obs = self.etat()
        self.assertEqual(statut, "needs_reconciliation")
        self.assertEqual(obs["youtube"][0], "reported_success")
        self.assertEqual(obs["instagram"], ("needs_reconciliation", None))
        for _ in range(3):
            self.assertEqual(w.traiter(SLOT, VIDEO, SHA)[0], 409)
        self.assertEqual(self.appels(), (1, 1), "aucune nouvelle publication après un envoi incertain")
        with self.assertRaises(sqlite3.DatabaseError):      # le schéma interdit aussi de le déclarer complet
            ouvrir(self.db).execute("UPDATE video_slot_reservations SET status='reported_complete', revision=revision+1")

    def test_youtube_timeout_instagram_jamais_appele(self):
        w = self.worker(yt="timeout")
        self.assertEqual(w.traiter(SLOT, VIDEO, SHA)[0], 502)
        self.assertEqual(self.appels(), (1, 0))
        self.assertNotIn("instagram", self.etat()[1])
        self.assertEqual(w.traiter(SLOT, VIDEO, SHA)[0], 409)
        self.assertEqual(self.appels(), (1, 0))

    def test_echec_declare_n_est_pas_une_preuve_d_absence(self):
        w = self.worker(yt="echec")
        self.assertEqual(w.traiter(SLOT, VIDEO, SHA)[0], 502)
        self.assertEqual(self.etat()[0][0], "needs_reconciliation")
        self.assertEqual(w.traiter(SLOT, VIDEO, SHA)[0], 409)
        self.assertEqual(self.appels(), (1, 0))

    def test_succes_sans_identifiant_distant_n_est_pas_un_succes(self):
        w = self.worker(yt="succes_sans_id")
        code, corps = w.traiter(SLOT, VIDEO, SHA)
        self.assertEqual((code, corps["youtube"]["success"]), (502, False))
        self.assertEqual(self.etat()[1]["youtube"], ("needs_reconciliation", None))

    def test_0001_ne_permet_pas_de_reconcilier_par_reecriture(self):
        """Limite : sortir de needs_reconciliation exige une extension (0002, preuves ajoutées en lecture seule)."""
        self.worker(ig="timeout").traiter(SLOT, VIDEO, SHA)
        c = ouvrir(self.db)
        with self.assertRaisesRegex(sqlite3.DatabaseError, "terminal observation immutable"):
            c.execute("UPDATE video_platform_results SET status='reported_success', remote_id='ig1', expected_revision=?, "
                      "updated_at='t' WHERE platform='instagram'", (self.etat()[0][1],))
        with self.assertRaises(sqlite3.DatabaseError):
            c.execute("UPDATE video_slot_reservations SET status='upload_started', revision=revision+1")


class ReprisesApresCrash(Base):
    def test_crash_entre_reservation_et_prise_se_rejoue_sans_risque(self):
        c = ouvrir(self.db)
        c.execute("INSERT INTO video_slot_reservations(slot_key,mp4_sha256,status,created_at,updated_at) "
                  "VALUES (?,?,'reserved','t','t')", (SLOT, SHA))
        c.close()
        self.assertEqual(self.worker().traiter(SLOT, VIDEO, SHA)[0], 200)   # aucune plateforme n'avait été appelée
        self.assertEqual(self.appels(), (1, 1))

    def test_crash_pendant_l_appel_youtube(self):
        w = self.worker(yt="crash_avant")
        with self.assertRaises(Crash):
            w.traiter(SLOT, VIDEO, SHA)
        self.assertEqual(self.etat()[0][0], "upload_started")
        w2 = self.worker()
        self.assertEqual(w2.traiter(SLOT, VIDEO, SHA)[0], 409)
        self.assertEqual(self.appels(), (0, 0))
        self.assertEqual(w2.balayer(APRES), [(SLOT, "needs_reconciliation")])
        self.assertEqual(w2.traiter(SLOT, VIDEO, SHA)[0], 409)
        self.assertEqual(self.appels(), (0, 0))

    def test_crash_apres_publication_youtube_avant_enregistrement(self):
        """Pire cas : la plateforme a publié, la base l'ignore. Aucun réessai, blocage en réconciliation."""
        w = self.worker(yt="crash_apres_publication")
        with self.assertRaises(Crash):
            w.traiter(SLOT, VIDEO, SHA)
        self.assertEqual(self.yt.publies, [SLOT])
        self.assertEqual(self.etat()[1]["youtube"], ("upload_started", None))
        yt0 = self.yt                       # client ayant réellement publié ; w2 reçoit de NOUVEAUX doubles
        w2 = self.worker()
        w2.traiter(SLOT, VIDEO, SHA)
        w2.balayer(APRES)
        w2.traiter(SLOT, VIDEO, SHA)
        self.assertEqual(self.appels(), (0, 0))
        self.assertEqual(self.etat()[0][0], "needs_reconciliation")
        self.assertEqual((yt0.appels, yt0.publies), (1, [SLOT]), "une seule publication YouTube au total")

    def test_crash_apres_les_deux_succes_enregistres_le_balayage_complete(self):
        """Les deux plateformes sont enregistrées en succès, le Worker meurt avant d'écrire « complet »."""
        def mourir():
            raise Crash()
        w = self.worker()
        w.avant_completion = mourir
        with self.assertRaises(Crash):
            w.traiter(SLOT, VIDEO, SHA)
        (statut, _), obs = self.etat()
        self.assertEqual((statut, obs["youtube"][0], obs["instagram"][0]),
                         ("upload_started", "reported_success", "reported_success"))
        w.avant_completion = None
        self.assertEqual(w.traiter(SLOT, VIDEO, SHA)[0], 409)
        self.assertEqual(w.balayer(APRES), [(SLOT, "reported_complete")])
        self.assertEqual(w.traiter(SLOT, VIDEO, SHA)[0], 200)
        self.assertEqual(self.appels(), (1, 1))

    def test_balayage_concurrent_le_succes_non_enregistre_est_renvoye_au_client(self):
        """Si le balayage passe pendant un envoi lent, le succès distant n'est pas enregistré : il doit au moins être
        renvoyé (id distant) pour la réconciliation manuelle."""
        w = self.worker(ig="succes")
        self.yt.avant_retour = lambda: w.balayer("9999-01-01T00:00:00Z")
        code, corps = w.traiter(SLOT, VIDEO, SHA)
        self.assertEqual(code, 502)
        self.assertEqual((corps["youtube"]["success"], corps["youtube"]["enregistre"]), (True, False))
        self.assertEqual(corps["youtube"]["remote_id"], f"youtube-{SLOT}")
        self.assertEqual(self.appels(), (1, 0))
        self.assertEqual(self.etat()[0][0], "needs_reconciliation")


class Concurrence(Base):
    def lancer(self, w_args, n=20):
        sorties, barriere, verrou = [], threading.Barrier(n), threading.Lock()

        def tache():
            w = Worker(self.db, self.yt, self.ig)
            barriere.wait()
            r = w.traiter(SLOT, VIDEO, SHA)
            with verrou:
                sorties.append(r)

        fils = [threading.Thread(target=tache) for _ in range(n)]
        [f.start() for f in fils]
        [f.join() for f in fils]
        return sorties

    def test_vingt_appels_simultanes_une_seule_publication(self):
        self.worker(delai=0.05)
        sorties = self.lancer(None)
        self.assertEqual(len(sorties), 20)
        gagnants = [s for s in sorties if s[0] == 200 and not s[1]["rejoue"]]
        self.assertEqual(len(gagnants), 1)
        for code, corps in sorties:
            self.assertTrue(code == 409 or (code == 200 and corps["rejoue"]) or (code, corps) == gagnants[0])
        self.assertEqual(self.appels(), (1, 1), "exactement une publication par plateforme")
        self.assertEqual(self.yt.publies, [SLOT])
        self.assertEqual(self.etat()[0][0], "reported_complete")

    def test_vingt_appels_simultanes_youtube_succes_instagram_timeout(self):
        self.worker(ig="timeout", delai=0.05)
        sorties = self.lancer(None)
        codes = sorted(c for c, _ in sorties)
        self.assertEqual(codes, [409] * 19 + [502])
        self.assertEqual(self.appels(), (1, 1))
        (statut, _), obs = self.etat()
        self.assertEqual((statut, obs["youtube"][0], obs["instagram"][0]),
                         ("needs_reconciliation", "reported_success", "needs_reconciliation"))


if __name__ == "__main__":
    unittest.main()
