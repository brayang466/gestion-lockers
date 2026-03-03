-- Ejecutar en MySQL Workbench. Base gestor_lockers: 10 tablas + usuarios (admin).

CREATE DATABASE IF NOT EXISTS gestor_lockers
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE gestor_lockers;

CREATE TABLE IF NOT EXISTS usuarios (
  id INT AUTO_INCREMENT PRIMARY KEY,
  nombre VARCHAR(120) NOT NULL,
  email VARCHAR(120) NOT NULL UNIQUE,
  password_hash VARCHAR(255) DEFAULT '',
  telefono VARCHAR(30) DEFAULT '',
  rol VARCHAR(30) DEFAULT 'admin',
  activo TINYINT(1) DEFAULT 1,
  creado_en DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS registro_personal (
  id INT AUTO_INCREMENT PRIMARY KEY,
  nombre VARCHAR(120) NOT NULL,
  documento VARCHAR(40) DEFAULT '',
  email VARCHAR(120) DEFAULT '',
  telefono VARCHAR(30) DEFAULT '',
  cargo VARCHAR(100) DEFAULT '',
  area VARCHAR(100) DEFAULT '',
  observaciones TEXT,
  creado_en DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS registro_asignaciones (
  id INT AUTO_INCREMENT PRIMARY KEY,
  personal_id INT NULL,
  locker_id INT NULL,
  dotacion_id INT NULL,
  fecha_asignacion DATETIME NOT NULL,
  fecha_devolucion DATETIME NULL,
  estado VARCHAR(40) DEFAULT 'activa',
  observaciones TEXT,
  creado_en DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS dotaciones_disponibles (
  id INT AUTO_INCREMENT PRIMARY KEY,
  codigo VARCHAR(50) DEFAULT '',
  descripcion VARCHAR(255) DEFAULT '',
  cantidad INT DEFAULT 0,
  unidad VARCHAR(30) DEFAULT '',
  observaciones TEXT,
  creado_en DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS personal_presupuestado (
  id INT AUTO_INCREMENT PRIMARY KEY,
  nombre VARCHAR(120) NOT NULL,
  documento VARCHAR(40) DEFAULT '',
  cargo VARCHAR(100) DEFAULT '',
  area VARCHAR(100) DEFAULT '',
  observaciones TEXT,
  creado_en DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS locker_disponibles (
  id INT AUTO_INCREMENT PRIMARY KEY,
  codigo VARCHAR(50) NOT NULL,
  estado VARCHAR(40) DEFAULT 'disponible',
  observaciones TEXT,
  creado_en DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS historial_retiros (
  id INT AUTO_INCREMENT PRIMARY KEY,
  asignacion_id INT NULL,
  personal_id INT NULL,
  locker_id INT NULL,
  dotacion_id INT NULL,
  fecha_retiro DATETIME NOT NULL,
  motivo VARCHAR(255) DEFAULT '',
  observaciones TEXT,
  creado_en DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS ingreso_lockers (
  id INT AUTO_INCREMENT PRIMARY KEY,
  codigo VARCHAR(50) DEFAULT '',
  cantidad INT DEFAULT 1,
  fecha_ingreso DATETIME NOT NULL,
  observaciones TEXT,
  creado_en DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS ingreso_dotacion (
  id INT AUTO_INCREMENT PRIMARY KEY,
  codigo VARCHAR(50) DEFAULT '',
  descripcion VARCHAR(255) DEFAULT '',
  cantidad INT DEFAULT 1,
  fecha_ingreso DATETIME NOT NULL,
  observaciones TEXT,
  creado_en DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS base_lockers (
  id INT AUTO_INCREMENT PRIMARY KEY,
  codigo VARCHAR(50) NOT NULL,
  estado VARCHAR(40) DEFAULT 'disponible',
  observaciones TEXT,
  creado_en DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS base_dotaciones (
  id INT AUTO_INCREMENT PRIMARY KEY,
  codigo VARCHAR(50) DEFAULT '',
  descripcion VARCHAR(255) DEFAULT '',
  unidad VARCHAR(30) DEFAULT '',
  observaciones TEXT,
  creado_en DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
