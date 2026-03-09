# LockerBeef

Flask + MySQL (XAMPP / MySQL Workbench). Tablas alineadas con tus hojas (REGISTRO DE PERSONAL, ASIGNACIONES, BASE DE LOCKERS, etc.) + usuarios (admin).

## Instalación

1. `.venv\Scripts\activate` y `pip install -r requirements.txt`
2. MySQL encendido. En Workbench: **database/crear_bd.sql**. Si ya tenías la BD, ejecuta además **database/migrar_cabeceras.sql** para añadir columnas de tus cabeceras.
3. Configurar el archivo `.env` en la raíz del proyecto (MYSQL_* y, si quieres recuperación de contraseña por correo, MAIL_*). Ver **docs/RECUPERACION_CONTRASENA.md** para el correo.
4. Crear admin: `python scripts/crear_admin.py`

## Ejecutar

`python run.py` → http://127.0.0.1:5000

La aplicación usa **Flask + Jinja2 + MySQL**: login, dashboard con estadísticas y enlaces a los 10 módulos (Base de Lockers, Registro de Personal, etc.). Cada módulo tiene listado, crear, editar y eliminar desde el navegador.

## Importar datos (tus cabeceras ya mapeadas)

- CSV en **datos_importar/**: base_lockers.csv, base_dotaciones.csv, registro_personal.csv, personal_presupuestado.csv, dotaciones_disponibles.csv, locker_disponibles.csv, registro_asignaciones.csv, historial_retiros.csv.
- INGRESO DE LOCKERS e INGRESO DE DOTACION no se importan; son para registro manual (ver docs/FORMULARIOS_INGRESO.md).
- `python scripts/importar_todo.py` o por tabla: `python scripts/import_datos.py archivo.csv -t base_lockers --replace`

## Base de datos en otro equipo

Para llevar la base de datos (estructura + datos) a otro PC: **exportar** con `python scripts/exportar_bd.py` (genera `database/gestor_lockers_dump.sql`), copiar ese archivo al otro equipo y **restaurar** con `python scripts/restaurar_bd.py`. Ver **docs/BASE_DATOS_OTRO_EQUIPO.md**.

## Siguiente: Login, dashboard, módulos

Ver **docs/SIGUIENTE_LOGIN_DASHBOARD.md** para login, dashboard y menú de módulos.
