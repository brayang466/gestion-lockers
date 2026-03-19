"""
Analiza las tablas de la BD y reporta columnas que están vacías (NULL o '').
Ejecutar desde la raíz: python database/analizar_columnas_vacias.py
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
    report = []
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
                "WHERE TABLE_SCHEMA = %s AND TABLE_TYPE = 'BASE TABLE' ORDER BY TABLE_NAME",
                (database,),
            )
            tables = [r[0] for r in cur.fetchall()]
        for table in tables:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS "
                    "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND EXTRA NOT LIKE '%%auto_increment%%'",
                    (database, table),
                )
                columns = cur.fetchall()
            total = None
            for col_name, data_type in columns:
                if col_name == "id":
                    cur2 = conn.cursor()
                    cur2.execute(f"SELECT COUNT(*) FROM `{table}`")
                    total = cur2.fetchone()[0]
                    cur2.close()
                    if total == 0:
                        report.append((table, col_name, "tabla vacía", 0, 0))
                    continue
                if total is None:
                    cur2 = conn.cursor()
                    cur2.execute(f"SELECT COUNT(*) FROM `{table}`")
                    total = cur2.fetchone()[0]
                    cur2.close()
                if total == 0:
                    report.append((table, col_name, "tabla vacía", 0, 0))
                    continue
                # Contar no vacíos: NOT NULL y != ''
                if data_type in ("int", "bigint", "smallint", "tinyint", "decimal", "float", "double"):
                    cur2 = conn.cursor()
                    cur2.execute(f"SELECT COUNT(*) FROM `{table}` WHERE `{col_name}` IS NOT NULL")
                    non_null = cur2.fetchone()[0]
                    cur2.close()
                    empty = total - non_null
                else:
                    cur2 = conn.cursor()
                    cur2.execute(
                        f"SELECT COUNT(*) FROM `{table}` WHERE `{col_name}` IS NOT NULL AND TRIM(COALESCE(`{col_name}`,'')) != ''"
                    )
                    filled = cur2.fetchone()[0]
                    cur2.close()
                    empty = total - filled
                if empty == total:
                    report.append((table, col_name, "100% vacío", total, 0))
                elif empty >= total * 0.9:
                    report.append((table, col_name, f"{100*empty//total}% vacío", total, total - empty))
    finally:
        conn.close()

    print("=== Columnas vacías o casi vacías ===\n")
    by_table = {}
    for table, col, reason, total, filled in report:
        by_table.setdefault(table, []).append((col, reason, total, filled))
    for table in sorted(by_table.keys()):
        print(f"Tabla: {table}")
        for col, reason, total, filled in by_table[table]:
            print(f"  - {col}: {reason} (total filas: {total}, con valor: {filled})")
        print()
    return report

if __name__ == "__main__":
    main()
