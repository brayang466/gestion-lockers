-- Ejecutar una vez contra tu base de datos antes de usar la app con esta versión.
-- MariaDB / MySQL:

ALTER TABLE historial_retiros
  ADD COLUMN observaciones VARCHAR(500) NOT NULL DEFAULT '';

-- SQLite (ejemplo):
-- ALTER TABLE historial_retiros ADD COLUMN observaciones TEXT NOT NULL DEFAULT '';

