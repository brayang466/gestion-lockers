-- Añadir columna area a usuarios (para rol Coordinador).
-- Ejecutar en MySQL si la tabla usuarios ya existía sin esta columna.

USE gestor_lockers;

-- Si la columna ya existe, omite este ALTER.
ALTER TABLE usuarios
  ADD COLUMN area VARCHAR(100) DEFAULT '' AFTER rol;
