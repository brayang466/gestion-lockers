-- Elimina el campo id_retiro de historial_retiros (innecesario).
-- Ejecutar en MySQL. Si la columna no existe, ignorar el error.

USE gestor_lockers;

ALTER TABLE historial_retiros DROP COLUMN id_retiro;
