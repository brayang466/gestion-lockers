-- Añadir columna palabra_clave a usuarios (pista para recordar contraseña).
-- Ejecutar en MySQL si la tabla usuarios ya existía sin esta columna.

USE gestor_lockers;

ALTER TABLE usuarios
  ADD COLUMN palabra_clave VARCHAR(80) DEFAULT '' AFTER area;
