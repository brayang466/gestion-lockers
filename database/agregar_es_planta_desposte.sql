-- Ejecutar una vez contra tu base de datos antes de usar la app con esta versión.
-- MariaDB / MySQL:

ALTER TABLE registro_asignaciones
  ADD COLUMN es_planta_desposte TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'True = CSV/import planta Desposte';

ALTER TABLE historial_retiros
  ADD COLUMN es_planta_desposte TINYINT(1) NOT NULL DEFAULT 0;

-- Tras aplicar columnas: volver a ejecutar los imports de planta si necesitas marcar datos DESPOSTE:
--   python database/importar_asignaciones_desposte.py
--   python database/importar_retiros_desposte.py

-- SQLite (ejemplo):
-- ALTER TABLE registro_asignaciones ADD COLUMN es_planta_desposte BOOLEAN NOT NULL DEFAULT 0;
-- ALTER TABLE historial_retiros ADD COLUMN es_planta_desposte BOOLEAN NOT NULL DEFAULT 0;
