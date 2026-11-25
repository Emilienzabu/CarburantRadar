-- CANDIDAT, NON APPLIQUÉ. À relire et appliquer uniquement par le propriétaire Cloudflare, après 0001 et après sauvegarde.
-- Extension ADDITIVE de 0001 : aucune table ni aucun trigger de 0001 n'est modifié ou remplacé (testé sous SQLite par
-- video/tests/test_ledger_0002.py et workers/video-automation/test ; PAS exécuté sur D1 : à essayer sur une base D1 de test).
--
-- Pourquoi : dans 0001 « needs_reconciliation » est sans issue (observations terminales immuables, réservation figée). Sortir d'un
-- créneau incertain exige donc des PREUVES AJOUTÉES (jamais de réécriture) puis une décision de clôture ajoutée, elle aussi.
-- Rien ici ne relance une publication : un créneau clos reste clos (« closed_nothing_published » ne rouvre rien).
--
--   video_attempt_refs             traces écrites par le Worker pendant la tentative (identifiant de conteneur Instagram,
--                                  classe d'échec) : aide à la vérification, ne prouve rien à elle seule.
--   video_reconciliation_evidence  une preuve par créneau et plateforme : « published » (identifiant distant) ou « absent ».
--   video_slot_resolutions         décision de clôture d'un créneau en needs_reconciliation, acceptée seulement si les preuves la justifient.

CREATE TABLE video_attempt_refs (
  slot_key    TEXT NOT NULL,
  platform    TEXT NOT NULL CHECK (platform IN ('youtube','instagram')),
  ref_kind    TEXT NOT NULL CHECK (ref_kind IN ('instagram_container','failure_class','failure_stage','http_status')),
  ref_value   TEXT NOT NULL CHECK (length(ref_value) BETWEEN 1 AND 200),
  recorded_at TEXT NOT NULL,
  PRIMARY KEY (slot_key, platform, ref_kind),
  CHECK (ref_kind != 'failure_class' OR ref_value IN ('definitive_pre_publish','uncertain'))
);

CREATE TRIGGER video_attempt_refs_insert_guard
BEFORE INSERT ON video_attempt_refs
BEGIN
  SELECT RAISE(ABORT, 'observation required for this platform')
   WHERE NOT EXISTS (SELECT 1 FROM video_platform_results WHERE slot_key = NEW.slot_key AND platform = NEW.platform);
END;
CREATE TRIGGER video_attempt_refs_no_update BEFORE UPDATE ON video_attempt_refs BEGIN SELECT RAISE(ABORT, 'refs are append-only'); END;
CREATE TRIGGER video_attempt_refs_no_delete BEFORE DELETE ON video_attempt_refs BEGIN SELECT RAISE(ABORT, 'refs are append-only'); END;

CREATE TABLE video_reconciliation_evidence (
  slot_key    TEXT NOT NULL,
  platform    TEXT NOT NULL CHECK (platform IN ('youtube','instagram')),
  mp4_sha256  TEXT NOT NULL CHECK (length(mp4_sha256) = 64),
  outcome     TEXT NOT NULL CHECK (outcome IN ('published','absent')),
  remote_id   TEXT,
  proof_kind  TEXT NOT NULL CHECK (proof_kind IN ('remote_lookup','owner_manual_check','worker_pre_publish')),
  note        TEXT CHECK (note IS NULL OR length(note) <= 500),
  recorded_at TEXT NOT NULL,
  PRIMARY KEY (slot_key, platform),
  CHECK ((outcome = 'published' AND remote_id IS NOT NULL AND length(remote_id) > 0) OR (outcome = 'absent' AND remote_id IS NULL))
);

-- Une preuve ne s'ajoute que sur un créneau bloqué (même empreinte), jamais pour une plateforme déjà confirmée, et la preuve
-- « worker_pre_publish » n'est acceptée que si le Worker a lui-même noté un échec AVANT tout envoi à la plateforme.
CREATE TRIGGER video_evidence_insert_guard
BEFORE INSERT ON video_reconciliation_evidence
BEGIN
  SELECT RAISE(ABORT, 'slot must await reconciliation')
   WHERE NOT EXISTS (SELECT 1 FROM video_slot_reservations
                      WHERE slot_key = NEW.slot_key AND mp4_sha256 = NEW.mp4_sha256 AND status = 'needs_reconciliation');
  SELECT RAISE(ABORT, 'platform already confirmed')
   WHERE EXISTS (SELECT 1 FROM video_platform_results
                  WHERE slot_key = NEW.slot_key AND platform = NEW.platform AND status = 'reported_success');
  SELECT RAISE(ABORT, 'worker proof needs a recorded pre-publish failure')
   WHERE NEW.proof_kind = 'worker_pre_publish'
     AND (NEW.outcome != 'absent'
          OR NOT EXISTS (SELECT 1 FROM video_attempt_refs
                          WHERE slot_key = NEW.slot_key AND platform = NEW.platform
                            AND ref_kind = 'failure_class' AND ref_value = 'definitive_pre_publish'));
END;
CREATE TRIGGER video_evidence_no_update BEFORE UPDATE ON video_reconciliation_evidence BEGIN SELECT RAISE(ABORT, 'evidence is append-only'); END;
CREATE TRIGGER video_evidence_no_delete BEFORE DELETE ON video_reconciliation_evidence BEGIN SELECT RAISE(ABORT, 'evidence is append-only'); END;

CREATE TABLE video_slot_resolutions (
  slot_key    TEXT PRIMARY KEY NOT NULL,
  mp4_sha256  TEXT NOT NULL CHECK (length(mp4_sha256) = 64),
  resolution  TEXT NOT NULL CHECK (resolution IN ('completed_by_evidence','closed_nothing_published')),
  recorded_at TEXT NOT NULL
);

-- completed_by_evidence : CHAQUE plateforme a une publication prouvée (observation reported_success OU preuve « published »).
-- closed_nothing_published : AUCUNE plateforme n'a de publication prouvée ET chaque plateforme tentée a une preuve « absent »
--                            (une plateforme jamais tentée, sans observation, n'a rien à prouver).
CREATE TRIGGER video_resolution_insert_guard
BEFORE INSERT ON video_slot_resolutions
BEGIN
  SELECT RAISE(ABORT, 'slot must await reconciliation')
   WHERE NOT EXISTS (SELECT 1 FROM video_slot_reservations
                      WHERE slot_key = NEW.slot_key AND mp4_sha256 = NEW.mp4_sha256 AND status = 'needs_reconciliation');
  SELECT RAISE(ABORT, 'completion needs proof of publication on both platforms')
   WHERE NEW.resolution = 'completed_by_evidence'
     AND (SELECT COUNT(*) FROM (SELECT 'youtube' AS p UNION ALL SELECT 'instagram') AS pf
           WHERE EXISTS (SELECT 1 FROM video_platform_results r WHERE r.slot_key = NEW.slot_key AND r.platform = pf.p
                          AND r.status = 'reported_success' AND r.remote_id IS NOT NULL)
              OR EXISTS (SELECT 1 FROM video_reconciliation_evidence e WHERE e.slot_key = NEW.slot_key AND e.platform = pf.p
                          AND e.outcome = 'published')) != 2;
  SELECT RAISE(ABORT, 'closing needs proof of absence on every attempted platform and no publication')
   WHERE NEW.resolution = 'closed_nothing_published'
     AND (SELECT COUNT(*) FROM (SELECT 'youtube' AS p UNION ALL SELECT 'instagram') AS pf
           WHERE NOT EXISTS (SELECT 1 FROM video_platform_results r WHERE r.slot_key = NEW.slot_key AND r.platform = pf.p
                              AND r.status = 'reported_success')
             AND NOT EXISTS (SELECT 1 FROM video_reconciliation_evidence e WHERE e.slot_key = NEW.slot_key AND e.platform = pf.p
                              AND e.outcome = 'published')
             AND (NOT EXISTS (SELECT 1 FROM video_platform_results r WHERE r.slot_key = NEW.slot_key AND r.platform = pf.p)
                  OR EXISTS (SELECT 1 FROM video_reconciliation_evidence e WHERE e.slot_key = NEW.slot_key AND e.platform = pf.p
                              AND e.outcome = 'absent'))) != 2;
END;
CREATE TRIGGER video_resolution_no_update BEFORE UPDATE ON video_slot_resolutions BEGIN SELECT RAISE(ABORT, 'resolutions are append-only'); END;
CREATE TRIGGER video_resolution_no_delete BEFORE DELETE ON video_slot_resolutions BEGIN SELECT RAISE(ABORT, 'resolutions are append-only'); END;
