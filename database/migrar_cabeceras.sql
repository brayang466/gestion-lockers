-- Ejecutar en MySQL Workbench si ya tenías las tablas. Añade columnas de tus hojas.
-- Si alguna columna ya existe, comenta esa línea.

USE gestor_lockers;

ALTER TABLE registro_personal ADD COLUMN id_personal VARCHAR(50) DEFAULT '' AFTER id;
ALTER TABLE registro_personal ADD COLUMN talla VARCHAR(20) DEFAULT '' AFTER area;
ALTER TABLE registro_personal ADD COLUMN area_lockers VARCHAR(100) DEFAULT '' AFTER talla;
ALTER TABLE registro_personal ADD COLUMN estado VARCHAR(40) DEFAULT '' AFTER area_lockers;

ALTER TABLE registro_asignaciones ADD COLUMN id_asignaciones VARCHAR(50) DEFAULT '' AFTER id;
ALTER TABLE registro_asignaciones ADD COLUMN codigo_dotacion VARCHAR(50) DEFAULT '' AFTER dotacion_id;
ALTER TABLE registro_asignaciones ADD COLUMN fecha_entrega DATETIME NULL AFTER fecha_asignacion;
ALTER TABLE registro_asignaciones ADD COLUMN operario VARCHAR(120) DEFAULT '' AFTER fecha_entrega;
ALTER TABLE registro_asignaciones ADD COLUMN codigo_lockets VARCHAR(50) DEFAULT '' AFTER operario;
ALTER TABLE registro_asignaciones ADD COLUMN identificacion VARCHAR(40) DEFAULT '' AFTER codigo_lockets;
ALTER TABLE registro_asignaciones ADD COLUMN codigo_seca_botas VARCHAR(50) DEFAULT '' AFTER identificacion;
ALTER TABLE registro_asignaciones ADD COLUMN area VARCHAR(100) DEFAULT '' AFTER codigo_seca_botas;
ALTER TABLE registro_asignaciones ADD COLUMN talla_operarios VARCHAR(20) DEFAULT '' AFTER area;
ALTER TABLE registro_asignaciones ADD COLUMN talla_dotacion VARCHAR(20) DEFAULT '' AFTER talla_operarios;
ALTER TABLE registro_asignaciones ADD COLUMN area_lockers VARCHAR(100) DEFAULT '' AFTER talla_dotacion;

ALTER TABLE dotaciones_disponibles ADD COLUMN talla VARCHAR(20) DEFAULT '' AFTER codigo;

ALTER TABLE personal_presupuestado ADD COLUMN aprobados INT DEFAULT NULL AFTER area;
ALTER TABLE personal_presupuestado ADD COLUMN contratados INT DEFAULT NULL AFTER aprobados;
ALTER TABLE personal_presupuestado ADD COLUMN por_contratar INT DEFAULT NULL AFTER contratados;

ALTER TABLE locker_disponibles ADD COLUMN area VARCHAR(100) DEFAULT '' AFTER codigo;
ALTER TABLE locker_disponibles ADD COLUMN area_lockers VARCHAR(100) DEFAULT '' AFTER area;

ALTER TABLE historial_retiros ADD COLUMN id_retiro VARCHAR(50) DEFAULT '' AFTER id;
ALTER TABLE historial_retiros ADD COLUMN identificacion VARCHAR(40) DEFAULT '' AFTER dotacion_id;
ALTER TABLE historial_retiros ADD COLUMN codigo_dotacion VARCHAR(50) DEFAULT '' AFTER identificacion;
ALTER TABLE historial_retiros ADD COLUMN operario VARCHAR(120) DEFAULT '' AFTER fecha_retiro;
ALTER TABLE historial_retiros ADD COLUMN codigo_lockets VARCHAR(50) DEFAULT '' AFTER operario;
ALTER TABLE historial_retiros ADD COLUMN area VARCHAR(100) DEFAULT '' AFTER codigo_lockets;
ALTER TABLE historial_retiros ADD COLUMN talla_operarios VARCHAR(20) DEFAULT '' AFTER area;
ALTER TABLE historial_retiros ADD COLUMN talla_dotacion VARCHAR(20) DEFAULT '' AFTER talla_operarios;
ALTER TABLE historial_retiros ADD COLUMN area_lockers VARCHAR(100) DEFAULT '' AFTER talla_dotacion;

ALTER TABLE base_lockers ADD COLUMN area VARCHAR(100) DEFAULT '' AFTER codigo;
ALTER TABLE base_lockers ADD COLUMN area_lockers VARCHAR(100) DEFAULT '' AFTER area;
ALTER TABLE base_lockers ADD COLUMN unidad VARCHAR(30) DEFAULT '' AFTER estado;

ALTER TABLE base_dotaciones ADD COLUMN cantidad INT DEFAULT NULL AFTER codigo;
ALTER TABLE base_dotaciones ADD COLUMN area_uso VARCHAR(100) DEFAULT '' AFTER descripcion;
ALTER TABLE base_dotaciones ADD COLUMN talla VARCHAR(20) DEFAULT '' AFTER area_uso;
ALTER TABLE base_dotaciones ADD COLUMN estado VARCHAR(40) DEFAULT '' AFTER talla;
