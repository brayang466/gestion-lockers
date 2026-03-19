"""
Añade las columnas email, telefono y cargo a registro_asignaciones si no existen.
Ejecutar desde la raíz del proyecto: python database/aplicar_migracion_registro_asignaciones.py
"""
import os
import sys
from pathlib import Path

# Cargar .env manualmente para no depender de dotenv en el path
raiz = Path(__file__).resolve().parent.parent
env_file = raiz / ".env"
if env_file.exists():
    with open(env_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                k, v = k.strip(), v.strip()
                if v.startswith('"') and v.endswith('"') or v.startswith("'") and v.endswith("'"):
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
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
        charset="utf8mb4",
    )
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'registro_asignaciones'",
                (database,),
            )
            columnas = {r[0] for r in cur.fetchall()}

            if "email" not in columnas:
                cur.execute(
                    "ALTER TABLE registro_asignaciones ADD COLUMN email VARCHAR(120) DEFAULT '' AFTER identificacion"
                )
                print("Columna 'email' añadida.")
            else:
                print("Columna 'email' ya existe.")

            cur.execute(
                "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'registro_asignaciones'",
                (database,),
            )
            columnas = {r[0] for r in cur.fetchall()}

            if "telefono" not in columnas:
                cur.execute(
                    "ALTER TABLE registro_asignaciones ADD COLUMN telefono VARCHAR(30) DEFAULT '' AFTER email"
                )
                print("Columna 'telefono' añadida.")
            else:
                print("Columna 'telefono' ya existe.")

            if "cargo" not in columnas:
                cur.execute(
                    "ALTER TABLE registro_asignaciones ADD COLUMN cargo VARCHAR(100) DEFAULT '' AFTER telefono"
                )
                print("Columna 'cargo' añadida.")
            else:
                print("Columna 'cargo' ya existe.")

            cur.execute("UPDATE registro_asignaciones SET estado = 'Activo' WHERE estado = 'activa'")
            if cur.rowcount:
                print(f"Actualizados {cur.rowcount} registros de estado 'activa' a 'Activo'.")
        conn.commit()
        print("Migración aplicada correctamente.")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
