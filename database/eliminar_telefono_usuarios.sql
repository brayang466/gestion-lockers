-- Eliminar columna telefono de la tabla usuarios (ya no se usa en el módulo Gestión de usuarios).
-- Ejecutar una vez en la base de datos (MySQL / MariaDB).

USE gestor_lockers;

ALTER TABLE usuarios DROP COLUMN telefono;
