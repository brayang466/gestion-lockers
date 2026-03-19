"""
1. Elimina las columnas vacías (nombre, documento, cargo, observaciones) de personal_presupuestado.
2. Borra los datos actuales e importa desde datos_importar/PERSONAL PRESUPUESTADO.csv

Ejecutar desde la raíz: python database/personal_presupuestado_eliminar_columnas_y_importar.py
"""
import csv
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

    csv_path = raiz / "datos_importar" / "PERSONAL PRESUPUESTADO.csv"
    if not csv_path.exists():
        print(f"No se encontró {csv_path}")
        sys.exit(1)

    conn = pymysql.connect(
        host=host, port=port, user=user, password=password,
        database=database, charset="utf8mb4",
    )
    try:
        with conn.cursor() as cur:
            for col in ("nombre", "documento", "cargo", "observaciones"):
                cur.execute(
                    "SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS "
                    "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'personal_presupuestado' AND COLUMN_NAME = %s",
                    (database, col),
                )
                if cur.fetchone():
                    cur.execute(f"ALTER TABLE personal_presupuestado DROP COLUMN `{col}`")
                    print(f"Eliminada columna: personal_presupuestado.{col}")

            cur.execute("DELETE FROM personal_presupuestado")
            deleted = cur.rowcount
            print(f"Eliminados {deleted} registros anteriores.")

        conn.commit()

        with open(csv_path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        if not rows:
            print("El CSV no tiene filas de datos.")
            return
        # Cabeceras del CSV: AREA, APROBADOS, CONTRATADOS, POR CONTRATAR
        with conn.cursor() as cur:
            for row in rows:
                area = (row.get("AREA") or row.get("area") or "").strip()
                if not area:
                    continue
                try:
                    aprobados = int(row.get("APROBADOS") or row.get("aprobados") or 0)
                except (TypeError, ValueError):
                    aprobados = None
                try:
                    contratados = int(row.get("CONTRATADOS") or row.get("contratados") or 0)
                except (TypeError, ValueError):
                    contratados = None
                try:
                    por_contratar = int(row.get("POR CONTRATAR") or row.get("por_contratar") or 0)
                except (TypeError, ValueError):
                    por_contratar = None
                cur.execute(
                    "INSERT INTO personal_presupuestado (area, aprobados, contratados, por_contratar) VALUES (%s, %s, %s, %s)",
                    (area, aprobados, contratados, por_contratar),
                )
            conn.commit()
        print(f"Importadas {len(rows)} filas desde PERSONAL PRESUPUESTADO.csv")
        print("Listo.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
