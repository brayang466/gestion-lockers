USE gestor_lockers;
ANALYZE TABLE usuarios;
ANALYZE TABLE registro_personal;
ANALYZE TABLE registro_asignaciones;
ANALYZE TABLE dotaciones_disponibles;
ANALYZE TABLE personal_presupuestado;
ANALYZE TABLE locker_disponibles;
ANALYZE TABLE historial_retiros;
ANALYZE TABLE ingreso_lockers;
ANALYZE TABLE ingreso_dotacion;
ANALYZE TABLE base_lockers;
ANALYZE TABLE base_dotaciones;

DROP VIEW IF EXISTS v_lockers_disponibles;
CREATE VIEW v_lockers_disponibles AS
SELECT id, codigo, estado, creado_en FROM base_lockers WHERE estado = 'disponible';

DROP VIEW IF EXISTS v_dotaciones_disponibles;
CREATE VIEW v_dotaciones_disponibles AS
SELECT id, codigo, descripcion, cantidad, unidad FROM dotaciones_disponibles WHERE cantidad > 0;
