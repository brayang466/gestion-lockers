# Volver a llenar la base de datos después de reinstalar MySQL

Si **no tienes** un archivo de respaldo (`gestor_lockers_dump.sql`), **no es posible recuperar** los datos que solo vivían en el MySQL anterior. Lo que sí puedes hacer es **volver a cargar** todo lo que tengas en archivos del proyecto.

## Opción A — Un solo comando (recomendado)

Con el venv activado y el `.env` apuntando a tu MySQL:

```powershell
cd C:\Users\TIC\gestor_lockers
.\.venv\Scripts\activate
python database\cargar_datos_desde_csv.py --replace
```

Qué hace:

1. Rellena la tabla **`area_trabajo`** (BENEFICIO, DESPOSTE, CALIDAD, LYD, PCC, LOGISTICA) si faltan filas.
2. Ejecuta **`scripts/importar_todo.py --replace`** con los CSV estándar que estén en **`datos_importar/`**:
   - `base_lockers.csv`
   - `base_dotaciones.csv`
   - `registro_personal.csv`
   - `personal_presupuestado.csv`
   - `dotaciones_disponibles.csv`
   - `locker_disponibles.csv`
   - `registro_asignaciones.csv`
   - `historial_retiros.csv`
3. Si existen estos archivos en **`datos_importar/`**, ejecuta además los importadores DESPOSTE:
   - `DOTACION DESPOSTE.csv`
   - `LOCKERS DES.csv`
   - `ASIGNACIONES DESPOSTE.csv`
   - `RETIROS DESPOSTE.csv`

`--replace` vacía cada tabla afectada **antes** de importar ese CSV (útil en una BD recién creada).

Sin `--replace`, los datos se **añaden** a lo que ya haya (puede duplicar si no vacías antes).

## Opción B — Restaurar copia completa (si alguna vez exportaste)

Si en otro equipo o antes del desastre generaste el dump:

```powershell
python scripts\exportar_bd.py   # solo en el PC que aún tenía los datos
```

En el PC nuevo, con la base `gestor_lockers` creada y `.env` correcto:

```powershell
python scripts\restaurar_bd.py
```

Ver también `docs/BASE_DATOS_OTRO_EQUIPO.md`.

## Qué debes tener en `datos_importar/`

Copia ahí **todos los CSV** que uses (los nombres deben coincidir con los del script o con `datos_importar/README.txt`).

Si falta un archivo, ese módulo quedará vacío o con lo que ya hubiera en la BD.

## Después de cargar

1. Crea de nuevo el usuario de la app si hace falta: `python scripts\crear_admin.py`
2. Arranca: `python run.py`
3. Comprueba login y cada área en el menú.

## Script `actualizar_areas_y_crear_area_trabajo.py`

Ese script **normaliza** códigos viejos de área (por ejemplo `DES` → `DESPOSTE`, `LOG` → `LOGISTICA`) en muchas tablas.  
Si trabajas con **subáreas de DESPOSTE** (`DES`, `CAL`, `LOG`, etc. en asignaciones/retiros), **no lo ejecutes** a ciegas después de importar los CSV de DESPOSTE, o revisa el impacto. Para solo tener el menú de áreas, **`cargar_datos_desde_csv.py` ya inserta `area_trabajo`** sin esos `UPDATE` masivos.
