# Base de datos en otro equipo

Para trabajar en otro equipo con la **misma información** (tablas y datos) que en el actual:

## En el equipo actual (donde ya tienes la BD con datos)

1. Asegúrate de tener el `.env` configurado (igual que para la app).
2. Ejecuta:
   ```bash
   python scripts/exportar_bd.py
   ```
3. Se crea el archivo **`database/gestor_lockers_dump.sql`** con la estructura y todos los datos de la base de datos.

## Llevar la información al otro equipo

- **Opción A:** Copia el archivo `database/gestor_lockers_dump.sql` (USB, nube, etc.) al mismo sitio en el proyecto en el otro equipo (`database/gestor_lockers_dump.sql`).
- **Opción B:** Si quieres versionar el dump en GitHub, quita del `.gitignore` la línea `database/gestor_lockers_dump.sql`, haz commit y push. En el otro equipo haz pull y tendrás el archivo. (Solo recomendable si el dump no es muy grande y no contiene datos sensibles.)

## En el otro equipo

1. Clona o copia el proyecto (si no lo tienes ya).
2. Crea el `.env` con los datos de MySQL de **ese** equipo (usuario, contraseña, host, etc.).
3. Si es la primera vez en ese equipo, crea la base vacía con:
   ```bash
   mysql -u usuario -p < database/crear_bd.sql
   ```
   (o ejecuta `crear_bd.sql` desde MySQL Workbench).
4. Coloca el archivo `gestor_lockers_dump.sql` en la carpeta `database/` (si no lo copiaste ya).
5. Restaura la base de datos:
   ```bash
   python scripts/restaurar_bd.py
   ```
6. Listo: la base de datos en ese equipo queda igual que en el de origen. Arranca la app con `python run.py`.

## Resumen

| Acción        | Comando                    |
|---------------|----------------------------|
| Exportar BD   | `python scripts/exportar_bd.py` |
| Restaurar BD  | `python scripts/restaurar_bd.py` |

Ambos scripts usan las variables `MYSQL_*` del `.env`, así que en cada equipo solo necesitas un `.env` correcto para ese MySQL.
