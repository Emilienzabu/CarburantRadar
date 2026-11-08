"""Modèle de RÉFÉRENCE (Python, tests uniquement) du protocole proposé pour le Worker `video-automation`.

Ce n'est PAS le Worker : le code réel (JavaScript) n'a pas pu être lu. Ce modèle fixe l'ORDRE des opérations et les
réponses attendues, exécutés contre le schéma candidat réel `video/ledger/0001_video_ledger.sql` (SQLite, pas D1).
Rien ici n'appelle YouTube, Instagram, Cloudflare ou le réseau : les plateformes sont des doubles de test.

Règles du protocole (voir aussi la section « Protocole » de video/ledger/README.md) :
  1. valider slot_id + sha256 AVANT tout accès base ; recalculer le SHA-256 des octets reçus (ne pas croire le client) ;
  2. réserver (INSERT ... ON CONFLICT DO NOTHING), puis PRENDRE le créneau (un seul gagnant) AVANT tout appel de plateforme ;
  3. une ligne d'observation par plateforme (clé primaire = prise unique) AVANT l'appel, résultat enregistré APRÈS ;
  4. tout ce qui n'est pas un succès prouvé (id distant non vide) -> needs_reconciliation ; on n'appelle pas la plateforme suivante ;
  5. jamais de réessai ni de réouverture automatiques ; un créneau terminé se rejoue en lecture seule (200, aucun appel).
"""
import datetime as dt
import hashlib
import re
import sqlite3
import threading
import time
from pathlib import Path

SQL = (Path(__file__).resolve().parents[1] / "ledger" / "0001_video_ledger.sql").read_text(encoding="utf-8")
SLOT_RE = re.compile(r"\d{4}-\d{2}-\d{2}:(matin|soir)")
SHA_RE = re.compile(r"[0-9a-f]{64}")
PLATEFORMES = ("youtube", "instagram")


class Timeout(Exception):
    """Délai dépassé côté Worker : l'issue chez la plateforme est INCONNUE."""


class Crash(BaseException):
    """Mort du processus (isolat arrêté, coupure) : rien après ce point ne s'exécute."""


def slot_valide(slot):
    if not isinstance(slot, str) or not SLOT_RE.fullmatch(slot):
        return False
    try:
        dt.date.fromisoformat(slot[:10])
    except ValueError:
        return False
    return True


def ouvrir(chemin):
    c = sqlite3.connect(chemin, timeout=30, isolation_level=None)
    c.execute("PRAGMA busy_timeout=30000")
    return c


def initialiser(chemin):
    c = ouvrir(chemin)
    c.executescript(SQL)
    c.close()


class FauxClient:
    """Double d'une API de plateforme. scenario : succes | timeout | echec | succes_sans_id | crash_avant | crash_apres_publication."""

    def __init__(self, nom, scenario="succes", delai=0.0, avant_retour=None):
        self.nom, self.scenario, self.delai, self.avant_retour = nom, scenario, delai, avant_retour
        self.appels, self.publies = 0, []
        self._verrou = threading.Lock()

    def publier(self, slot, sha, video):
        with self._verrou:
            self.appels += 1
        if self.delai:
            time.sleep(self.delai)
        s = self.scenario
        if s == "crash_avant":
            raise Crash()
        if s == "timeout":
            raise Timeout()
        if s == "echec":
            return {"ok": False, "erreur": "quota"}
        if s == "succes_sans_id":
            return {"ok": True}
        with self._verrou:
            self.publies.append(slot)          # la plateforme a RÉELLEMENT publié
        if s == "crash_apres_publication":
            raise Crash()                      # publié, mais le Worker meurt avant d'enregistrer
        if self.avant_retour:
            self.avant_retour()
        return {"ok": True, "remote_id": f"{self.nom}-{slot}"}


