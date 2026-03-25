# Recuperar la base de datos desde cero (XAMPP + MySQL Workbench)

Si **no guardaste un respaldo** (`gestor_lockers_dump.sql`), no se pueden recuperar los datos antiguos: solo se puede **reconstruir la estructura** y **volver a cargar** CSV/scripts del proyecto.

> **Importante:** `database/crear_bd.sql` es un esquema **antiguo** y **no coincide** con la app actual.  
> La forma correcta hoy es: **base vacía + arrancar Flask** (`db.create_all()`) + migraciones Python en `database/*.py` + importadores.

---

## 1) Instalar XAMPP (MySQL)

1. Descarga XAMPP desde [https://www.apachefriends.org](https://www.apachefriends.org).
2. Instala y abre el **Panel de control XAMPP**.
3. Pulsa **Start** en **MySQL** (el puerto por defecto es **3306**).
4. Si Windows pregunta por firewall, permite acceso privado.

**Usuario `root`:** en una instalación nueva suele pedirte definir contraseña o dejarla vacía. Anota lo que uses; lo pondrás en el `.env`.

---

## 2) Instalar MySQL Workbench

1. Descarga desde [https://dev.mysql.com/downloads/workbench/](https://dev.mysql.com/downloads/workbench/).
2. Instala y abre Workbench.

### Conexión como **root**

1. **MySQL Connections** → **+** (nueva conexión).
2. **Connection Name:** `XAMPP Local Root` (o el nombre que quieras).
3. **Hostname:** `127.0.0.1` o `localhost`
4. **Port:** `3306`
5. **Username:** `root`
6. **Password:** **Store in Keychain** → la contraseña de root (o vacío si no tiene).
7. **Test Connection** → **OK** → **Close**.

### Conexión “normal” (usuario de la app)

Después de crear el usuario `gestor_adm` (paso 5), crea otra conexión:

- **Username:** `gestor_adm`
- **Password:** la del script `database/crear_usuario.sql` (por defecto `adm2026` si no lo cambiaste).
- Mismo host y puerto.

---

## 3) Crear solo la base vacía

En Workbench, conectado como **root**:

1. **File → Open SQL Script…** → elige `database/00_crear_base_vacia.sql`
2. Ejecuta el script (rayo ⚡).

O manualmente:

```sql
CREATE DATABASE IF NOT EXISTS gestor_lockers
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

---

## 4) Configurar `.env` en la raíz del proyecto

Ejemplo si usas **root** sin contraseña:

```env
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=
MYSQL_DATABASE=gestor_lockers
```

Si usas **gestor_adm**:

```env
MYSQL_USER=gestor_adm
MYSQL_PASSWORD=adm2026
```

---

## 5) Crear tablas con la app (recomendado)

Con el venv activado y dependencias instaladas:

```powershell
cd ruta\al\proyecto
.\.venv\Scripts\activate
pip install -r requirements.txt
python -c "from app import create_app; create_app(); print('Tablas OK')"
```

Eso ejecuta `db.create_all()` y crea **todas** las tablas según `app/models/`.

---

## 6) Migraciones adicionales (columnas que a veces faltan en BD vieja)

En una instalación **nueva** con `create_all()` muchas ya no hacen falta; son **idempotentes** o fallan si la columna existe (en ese caso ignora o comenta la línea en el `.sql`).

Ejecuta **en este orden** si algo falla al arrancar la app:

| Orden | Archivo / comando | Para qué |
|------|---------------------|----------|
| 1 | `python database/agregar_subarea_lockers.py` | Columna `subarea` en lockers |
| 2 | `python database/aplicar_migracion_registro_asignaciones.py` | Email/teléfono/cargo en asignaciones |
| 3 | SQL: `database/agregar_rol_area_usuarios.sql` | Columna `area` en usuarios (si la BD era antigua) |
| 4 | SQL: `database/agregar_palabra_clave_usuarios.sql` | Columna `palabra_clave` |
| 5 | SQL: `database/agregar_email_telefono_cargo_registro_asignaciones.sql` | Si aplica |

Si **empezaste solo con `create_all()`** y la app arranca sin error de columnas, puedes **omitir** los SQL de ALTER que fallen por “columna duplicada”.

---

## 7) Usuario MySQL dedicado (opcional pero recomendado)

En Workbench como **root**, ejecuta `database/crear_usuario.sql`  
(cambia la contraseña en el script si no quieres usar la por defecto).

Luego actualiza `.env` con `gestor_adm` y su clave.

---

## 8) Primer usuario para entrar a la app

```powershell
python scripts\crear_admin.py
```

Sigue las indicaciones (email, contraseña, rol).

---

## 9) Volver a meter datos (sin backup)

No se recuperan datos que no estén en un archivo. Usa **todos los CSV** que tengas en `datos_importar/`:

```powershell
python database\cargar_datos_desde_csv.py --replace
```

Eso ejecuta `importar_todo` y, si existen, los CSV de DESPOSTE. Detalle: **`docs/CARGAR_DATOS_DESPUES_DE_REINSTALAR.md`**.

Alternativa manual: `datos_importar/README.txt`, `python scripts/importar_todo.py [--replace]` y luego cada `database/importar_*_desposte.py`.

---

## 10) Arrancar la aplicación

```powershell
python run.py
```

Abre `http://127.0.0.1:5000` y prueba login.

---

## Si en el futuro quieres no perder datos otra vez

En un equipo donde la BD **sí funciona**:

```powershell
python scripts\exportar_bd.py
```

Se genera `database/gestor_lockers_dump.sql`. Cópialo a un USB/nube. En el nuevo PC: crear base vacía y `python scripts\restaurar_bd.py` (ver `docs/BASE_DATOS_OTRO_EQUIPO.md`).

---

## Resumen rápido

1. XAMPP → MySQL **Start**  
2. Workbench → conexión **root**  
3. Ejecutar `database/00_crear_base_vacia.sql`  
4. `.env` con `MYSQL_*`  
5. `python -c "from app import create_app; create_app()"`  
6. `python database/agregar_subarea_lockers.py` (y otros si hace falta)  
7. Opcional: `crear_usuario.sql`  
8. `python scripts/crear_admin.py`  
9. Importar CSV / scripts DESPOSTE  
10. `python run.py`
