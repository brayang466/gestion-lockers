# Cómo aplicar cambios de columnas en las tablas

Cuando elimines o agregues columnas en una tabla de la base de datos, debes mantener **sincronizado** el código en estos lugares:

---

## Regla: ID en Registro de Asignaciones (ASG-00)

Al **insertar** un nuevo registro en `registro_asignaciones` (desde "Registro personal" o desde el módulo "Registro de Asignaciones"), se debe asignar `id_asignaciones` con formato **ASG-00**, **ASG-01**, etc. (autoincrementable). En `app/routes/main.py` se usa la función `_get_next_id_asignaciones()` para obtener el siguiente valor. Si en el futuro se agregan más flujos que crean `RegistroAsignaciones`, hay que llamar a `_get_next_id_asignaciones()` y asignar el resultado a `obj.id_asignaciones` antes de `db.session.add(obj)`.

---

## 1. Modelo (Python)

**Archivo:** `app/models/<nombre_tabla>.py`

- **Quitar columna:** borra la línea `db.Column(...)` correspondiente.
- **Agregar columna:** añade una línea con el tipo correcto, por ejemplo:
  `nombre_campo = db.Column(db.String(100), default="")`

El nombre del archivo suele ser el de la tabla en snake_case (ej. `base_dotaciones` → `app/models/base_dotaciones.py`).

---

## 2. Configuración del módulo en el backend (Python)

**Archivo:** `app/routes/main.py`

Busca el bloque del módulo en `MODULOS_CONFIG` (ej. `"base-dotaciones": { ... }`):

- **`columnas`:** lista de `{"key": "nombre_campo", "label": "Etiqueta"}`. Quita o agrega entradas según las columnas que quieras mostrar en la tabla del listado.
- **`form_fields`:** lista de `{"name": "nombre_campo", "label": "Etiqueta", "type": "text"|"number"|"date"|"textarea"}`. Quita o agrega según los campos del formulario de crear/editar.

Solo toca las entradas del módulo de esa tabla (no otras).

---

## 3. Frontend (si lo usas)

**Archivo:** `frontend/src/config/modulesConfig.js`

Busca el objeto del módulo (ej. `path: 'base-dotaciones'`) y ajusta:

- **`columns`:** mismas keys que en el backend para la tabla.
- **`formFields`:** mismos campos que en el backend para el formulario.

---

## 4. Scripts de importación (si importas CSV/Excel)

**Archivo:** `scripts/import_datos.py`

Si existe una función `import_<tabla>` para esa tabla, revisa el mapeo de columnas del CSV a los nombres del modelo. Quita o agrega según las columnas que tenga el modelo.

---

## 5. Base de datos

- **Eliminar columna:** ejecuta en tu BD, por ejemplo:
  ```sql
  ALTER TABLE nombre_tabla DROP COLUMN nombre_columna;
  ```
- **Agregar columna:** por ejemplo:
  ```sql
  ALTER TABLE nombre_tabla ADD COLUMN nombre_columna VARCHAR(100) DEFAULT '';
  ```

Puedes guardar estos `ALTER TABLE` en un archivo en `database/` (ej. `database/cambios_base_dotaciones.sql`) para tener historial.

---

## Resumen por tabla

| Dónde | Qué tocar |
|-------|-----------|
| BD | `ALTER TABLE ... DROP/ADD COLUMN` |
| `app/models/<tabla>.py` | Definición de columnas del modelo |
| `app/routes/main.py` | `MODULOS_CONFIG["id-modulo"]` → `columnas` y `form_fields` |
| `frontend/.../modulesConfig.js` | Objeto del módulo → `columns` y `formFields` |
| `scripts/import_datos.py` | Función `import_<tabla>` y mapeo de columnas |

Después de cambiar el modelo y la configuración, **reinicia la aplicación** (por ejemplo `python run.py`) para que cargue los cambios.

---

## Si sigue el error "Unknown column 'tabla.columna' in 'field list'"

Significa que la columna sigue en el **código** pero ya no existe en la **base de datos**. Revisa:

1. **Modelo** (`app/models/<tabla>.py`): que **no** haya ninguna línea `nombre_columna = db.Column(...)` para esa columna. Si la borraste de la BD, tiene que estar borrada también aquí.
2. **form_fields** en `main.py`: en `MODULOS_CONFIG` del módulo de esa tabla, que **no** aparezca `{"name": "nombre_columna", ...}` en `form_fields`. Si está, la app intentará leer/escribir ese campo.
3. **Reiniciar bien la app:** cierra el proceso de `python run.py` y vuelve a ejecutarlo (y si quieres, borra la carpeta `app/__pycache__` y `app/models/__pycache__` para que no use código en caché).