class Worker:
    def __init__(self, chemin, youtube, instagram, horloge=lambda: "2026-11-07T06:40:00Z", avant_completion=None):
        self.chemin, self.clients, self.horloge = chemin, {"youtube": youtube, "instagram": instagram}, horloge
        self.avant_completion = avant_completion   # point d'injection de crash (tests)

    # -- point d'entrée : (code HTTP, corps JSON) -------------------------------------------------------------------
    def traiter(self, slot_id, video, sha256):
        if not slot_valide(slot_id):
            return 400, {"erreur": "slot_id_invalide"}
        if not isinstance(sha256, str) or not SHA_RE.fullmatch(sha256):
            return 400, {"erreur": "sha256_invalide"}
        if hashlib.sha256(video).hexdigest() != sha256:
            return 400, {"erreur": "sha256_different_du_contenu"}
        c = ouvrir(self.chemin)
        try:
            return self._traiter(c, slot_id, sha256, video)
        finally:
            c.close()

    def _traiter(self, c, slot, sha, video):
        t = self.horloge()
        c.execute("INSERT INTO video_slot_reservations(slot_key,mp4_sha256,status,created_at,updated_at) "
                  "VALUES (?,?,'reserved',?,?) ON CONFLICT(slot_key) DO NOTHING", (slot, sha, t, t))
        statut, sha_bd, rev = c.execute("SELECT status, mp4_sha256, revision FROM video_slot_reservations "
                                        "WHERE slot_key=?", (slot,)).fetchone()
        if sha_bd != sha:
            return 409, {"erreur": "creneau_deja_utilise_par_une_autre_video", "slot_id": slot}
        if statut == "reported_complete":
            return 200, self._corps(c, slot, sha, "complet", rejoue=True)
        if statut == "needs_reconciliation":
            return 409, {"erreur": "reconciliation_requise", "slot_id": slot}
        if statut == "upload_started":
            return 409, {"erreur": "creneau_en_cours", "slot_id": slot}
        if c.execute("UPDATE video_slot_reservations SET status='upload_started', revision=revision+1, updated_at=? "
                     "WHERE slot_key=? AND mp4_sha256=? AND status='reserved' AND revision=?",
                     (t, slot, sha, rev)).rowcount != 1:
            return 409, {"erreur": "creneau_en_cours", "slot_id": slot}

        resultats, tout_ok = {}, True
        for nom in PLATEFORMES:
            c.execute("INSERT INTO video_platform_results(slot_key,platform,mp4_sha256,status,updated_at) "
                      "VALUES (?,?,?,'upload_started',?)", (slot, nom, sha, t))
            try:
                reponse = self.clients[nom].publier(slot, sha, video)
            except Timeout:
                reponse = None
            ok = (isinstance(reponse, dict) and reponse.get("ok") is True
                  and isinstance(reponse.get("remote_id"), str) and bool(reponse["remote_id"].strip()))
            remote = reponse["remote_id"] if ok else None
            enregistre = True
            try:
                c.execute("UPDATE video_platform_results SET status=?, remote_id=?, expected_revision=?, updated_at=? "
                          "WHERE slot_key=? AND platform=?",
                          ("reported_success" if ok else "needs_reconciliation", remote, self._rev(c, slot), t, slot, nom))
            except sqlite3.DatabaseError:
                enregistre = False             # ex. balayage concurrent : le succès éventuel n'est pas enregistré
            resultats[nom] = {"success": ok, "remote_id": remote, "enregistre": enregistre}
            if not (ok and enregistre):
                tout_ok = False
                break                          # on n'appelle JAMAIS la plateforme suivante après un doute
        if tout_ok:
            if self.avant_completion:
                self.avant_completion()
            if c.execute("UPDATE video_slot_reservations SET status='reported_complete', revision=revision+1, updated_at=? "
                         "WHERE slot_key=? AND status='upload_started' AND revision=?",
                         (t, slot, self._rev(c, slot))).rowcount == 1:
                return 200, self._corps(c, slot, sha, "complet", rejoue=False)
        c.execute("UPDATE video_slot_reservations SET status='needs_reconciliation', revision=revision+1, updated_at=? "
                  "WHERE slot_key=? AND status='upload_started' AND revision=?", (t, slot, self._rev(c, slot)))
        corps = {"slot_id": slot, "sha256": sha, "etat": "reconciliation_requise", "rejoue": False}
        for nom in PLATEFORMES:
            corps[nom] = resultats.get(nom, {"success": False, "remote_id": None, "enregistre": False, "tentee": False})
        return 502, corps

    @staticmethod
    def _rev(c, slot):
        return c.execute("SELECT revision FROM video_slot_reservations WHERE slot_key=?", (slot,)).fetchone()[0]

    def _corps(self, c, slot, sha, etat, rejoue):
        corps = {"slot_id": slot, "sha256": sha, "etat": etat, "rejoue": rejoue}
        for nom, st, rid in c.execute("SELECT platform,status,remote_id FROM video_platform_results WHERE slot_key=?", (slot,)):
            corps[nom] = {"success": st == "reported_success", "remote_id": rid, "enregistre": True}
        return corps

    # -- reprise après crash : ne publie jamais, ne rouvre jamais --------------------------------------------------
    def balayer(self, avant):
        """Créneaux « upload_started » plus vieux que `avant` : complétés si les DEUX succès sont enregistrés, sinon
        bloqués en needs_reconciliation. Renvoie [(slot, nouvel_etat)]."""
        c, t, sortie = ouvrir(self.chemin), self.horloge(), []
        try:
            for slot, sha in c.execute("SELECT slot_key, mp4_sha256 FROM video_slot_reservations "
                                       "WHERE status='upload_started' AND updated_at < ?", (avant,)).fetchall():
                n_ok = c.execute("SELECT COUNT(*) FROM video_platform_results WHERE slot_key=? AND status='reported_success' "
                                 "AND remote_id IS NOT NULL", (slot,)).fetchone()[0]
                if n_ok == 2:
                    cible = "reported_complete"
                else:
                    cible = "needs_reconciliation"
                    for (nom,) in c.execute("SELECT platform FROM video_platform_results WHERE slot_key=? "
                                            "AND status='upload_started'", (slot,)).fetchall():
                        c.execute("UPDATE video_platform_results SET status='needs_reconciliation', expected_revision=?, "
                                  "updated_at=? WHERE slot_key=? AND platform=? AND status='upload_started'",
                                  (self._rev(c, slot), t, slot, nom))
                if c.execute("UPDATE video_slot_reservations SET status=?, revision=revision+1, updated_at=? "
                             "WHERE slot_key=? AND status='upload_started' AND revision=?",
                             (cible, t, slot, self._rev(c, slot))).rowcount == 1:
                    sortie.append((slot, cible))
            return sortie
        finally:
            c.close()
