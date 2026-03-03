-- Crear usuario dedicado para la aplicación (ejecutar como root en MySQL).
-- Base de datos: gestor_lockers
-- Usuario: gestor_adm  |  Clave: adm2026

-- Crear usuario (localhost para XAMPP/local)
CREATE USER IF NOT EXISTS 'gestor_adm'@'localhost' IDENTIFIED BY 'adm2026';

-- Dar todos los permisos sobre la base gestor_lockers
GRANT ALL PRIVILEGES ON gestor_lockers.* TO 'gestor_adm'@'localhost';

-- Aplicar cambios
FLUSH PRIVILEGES;

-- Opcional: si también accedes desde 127.0.0.1 (algunos clientes lo usan)
CREATE USER IF NOT EXISTS 'gestor_adm'@'127.0.0.1' IDENTIFIED BY 'adm2026';
GRANT ALL PRIVILEGES ON gestor_lockers.* TO 'gestor_adm'@'127.0.0.1';
FLUSH PRIVILEGES;
