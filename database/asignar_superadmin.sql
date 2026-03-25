-- Asigna el rol 'superadmin' al usuario con id = 1.
-- Si tu único usuario tiene otro id, usa en su lugar:
--   UPDATE usuarios SET rol = 'superadmin' WHERE email = 'tu@correo.com';
-- O desde el proyecto: python scripts/asignar_superadmin.py
--   (si solo hay un usuario, asigna superadmin a ese; si hay varios: id=1 o pasar email).
--
-- Los usuarios borrados no se recuperan sin un respaldo (dump) de la base de datos.

UPDATE usuarios SET rol = 'superadmin' WHERE id = 1;
