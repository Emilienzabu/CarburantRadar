-- CarburantRadar radar V2 : snapshot France immuable et versionné (D1). CANDIDAT, NON APPLIQUÉ.
-- À appliquer d'abord sur une base D1 DE TEST. Aucune donnée utilisateur. Sans effet sur DB_STATS / DB_ITALIE.

CREATE TABLE IF NOT EXISTS snapshot_versions (
  version        TEXT PRIMARY KEY CHECK (version GLOB '[A-Za-z0-9._-]*' AND length(version) BETWEEN 1 AND 100),
  created_at     TEXT NOT NULL,
  sha256         TEXT NOT NULL CHECK (length(sha256) = 64),
  station_count  INTEGER NOT NULL CHECK (station_count >= 0),
  rejected_count INTEGER NOT NULL CHECK (rejected_count >= 0),
  source_total   INTEGER NOT NULL CHECK (source_total >= 0),
  status         TEXT NOT NULL DEFAULT 'staged' CHECK (status IN ('staged','activated','pruned'))
);

CREATE TABLE IF NOT EXISTS snapshot_active (
  id          INTEGER PRIMARY KEY CHECK (id = 1),
  version     TEXT NOT NULL REFERENCES snapshot_versions(version),
  revision    INTEGER NOT NULL CHECK (revision >= 1),
  switched_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS snapshot_lock (
  id         INTEGER PRIMARY KEY CHECK (id = 1),
  holder     TEXT NOT NULL,
  expires_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS snapshot_events (
  id      INTEGER PRIMARY KEY AUTOINCREMENT,
  at      INTEGER NOT NULL,
  kind    TEXT NOT NULL,
  version TEXT,
  detail  TEXT
);

-- Une version publiée ne change jamais : seules les transitions de statut sont permises.
CREATE TRIGGER IF NOT EXISTS snapshot_versions_immutable BEFORE UPDATE ON snapshot_versions
WHEN NEW.version <> OLD.version OR NEW.created_at <> OLD.created_at OR NEW.sha256 <> OLD.sha256
  OR NEW.station_count <> OLD.station_count OR NEW.rejected_count <> OLD.rejected_count OR NEW.source_total <> OLD.source_total
BEGIN SELECT RAISE(ABORT, 'snapshot_version_immutable'); END;

CREATE TRIGGER IF NOT EXISTS snapshot_versions_no_delete BEFORE DELETE ON snapshot_versions
BEGIN SELECT RAISE(ABORT, 'snapshot_version_undeletable'); END;

CREATE TRIGGER IF NOT EXISTS snapshot_status_forward BEFORE UPDATE OF status ON snapshot_versions
WHEN NOT (NEW.status = OLD.status
  OR (OLD.status = 'staged' AND NEW.status IN ('activated','pruned'))
  OR (OLD.status = 'activated' AND NEW.status = 'pruned'))
BEGIN SELECT RAISE(ABORT, 'snapshot_status_invalid'); END;

CREATE TRIGGER IF NOT EXISTS snapshot_active_not_prunable BEFORE UPDATE OF status ON snapshot_versions
WHEN NEW.status = 'pruned' AND EXISTS (SELECT 1 FROM snapshot_active WHERE version = OLD.version)
BEGIN SELECT RAISE(ABORT, 'snapshot_active_not_prunable'); END;

-- Le pointeur actif ne peut viser qu'une version jamais élaguée.
CREATE TRIGGER IF NOT EXISTS snapshot_active_target_insert BEFORE INSERT ON snapshot_active
WHEN (SELECT status FROM snapshot_versions WHERE version = NEW.version) IS NULL
  OR (SELECT status FROM snapshot_versions WHERE version = NEW.version) NOT IN ('staged','activated')
BEGIN SELECT RAISE(ABORT, 'snapshot_target_invalid'); END;

CREATE TRIGGER IF NOT EXISTS snapshot_active_target_update BEFORE UPDATE ON snapshot_active
WHEN (SELECT status FROM snapshot_versions WHERE version = NEW.version) IS NULL
  OR (SELECT status FROM snapshot_versions WHERE version = NEW.version) NOT IN ('staged','activated')
BEGIN SELECT RAISE(ABORT, 'snapshot_target_invalid'); END;

CREATE TRIGGER IF NOT EXISTS snapshot_active_revision_step BEFORE UPDATE ON snapshot_active
WHEN NEW.revision <> OLD.revision + 1 OR NEW.id <> OLD.id
BEGIN SELECT RAISE(ABORT, 'snapshot_revision_step'); END;

CREATE TRIGGER IF NOT EXISTS snapshot_active_no_delete BEFORE DELETE ON snapshot_active
BEGIN SELECT RAISE(ABORT, 'snapshot_active_undeletable'); END;

CREATE TRIGGER IF NOT EXISTS snapshot_active_mark_insert AFTER INSERT ON snapshot_active
BEGIN UPDATE snapshot_versions SET status = 'activated' WHERE version = NEW.version AND status = 'staged'; END;

CREATE TRIGGER IF NOT EXISTS snapshot_active_mark_update AFTER UPDATE ON snapshot_active
BEGIN UPDATE snapshot_versions SET status = 'activated' WHERE version = NEW.version AND status = 'staged'; END;
