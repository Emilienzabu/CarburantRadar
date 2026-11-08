"""Extension 0002 (preuves et clôture de créneaux incertains) sous SQLite, par-dessus 0001 inchangé.
Rien n'est exécuté sur D1 ; aucun réseau ; aucune publication."""
import sqlite3
import unittest
from pathlib import Path

LEDGER = Path(__file__).resolve().parents[1] / "ledger"
SQL1 = (LEDGER / "0001_video_ledger.sql").read_text(encoding="utf-8")
SQL2 = (LEDGER / "0002_video_ledger_evidence.sql").read_text(encoding="utf-8")
SLOT, SHA, T = "2026-11-07:matin", "a" * 64, "2026-11-07T06:40:00Z"


def base(avec_0002=True):
    c = sqlite3.connect(":memory:", isolation_level=None)
    c.executescript(SQL1)
    if avec_0002:
        c.executescript(SQL2)
    return c


def rev(c, slot=SLOT):
    return c.execute("SELECT revision FROM video_slot_reservations WHERE slot_key=?", (slot,)).fetchone()[0]


def bloquer(c, yt=("reported_success", "yt1"), ig=("needs_reconciliation", None), slot=SLOT, sha=SHA, ig_tentee=True):
    """Amène un créneau en needs_reconciliation par des transitions légitimes de 0001."""
    c.execute("INSERT INTO video_slot_reservations VALUES (?,?,'reserved',0,?,?)", (slot, sha, T, T))
    c.execute("UPDATE video_slot_reservations SET status='upload_started', revision=revision+1 WHERE slot_key=?", (slot,))
    for nom, (st, rid), tentee in (("youtube", yt, True), ("instagram", ig, ig_tentee)):
        if not tentee:
            continue
        c.execute("INSERT INTO video_platform_results VALUES (?,?,?,'upload_started',NULL,NULL,?)", (slot, nom, sha, T))
        c.execute("UPDATE video_platform_results SET status=?, remote_id=?, expected_revision=?, updated_at=? "
                  "WHERE slot_key=? AND platform=?", (st, rid, rev(c, slot), T, slot, nom))
    c.execute("UPDATE video_slot_reservations SET status='needs_reconciliation', revision=revision+1 WHERE slot_key=?", (slot,))


def preuve(c, plateforme, issue, remote=None, genre="owner_manual_check", sha=SHA, slot=SLOT):
    c.execute("INSERT INTO video_reconciliation_evidence VALUES (?,?,?,?,?,?,NULL,?)",
              (slot, plateforme, sha, issue, remote, genre, T))


def clore(c, resolution, sha=SHA, slot=SLOT):
    c.execute("INSERT INTO video_slot_resolutions VALUES (?,?,?,?)", (slot, sha, resolution, T))


class Refs(unittest.TestCase):
    def test_exige_une_observation_et_reste_en_ajout_seul(self):
        c = base()
        with self.assertRaisesRegex(sqlite3.DatabaseError, "observation required"):
            c.execute("INSERT INTO video_attempt_refs VALUES (?, 'instagram','instagram_container','c1',?)", (SLOT, T))
        bloquer(c)
        c.execute("INSERT INTO video_attempt_refs VALUES (?, 'instagram','instagram_container','c1',?)", (SLOT, T))
        with self.assertRaisesRegex(sqlite3.DatabaseError, "append-only"):
            c.execute("UPDATE video_attempt_refs SET ref_value='c2'")
        with self.assertRaisesRegex(sqlite3.DatabaseError, "append-only"):
            c.execute("DELETE FROM video_attempt_refs")

    def test_classe_d_echec_restreinte(self):
        c = base()
        bloquer(c)
        with self.assertRaises(sqlite3.IntegrityError):
            c.execute("INSERT INTO video_attempt_refs VALUES (?, 'instagram','failure_class','tout-va-bien',?)", (SLOT, T))


class Preuves(unittest.TestCase):
    def test_refusee_hors_creneau_bloque(self):
        c = base()
        c.execute("INSERT INTO video_slot_reservations VALUES (?,?,'reserved',0,?,?)", (SLOT, SHA, T, T))
        with self.assertRaisesRegex(sqlite3.DatabaseError, "await reconciliation"):
            preuve(c, "instagram", "absent")

    def test_refusee_si_plateforme_deja_confirmee(self):
        c = base(); bloquer(c)
        with self.assertRaisesRegex(sqlite3.DatabaseError, "already confirmed"):
            preuve(c, "youtube", "absent")

    def test_empreinte_differente_refusee(self):
        c = base(); bloquer(c)
        with self.assertRaisesRegex(sqlite3.DatabaseError, "await reconciliation"):
            preuve(c, "instagram", "absent", sha="b" * 64)

    def test_forme_de_la_preuve(self):
        c = base(); bloquer(c)
        with self.assertRaises(sqlite3.IntegrityError):
            preuve(c, "instagram", "published", remote=None)       # publiée sans identifiant
        with self.assertRaises(sqlite3.IntegrityError):
            preuve(c, "instagram", "absent", remote="ig1")         # absente avec identifiant
        preuve(c, "instagram", "published", remote="ig1")
        with self.assertRaises(sqlite3.IntegrityError):
            preuve(c, "instagram", "absent")                       # une seule preuve par plateforme
        with self.assertRaisesRegex(sqlite3.DatabaseError, "append-only"):
            c.execute("UPDATE video_reconciliation_evidence SET outcome='absent', remote_id=NULL")
        with self.assertRaisesRegex(sqlite3.DatabaseError, "append-only"):
            c.execute("DELETE FROM video_reconciliation_evidence")

    def test_preuve_du_worker_exige_une_trace_d_echec_avant_envoi(self):
        c = base(); bloquer(c)
        with self.assertRaisesRegex(sqlite3.DatabaseError, "pre-publish"):
            preuve(c, "instagram", "absent", genre="worker_pre_publish")
        c.execute("INSERT INTO video_attempt_refs VALUES (?, 'instagram','failure_class','uncertain',?)", (SLOT, T))
        with self.assertRaisesRegex(sqlite3.DatabaseError, "pre-publish"):
            preuve(c, "instagram", "absent", genre="worker_pre_publish")
        c2 = base(); bloquer(c2)
        c2.execute("INSERT INTO video_attempt_refs VALUES (?, 'instagram','failure_class','definitive_pre_publish',?)", (SLOT, T))
        preuve(c2, "instagram", "absent", genre="worker_pre_publish")
        c3 = base(); bloquer(c3)
        c3.execute("INSERT INTO video_attempt_refs VALUES (?, 'instagram','failure_class','definitive_pre_publish',?)", (SLOT, T))
        with self.assertRaisesRegex(sqlite3.DatabaseError, "pre-publish"):
            preuve(c3, "instagram", "published", remote="ig1", genre="worker_pre_publish")


