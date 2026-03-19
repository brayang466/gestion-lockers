"""
Elimina columnas que están vacías y no se usan (según análisis).
Ejecutar desde la raíz: python database/aplicar_eliminar_columnas_vacias.py
"""
import os
import sys
from pathlib import Path

raiz = Path(__file__).resolve().parent.parent
env_file = raiz / ".env"
if env_file.exists():
    with open(env_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                k, v = k.strip(), v.strip()
                if len(v) >= 2 and v[0] == v[-1] and v[0] in ('"', "'"):
                    v = v[1:-1]
                os.environ.setdefault(k, v)


def main():
    import pymysql

    host = os.environ.get("MYSQL_HOST", "127.0.0.1")
    port = int(os.environ.get("MYSQL_PORT", "3306"))
    user = os.environ.get("MYSQL_USER", "root")
    password = os.environ.get("MYSQL_PASSWORD", "")
    database = os.environ.get("MYSQL_DATABASE", "gestor_lockers")

    conn = pymysql.connect(
        host=host, port=port, user=user, password=password,
        database=database, charset="utf8mb4",
    )
    drops = [
        ("registro_asignaciones", "personal_id"),
        ("registro_asignaciones", "locker_id"),
        ("registro_asignaciones", "dotacion_id"),
        ("registro_asignaciones", "fecha_devolucion"),
        ("usuarios", "telefono"),
    ]
    try:
        with conn.cursor() as cur:
            for table, col in drops:
                cur.execute(
                    "SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS "
                    "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND COLUMN_NAME = %s",
                    (database, table, col),
                )
                if cur.fetchone():
                    cur.execute(f"ALTER TABLE `{table}` DROP COLUMN `{col}`")
                    print(f"Eliminada columna: {table}.{col}")
                else:
                    print(f"La columna {table}.{col} no existe, se omite.")
        conn.commit()
        print("Listo.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
