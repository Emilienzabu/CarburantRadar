-- CANDIDAT, NON APPLIQUÉ. À relire et appliquer uniquement par le propriétaire Cloudflare, après sauvegarde.
-- Journal durable des publications vidéo (anti-doublon). Consolidation des migrations successives du paquet d'audit V100
-- (V77 à V90 : réservation, états par plateforme, révision, observations immuables) en UN schéma initial testé sous SQLite
-- (video/tests/test_ledger_sql.py). D1 est basé sur SQLite mais ces triggers n'ont PAS été exécutés sur D1 : à essayer sur
-- une base D1 de test avant toute base réelle.
--
-- Principe : un « créneau » (slot_key = AAAA-MM-JJ:matin|soir, heure de Paris) ne peut être publié qu'UNE fois.
--   reserved -> upload_started -> reported_complete        (les deux plateformes ont confirmé)
--                              -> needs_reconciliation      (issue incertaine : JAMAIS de réessai automatique)
-- « reported_* » = ce que le Worker a déclaré ; ce n'est PAS une preuve vérifiée à distance.

CREATE TABLE video_slot_reservations (
  slot_key   TEXT PRIMARY KEY NOT NULL
             CHECK (slot_key GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]:matin'
                 OR slot_key GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]:soir'),
  mp4_sha256 TEXT NOT NULL CHECK (length(mp4_sha256) = 64 AND mp4_sha256 NOT GLOB '*[^0-9a-f]*'),
  status     TEXT NOT NULL CHECK (status IN ('reserved','upload_started','needs_reconciliation','reported_complete')),
  revision   INTEGER NOT NULL DEFAULT 0 CHECK (revision >= 0),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE video_platform_results (
  slot_key          TEXT NOT NULL,
  platform          TEXT NOT NULL CHECK (platform IN ('youtube','instagram')),
  mp4_sha256        TEXT NOT NULL CHECK (length(mp4_sha256) = 64),
  status            TEXT NOT NULL CHECK (status IN ('upload_started','reported_success','needs_reconciliation')),
  remote_id         TEXT,
  expected_revision INTEGER CHECK (expected_revision >= 0),
  updated_at        TEXT NOT NULL,
  PRIMARY KEY (slot_key, platform),
  CHECK ((status = 'reported_success' AND remote_id IS NOT NULL) OR (status != 'reported_success' AND remote_id IS NULL))
);

-- Une observation ne naît qu'« en attente », rattachée à une réservation active de même empreinte.
CREATE TRIGGER video_observation_insert_guard
BEFORE INSERT ON video_platform_results
BEGIN
  SELECT RAISE(ABORT, 'only pending observations may be initialized')
   WHERE NEW.status != 'upload_started' OR NEW.remote_id IS NOT NULL OR NEW.expected_revision IS NOT NULL;
  SELECT RAISE(ABORT, 'active matching parent required')
   WHERE NOT EXISTS (SELECT 1 FROM video_slot_reservations
                      WHERE slot_key = NEW.slot_key AND mp4_sha256 = NEW.mp4_sha256 AND status = 'upload_started');
END;

-- Identité et état final d'une observation sont immuables ; rien n'est supprimé (les preuves de réconciliation restent).
CREATE TRIGGER video_observation_immutable_guard
BEFORE UPDATE ON video_platform_results
BEGIN
  SELECT RAISE(ABORT, 'observation identity immutable')
   WHERE NEW.slot_key IS NOT OLD.slot_key OR NEW.platform IS NOT OLD.platform OR NEW.mp4_sha256 IS NOT OLD.mp4_sha256;
  SELECT RAISE(ABORT, 'terminal observation immutable') WHERE OLD.status != 'upload_started';
  SELECT RAISE(ABORT, 'no mutable pending observation')
   WHERE NEW.status = 'upload_started' AND (NEW.remote_id IS NOT OLD.remote_id
      OR NEW.expected_revision IS NOT OLD.expected_revision OR NEW.updated_at IS NOT OLD.updated_at);
  SELECT RAISE(ABORT, 'terminal transition required')
   WHERE NEW.status NOT IN ('reported_success','needs_reconciliation','upload_started');
END;

CREATE TRIGGER video_observation_no_delete
BEFORE DELETE ON video_platform_results
BEGIN
  SELECT RAISE(ABORT, 'observation deletion forbidden');
END;

-- Passer une observation en état final fait avancer la révision de la réservation parente (verrou optimiste) :
-- l'appelant doit fournir la révision qu'il a lue ; une lecture périmée est refusée.
CREATE TRIGGER video_observation_revision_guard
AFTER UPDATE OF status ON video_platform_results
WHEN OLD.status = 'upload_started' AND NEW.status IN ('reported_success','needs_reconciliation')
BEGIN
  SELECT RAISE(ABORT, 'expected revision required') WHERE NEW.expected_revision IS NULL;
  UPDATE video_slot_reservations
     SET revision = revision + 1, updated_at = NEW.updated_at
   WHERE slot_key = NEW.slot_key AND mp4_sha256 = NEW.mp4_sha256
     AND status = 'upload_started' AND revision = NEW.expected_revision;
  SELECT RAISE(ABORT, 'stale or missing parent reservation') WHERE changes() != 1;
END;

-- Réservation : identité immuable, pas de suppression, révision +1 exactement, transitions autorisées uniquement,
-- et « reported_complete » seulement si les DEUX plateformes ont une observation reported_success avec identifiant distant.
CREATE TRIGGER video_reservation_no_delete
BEFORE DELETE ON video_slot_reservations
BEGIN
  SELECT RAISE(ABORT, 'reservation deletion forbidden');
END;

CREATE TRIGGER video_reservation_update_guard
BEFORE UPDATE ON video_slot_reservations
BEGIN
  SELECT RAISE(ABORT, 'reservation identity immutable')
   WHERE NEW.slot_key IS NOT OLD.slot_key OR NEW.mp4_sha256 IS NOT OLD.mp4_sha256 OR NEW.created_at IS NOT OLD.created_at;
  SELECT RAISE(ABORT, 'reservation revision must increase exactly once') WHERE NEW.revision != OLD.revision + 1;
  SELECT RAISE(ABORT, 'invalid reservation transition')
   WHERE NOT (
        (OLD.status = 'reserved'             AND NEW.status IN ('reserved','upload_started'))
     OR (OLD.status = 'upload_started'       AND NEW.status IN ('upload_started','needs_reconciliation','reported_complete'))
     OR (OLD.status = 'needs_reconciliation' AND NEW.status = 'needs_reconciliation')
     OR (OLD.status = 'reported_complete'    AND NEW.status = 'reported_complete'));
  SELECT RAISE(ABORT, 'completion requires both platform observations')
   WHERE NEW.status = 'reported_complete' AND OLD.status != 'reported_complete'
     AND (SELECT COUNT(*) FROM video_platform_results
           WHERE slot_key = NEW.slot_key AND mp4_sha256 = NEW.mp4_sha256
             AND status = 'reported_success' AND remote_id IS NOT NULL
             AND platform IN ('youtube','instagram')) != 2;
END;
