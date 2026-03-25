-- Solo crea la base de datos vacía (sin tablas).
-- Las tablas las crea la aplicación Flask al arrancar: db.create_all() en app/__init__.py
-- Ejecutar en MySQL Workbench como root, o: mysql -u root -p < database/00_crear_base_vacia.sql

CREATE DATABASE IF NOT EXISTS gestor_lockers
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE gestor_lockers;

-- No crear tablas aquí: el esquema actual lo generan los modelos en app/models/
