# Informe: columnas vacías en la base de datos

Se analizó la BD con `python database/analizar_columnas_vacias.py`. Resumen:

---

## Columnas eliminadas (ya aplicado)

| Tabla | Columna | Motivo |
|-------|---------|--------|
| **registro_asignaciones** | personal_id | 100% vacía; la app usa codigo_lockets/codigo_dotacion, no FKs |
| **registro_asignaciones** | locker_id | 100% vacía; mismo motivo |
| **registro_asignaciones** | dotacion_id | 100% vacía; mismo motivo |
| **registro_asignaciones** | fecha_devolucion | 100% vacía; la app usa fecha_entrega |
| **usuarios** | telefono | 100% vacía; no existe en el modelo |

**Cómo se aplicó:** modelo actualizado en `app/models/registro_asignaciones.py` (quitados personal_id, locker_id, dotacion_id). En la BD se ejecutó `python database/aplicar_eliminar_columnas_vacias.py`.

---

## Columnas 100% vacías que se mantienen

- **base_lockers.observaciones** – 228 filas, 0 con valor. Se deja por si se quieren anotar observaciones en el futuro.
- **locker_disponibles.observaciones** – 75 filas, 0 con valor. Mismo criterio.

Si en tu caso no vas a usar observaciones en lockers, puedes eliminarlas con:
`ALTER TABLE base_lockers DROP COLUMN observaciones;` y lo mismo para `locker_disponibles`.

---

## Tablas vacías (0 filas)

- **ingreso_lockers** – La app ya no guarda aquí; los ingresos van a Base de Lockers. La tabla queda como legacy.
- **ingreso_dotacion** – Igual; los ingresos van a Base de Dotaciones.
- **registro_personal** – La app ya no la usa; el “Personal Registrado” viene de registro_asignaciones.

Opcional: si quieres borrar estas tablas para no tener estructura sin uso:
```sql
DROP TABLE IF EXISTS ingreso_lockers;
DROP TABLE IF EXISTS ingreso_dotacion;
DROP TABLE IF EXISTS registro_personal;
```
Antes de hacerlo, revisa que ningún script ni integración use estas tablas (p. ej. `scripts/import_datos.py`, `scripts/importar_todo.py`).

---

## Columnas con pocos valores (no eliminadas)

- **registro_asignaciones**: email, telefono, cargo ~98% vacíos (solo 2 filas con valor). Se mantienen porque el formulario “Registro personal” sí los usa para registros nuevos.
- **personal_presupuestado**: nombre, documento, cargo, observaciones 100% vacíos en 5 filas; esos registros podrían tener solo aprobados/contratados/por_contratar. Se mantienen por ser parte del diseño del módulo.

---

## Cómo repetir el análisis

Desde la raíz del proyecto:
```bash
python database/analizar_columnas_vacias.py
```

Para aplicar de nuevo la eliminación de columnas (solo borra si existen):
```bash
python database/aplicar_eliminar_columnas_vacias.py
```
