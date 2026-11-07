"""Tests du schéma candidat video/ledger/0001_video_ledger.sql sous SQLite (aucune base distante, rien d'appliqué).

SQLite n'est pas D1 : ces tests prouvent la logique du schéma, pas son comportement sur Cloudflare.
"""
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path

SQL = (Path(__file__).resolve().parents[1] / "ledger" / "0001_video_ledger.sql").read_text(encoding="utf-8")
SLOT, SHA = "2026-11-07:matin", "a" * 64
T = "2026-11-07T06:40:00Z"


def base(chemin=":memory:"):
    c = sqlite3.connect(chemin, timeout=10, isolation_level=None)
    c.executescript(SQL)
    return c


def reserver(c, slot=SLOT, sha=SHA):
    return c.execute("INSERT INTO video_slot_reservations(slot_key,mp4_sha256,status,created_at,updated_at) "
                     "VALUES (?,?,'reserved',?,?) ON CONFLICT(slot_key) DO NOTHING", (slot, sha, T, T)).rowcount


def prendre(c, slot=SLOT, sha=SHA, rev=0):
    return c.execute("UPDATE video_slot_reservations SET status='upload_started', revision=revision+1, updated_at=? "
                     "WHERE slot_key=? AND mp4_sha256=? AND status='reserved' AND revision=?", (T, slot, sha, rev)).rowcount


def init_plateformes(c, slot=SLOT, sha=SHA):
    for p in ("youtube", "instagram"):
        c.execute("INSERT INTO video_platform_results(slot_key,platform,mp4_sha256,status,updated_at) "
                  "VALUES (?,?,?,'upload_started',?)", (slot, p, sha, T))


def revision(c, slot=SLOT):
    return c.execute("SELECT revision FROM video_slot_reservations WHERE slot_key=?", (slot,)).fetchone()[0]


def reussite(c, plateforme, remote_id, slot=SLOT, rev=None):
    rev = revision(c, slot) if rev is None else rev
    return c.execute("UPDATE video_platform_results SET status='reported_success', remote_id=?, expected_revision=?, "
                     "updated_at=? WHERE slot_key=? AND platform=?", (remote_id, rev, T, slot, plateforme)).rowcount


def terminer(c, slot=SLOT):
    return c.execute("UPDATE video_slot_reservations SET status='reported_complete', revision=revision+1, updated_at=? "
                     "WHERE slot_key=? AND status='upload_started' AND revision=?", (T, slot, revision(c, slot))).rowcount


class Reservation(unittest.TestCase):
    def test_un_creneau_une_reservation(self):
        c = base()
        self.assertEqual(reserver(c), 1)
        self.assertEqual(reserver(c), 0, "la deuxième réservation du même créneau ne doit rien créer")
        self.assertEqual(reserver(c, sha="b" * 64), 0, "même créneau, autre vidéo : toujours refusé")
        self.assertEqual(c.execute("SELECT mp4_sha256 FROM video_slot_reservations").fetchone()[0], SHA)

    def test_matin_et_soir_sont_deux_creneaux(self):
        c = base()
        self.assertEqual(reserver(c, "2026-11-07:matin"), 1)
        self.assertEqual(reserver(c, "2026-11-07:soir", "c" * 64), 1)

    def test_cles_et_empreintes_invalides_refusees(self):
        c = base()
        for slot, sha in [("n-importe-quoi", SHA), ("2026-11-07:midi", SHA), (SLOT, "a" * 63), (SLOT, "G" * 64), (SLOT, "A" * 64)]:
            with self.subTest(slot=slot, sha=sha[:6]):
                with self.assertRaises(sqlite3.IntegrityError):
                    reserver(c, slot, sha)

    def test_prise_du_creneau_une_seule_fois(self):
        c = base()
        reserver(c)
        self.assertEqual(prendre(c), 1)
        self.assertEqual(prendre(c), 0, "le créneau déjà pris ne peut pas l'être une seconde fois")
        self.assertEqual(prendre(c, rev=1), 0, "même avec la nouvelle révision, l'état n'est plus « reserved »")

    def test_prise_avec_mauvaise_empreinte_ou_revision(self):
        c = base()
        reserver(c)
        self.assertEqual(prendre(c, sha="b" * 64), 0)
        self.assertEqual(prendre(c, rev=5), 0)
        self.assertEqual(prendre(c), 1)


class Concurrence(unittest.TestCase):
    def test_vingt_workflows_simultanes_un_seul_gagne(self):
        with tempfile.TemporaryDirectory() as t:
            chemin = str(Path(t) / "d1.sqlite")
            base(chemin).close()
            gagnants, barriere = [], threading.Barrier(20)

            def worker(i):
                c = sqlite3.connect(chemin, timeout=30, isolation_level=None)
                barriere.wait()
                reserver(c)
                gagnants.append(prendre(c))
                c.close()

            fils = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
            [f.start() for f in fils]
            [f.join() for f in fils]
            self.assertEqual(sum(gagnants), 1, f"exactement une prise attendue, obtenu {sum(gagnants)}")
            c = sqlite3.connect(chemin)
            self.assertEqual(c.execute("SELECT COUNT(*) FROM video_slot_reservations").fetchone()[0], 1)
            self.assertEqual(c.execute("SELECT status FROM video_slot_reservations").fetchone()[0], "upload_started")


