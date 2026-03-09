# Roles de usuario

En el encabezado se muestra el **rol** debajo del nombre del usuario.

## Tipos de rol

| Rol en BD   | Se muestra como   | Permisos |
|-------------|-------------------|----------|
| `admin`     | **Administrador**  | Acceso total: ver, crear, editar y eliminar en todos los módulos y áreas. |
| `coordinador` | **Coordinador** | Ver, crear, editar y eliminar **solo en su área asignada**. En módulos con área (Base de Lockers, Registro de Personal, etc.) solo ve y modifica registros de su área. |
| `usuario`   | **Usuario**       | Solo **consulta**: puede ver listados y datos, no puede crear, editar ni eliminar. |

## Asignación de roles

- **Nuevos registros**: Quien se registra por la pantalla de **Registro** recibe automáticamente el rol **Usuario**.
- **Administrador**: Crear con `python scripts/crear_admin.py` (ya asigna `rol=admin`).
- **Coordinador**: Asignar manualmente en la base de datos:
  - `rol = 'coordinador'`
  - `area = 'Nombre del área'` (debe coincidir con el valor de la columna área/area_uso en los módulos que use).

## Base de datos

Si la tabla `usuarios` se creó antes de tener roles/área, ejecuta:

```sql
-- database/agregar_rol_area_usuarios.sql
ALTER TABLE usuarios ADD COLUMN area VARCHAR(100) DEFAULT '' AFTER rol;
```

(Si la columna `area` ya existe, omite o comenta esa línea.)
