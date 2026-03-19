-- Asigna el rol 'superadmin' al usuario con id = 1.
-- Solo ejecutar una vez (o cuando se quiera restaurar el superadmin).
-- Ejemplo: mysql -u usuario -p nombre_bd < database/asignar_superadmin.sql

UPDATE usuarios SET rol = 'superadmin' WHERE id = 1;