class Plateformes(unittest.TestCase):
    def pret(self):
        c = base()
        reserver(c)
        prendre(c)
        init_plateformes(c)
        return c

    def test_observation_sans_reservation_active_refusee(self):
        c = base()
        reserver(c)   # encore « reserved » : pas de prise
        with self.assertRaisesRegex(sqlite3.DatabaseError, "active matching parent required"):
            init_plateformes(c)

    def test_observation_avec_autre_empreinte_refusee(self):
        c = base()
        reserver(c)
        prendre(c)
        with self.assertRaisesRegex(sqlite3.DatabaseError, "active matching parent required"):
            init_plateformes(c, sha="b" * 64)

    def test_observation_terminale_fabriquee_refusee(self):
        c = base()
        reserver(c)
        prendre(c)
        with self.assertRaisesRegex(sqlite3.DatabaseError, "only pending"):
            c.execute("INSERT INTO video_platform_results VALUES (?,?,?,?,?,?,?)",
                      (SLOT, "youtube", SHA, "reported_success", "abc", 1, T))

    def test_succes_sans_identifiant_distant_refuse(self):
        c = self.pret()
        with self.assertRaises(sqlite3.IntegrityError):
            c.execute("UPDATE video_platform_results SET status='reported_success', remote_id=NULL, expected_revision=?, "
                      "updated_at=? WHERE platform='youtube'", (revision(c), T))

    def test_revision_obligatoire_et_non_perimee(self):
        c = self.pret()
        with self.assertRaisesRegex(sqlite3.DatabaseError, "expected revision required"):
            c.execute("UPDATE video_platform_results SET status='reported_success', remote_id='y1', updated_at=? "
                      "WHERE platform='youtube'", (T,))
        with self.assertRaisesRegex(sqlite3.DatabaseError, "stale or missing parent reservation"):
            reussite(c, "youtube", "y1", rev=revision(c) + 7)
        self.assertEqual(reussite(c, "youtube", "y1"), 1)

    def test_etat_final_immuable_et_pas_de_suppression(self):
        c = self.pret()
        reussite(c, "youtube", "y1")
        with self.assertRaisesRegex(sqlite3.DatabaseError, "terminal observation immutable"):
            c.execute("UPDATE video_platform_results SET status='needs_reconciliation', remote_id=NULL, "
                      "expected_revision=?, updated_at=? WHERE platform='youtube'", (revision(c), T))
        with self.assertRaisesRegex(sqlite3.DatabaseError, "observation deletion forbidden"):
            c.execute("DELETE FROM video_platform_results WHERE platform='youtube'")

    def test_identite_d_observation_immuable(self):
        c = self.pret()
        with self.assertRaisesRegex(sqlite3.DatabaseError, "observation identity immutable"):
            c.execute("UPDATE video_platform_results SET mp4_sha256=? WHERE platform='youtube'", ("b" * 64,))


class Completion(unittest.TestCase):
    def pret(self):
        c = base()
        reserver(c)
        prendre(c)
        init_plateformes(c)
        return c

    def test_succes_partiel_ne_peut_pas_etre_declare_complet(self):
        c = self.pret()
        reussite(c, "youtube", "y1")
        with self.assertRaisesRegex(sqlite3.DatabaseError, "completion requires both platform observations"):
            terminer(c)
        self.assertEqual(c.execute("SELECT status FROM video_slot_reservations").fetchone()[0], "upload_started")

    def test_complet_avec_les_deux_plateformes(self):
        c = self.pret()
        reussite(c, "youtube", "y1")
        reussite(c, "instagram", "i1")
        self.assertEqual(terminer(c), 1)
        self.assertEqual(c.execute("SELECT status, revision FROM video_slot_reservations").fetchone(), ("reported_complete", 4))
        self.assertEqual(prendre(c, rev=4), 0, "un créneau terminé ne se reprend jamais")

    def test_issue_incertaine_bloque_tout_reessai(self):
        c = self.pret()
        self.assertEqual(c.execute("UPDATE video_slot_reservations SET status='needs_reconciliation', revision=revision+1, "
                                   "updated_at=? WHERE status='upload_started' AND revision=?", (T, revision(c))).rowcount, 1)
        self.assertEqual(prendre(c, rev=revision(c)), 0)
        for destination in ("reserved", "upload_started", "reported_complete"):
            with self.subTest(destination=destination), self.assertRaises(sqlite3.DatabaseError):
                c.execute("UPDATE video_slot_reservations SET status=?, revision=revision+1 WHERE slot_key=?", (destination, SLOT))

    def test_pas_de_retour_en_arriere_ni_suppression(self):
        c = self.pret()
        with self.assertRaisesRegex(sqlite3.DatabaseError, "invalid reservation transition"):
            c.execute("UPDATE video_slot_reservations SET status='reserved', revision=revision+1 WHERE slot_key=?", (SLOT,))
        with self.assertRaisesRegex(sqlite3.DatabaseError, "reservation deletion forbidden"):
            c.execute("DELETE FROM video_slot_reservations")
        with self.assertRaisesRegex(sqlite3.DatabaseError, "reservation revision must increase exactly once"):
            c.execute("UPDATE video_slot_reservations SET status='needs_reconciliation' WHERE slot_key=?", (SLOT,))
        with self.assertRaisesRegex(sqlite3.DatabaseError, "reservation identity immutable"):
            c.execute("UPDATE video_slot_reservations SET mp4_sha256=?, revision=revision+1 WHERE slot_key=?", ("b" * 64, SLOT))


if __name__ == "__main__":
    unittest.main()
