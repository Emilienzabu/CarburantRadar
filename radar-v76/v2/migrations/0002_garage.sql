-- CarburantRadar radar V2 : garage synchronisé par compte (D1). CANDIDAT, NON APPLIQUÉ.
-- Une ligne par compte. user_id vient UNIQUEMENT de l'authentification côté serveur, jamais du corps de la requête.

CREATE TABLE IF NOT EXISTS garages (
  user_id    TEXT PRIMARY KEY CHECK (length(user_id) BETWEEN 1 AND 128),
  revision   INTEGER NOT NULL CHECK (revision >= 1),
  body       TEXT NOT NULL CHECK (length(body) <= 32768),
  updated_at INTEGER NOT NULL
);

-- Comparaison-et-échange : la révision avance d'exactement 1, jamais en arrière, et le compte ne change jamais.
CREATE TRIGGER IF NOT EXISTS garages_revision_step BEFORE UPDATE ON garages
WHEN NEW.revision <> OLD.revision + 1 OR NEW.user_id <> OLD.user_id
BEGIN SELECT RAISE(ABORT, 'garage_revision_step'); END;
