Pon aquí los CSV exportados de tus hojas (uno por tabla).
Nombres canónicos (o alias que importar_todo.py reconoce automáticamente):
  base_lockers.csv  ó  LOCKERES.csv
  base_dotaciones.csv  ó  DOTACIONES.csv
  registro_personal.csv  ó  PERSONAL.csv
  personal_presupuestado.csv  ó  PERSONAL PRESUPUESTADO.csv
  dotaciones_disponibles.csv  ó  DOTACIONES DISPONIBLES.csv
  locker_disponibles.csv  ó  LOCKER DISPONIBLES.csv
  registro_asignaciones.csv  ó  ASIGNACIONES ACTUALIZADO.csv  ó  ASIGNACIONES.csv
  historial_retiros.csv  ó  RETIROS.csv
Si existen ambos nombres, se usa primero el canónico (si tiene al menos 2 filas).

Validar ASIGNACIONES.csv (áreas generales; Desposte va aparte en ASIGNACIONES DESPOSTE.csv):
  python scripts/validar_asignaciones_csv.py
  python scripts/validar_asignaciones_csv.py --no-db

Carga completa tras reinstalar MySQL (CSV en esta carpeta):
  python database/cargar_datos_desde_csv.py --replace
  Ver docs/CARGAR_DATOS_DESPUES_DE_REINSTALAR.md

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