class Clotures(unittest.TestCase):
    def test_completion_exige_la_preuve_des_deux_plateformes(self):
        c = base(); bloquer(c)
        with self.assertRaisesRegex(sqlite3.DatabaseError, "both platforms"):
            clore(c, "completed_by_evidence")
        preuve(c, "instagram", "absent")
        with self.assertRaisesRegex(sqlite3.DatabaseError, "both platforms"):
            clore(c, "completed_by_evidence")

    def test_completion_acceptee_avec_preuve_publiee(self):
        c = base(); bloquer(c)
        preuve(c, "instagram", "published", remote="ig1")
        clore(c, "completed_by_evidence")
        self.assertEqual(c.execute("SELECT status FROM video_slot_reservations").fetchone()[0], "needs_reconciliation",
                         "la réservation n'est pas réécrite : la décision est AJOUTÉE")

    def test_completion_acceptee_si_les_deux_succes_sont_deja_enregistres(self):
        c = base(); bloquer(c, ig=("reported_success", "ig1"))     # ex. échec d'écriture de l'état final
        clore(c, "completed_by_evidence")

    def test_cloture_sans_publication(self):
        c = base(); bloquer(c, yt=("needs_reconciliation", None), ig_tentee=False)   # YouTube incertain, Instagram jamais tenté
        with self.assertRaisesRegex(sqlite3.DatabaseError, "closing needs proof"):
            clore(c, "closed_nothing_published")
        preuve(c, "youtube", "absent")
        clore(c, "closed_nothing_published")

    def test_cloture_refusee_s_il_existe_une_publication(self):
        c = base(); bloquer(c)                                   # YouTube publié
        preuve(c, "instagram", "absent")
        with self.assertRaisesRegex(sqlite3.DatabaseError, "closing needs proof"):
            clore(c, "closed_nothing_published")
        c2 = base(); bloquer(c2, yt=("needs_reconciliation", None), ig_tentee=False)
        preuve(c2, "youtube", "published", remote="yt9")
        with self.assertRaisesRegex(sqlite3.DatabaseError, "closing needs proof"):
            clore(c2, "closed_nothing_published")

    def test_cloture_refusee_si_une_plateforme_tentee_n_a_pas_de_preuve(self):
        c = base(); bloquer(c, yt=("needs_reconciliation", None), ig=("needs_reconciliation", None))
        preuve(c, "youtube", "absent")
        with self.assertRaisesRegex(sqlite3.DatabaseError, "closing needs proof"):
            clore(c, "closed_nothing_published")
        preuve(c, "instagram", "absent")
        clore(c, "closed_nothing_published")

    def test_une_seule_decision_ajoutee_jamais_modifiee(self):
        c = base(); bloquer(c, ig=("reported_success", "ig1"))
        clore(c, "completed_by_evidence")
        with self.assertRaises(sqlite3.IntegrityError):
            clore(c, "completed_by_evidence")
        with self.assertRaisesRegex(sqlite3.DatabaseError, "append-only"):
            c.execute("UPDATE video_slot_resolutions SET resolution='closed_nothing_published'")
        with self.assertRaisesRegex(sqlite3.DatabaseError, "append-only"):
            c.execute("DELETE FROM video_slot_resolutions")

    def test_les_garde_fous_de_0001_tiennent_toujours(self):
        c = base(); bloquer(c, ig=("reported_success", "ig1"))
        clore(c, "completed_by_evidence")
        with self.assertRaises(sqlite3.DatabaseError):           # on ne rouvre pas un créneau bloqué
            c.execute("UPDATE video_slot_reservations SET status='upload_started', revision=revision+1")
        with self.assertRaises(sqlite3.DatabaseError):
            c.execute("UPDATE video_slot_reservations SET status='reserved', revision=revision+1")


class Compatibilite(unittest.TestCase):
    def test_0002_ne_modifie_aucun_objet_de_0001(self):
        seul = sqlite3.connect(":memory:"); seul.executescript(SQL1)
        avant = set(seul.execute("SELECT type,name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'").fetchall())
        c = base()
        apres = set(c.execute("SELECT type,name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'").fetchall())
        self.assertTrue(avant <= apres, "tous les objets de 0001 sont conservés à l'identique")
        self.assertTrue({n for _, n, _ in apres - avant}, "0002 n'ajoute que de nouveaux objets")


if __name__ == "__main__":
    unittest.main()
