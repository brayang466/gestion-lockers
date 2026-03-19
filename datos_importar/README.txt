Pon aquí los CSV exportados de tus hojas (uno por tabla).
Nombres esperados:
  base_lockers.csv, base_dotaciones.csv, registro_personal.csv, personal_presupuestado.csv,
  dotaciones_disponibles.csv, locker_disponibles.csv, registro_asignaciones.csv, historial_retiros.csv

Importación específica área DESPOSTE:
  - DOTACION DESPOSTE.csv → Base de Dotaciones (solo área DESPOSTE): python database/importar_dotacion_desposte.py
  - LOCKERS DES.csv → Base de Lockers y Locker Disponibles (solo área DESPOSTE): python database/importar_lockers_desposte.py
  - ASIGNACIONES DESPOSTE.csv → Registro de Asignaciones (DES + subáreas): python database/importar_asignaciones_desposte.py
  - RETIROS DESPOSTE.csv → Historial de Retiros (DES + subáreas): python database/importar_retiros_desposte.py
  Antes de importar lockers Desposte, ejecutar: python database/agregar_subarea_lockers.py

INGRESO DE LOCKERS e INGRESO DE DOTACION no se importan (son para registro manual en la app).
Orden: base_lockers, base_dotaciones, registro_personal, personal_presupuestado,
  dotaciones_disponibles, locker_disponibles, registro_asignaciones, historial_retiros.
Ejecutar: python scripts/importar_todo.py (o --replace para vaciar antes).
Si ya tenías la BD creada, ejecuta antes database/migrar_cabeceras.sql en Workbench.
