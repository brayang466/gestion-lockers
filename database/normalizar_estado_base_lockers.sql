-- Normaliza la columna estado en base_lockers: elimina la palabra "LOCKERT"
-- y deja solo el estado real (ej: "LOCKERT disponible" -> "disponible").
-- Ejecutar una vez sobre los datos existentes.
-- Ejemplo: mysql -u usuario -p nombre_bd < database/normalizar_estado_base_lockers.sql

UPDATE base_lockers
SET estado = TRIM(REPLACE(estado, 'LOCKERT', ''))
WHERE estado LIKE '%LOCKERT%';

-- Si quedó vacío, dejar 'disponible'
UPDATE base_lockers
SET estado = 'disponible'
WHERE TRIM(estado) = '' OR estado IS NULL;
