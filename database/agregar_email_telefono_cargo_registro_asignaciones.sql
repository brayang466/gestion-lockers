-- Añade columnas para el registro de personal que se guarda en registro_asignaciones.
-- Ejecutar si la tabla ya existe: mysql -u usuario -p nombre_bd < database/agregar_email_telefono_cargo_registro_asignaciones.sql

-- Si la columna ya existe, omitir esa línea o comentarla.
ALTER TABLE registro_asignaciones ADD COLUMN email VARCHAR(120) DEFAULT '' AFTER identificacion;
ALTER TABLE registro_asignaciones ADD COLUMN telefono VARCHAR(30) DEFAULT '' AFTER email;
ALTER TABLE registro_asignaciones ADD COLUMN cargo VARCHAR(100) DEFAULT '' AFTER telefono;

-- Opcional: cambiar valores 'activa' a 'Activo'
UPDATE registro_asignaciones SET estado = 'Activo' WHERE estado = 'activa';
