# Áreas de trabajo y normalización DES → DESPOSTE

## Tablas y columnas revisadas (por módulo)

Cualquier valor **"DES"**, **"Des"** o **"des"** en estas columnas se asigna al área de trabajo **DESPOSTE** para que aparezca en el dashboard y en los listados de esa área.

| Módulo      | Tabla                  | Columna(s)     | Uso en dashboard DESPOSTE |
|------------|------------------------|-----------------|----------------------------|
| Usuarios   | `usuarios`             | `area`          | Área asignada al usuario   |
| Lockers    | `base_lockers`        | `area`, `area_lockers` | Total lockers, disponibles |
| Lockers    | `locker_disponibles`  | `area`, `area_lockers` | Listado Locker Disponibles |
| Dotaciones | `base_dotaciones`     | `area_uso`      | Total dotaciones           |
| Personal   | `registro_personal`   | `area`, `area_lockers` | Total personal             |
| Personal   | `personal_presupuestado` | `area`        | Listado personal presupuestado |
| Operaciones| `registro_asignaciones` | `area`, `area_lockers` | Total asignaciones, gráfico |
| Operaciones| `historial_retiros`   | `area`, `area_lockers` | Total retiros              |

## Cómo ejecutar la normalización

```bash
python scripts/actualizar_areas_y_crear_area_trabajo.py
```

- Primero normaliza **DES** → **DESPOSTE** (insensible a mayúsculas) en todas las tablas/columnas de la tabla anterior.
- Luego aplica el resto de reemplazos (LN→BENEFICIO, CAL→CALIDAD, etc.).

## Si el dashboard DESPOSTE sigue vacío

El dashboard por área filtra por:

- **Total lockers / Disponibles**: `base_lockers.area`
- **Total dotaciones**: `base_dotaciones.area_uso`
- **Personal**: `registro_personal.area`
- **Asignaciones / Gráfico**: `registro_asignaciones.area`
- **Retiros**: `historial_retiros.area`

Si en la base de datos no hay filas con `area` o `area_uso` = **DESPOSTE** en esas tablas, los totales del dashboard DESPOSTE serán 0. En ese caso hay que:

1. Revisar si en esas tablas existe el valor antiguo "DES" (o variantes) y volver a ejecutar el script, o  
2. Asignar manualmente el área **DESPOSTE** a los registros que correspondan (desde la app, entrando al área DESPOSTE y creando/editando registros).
