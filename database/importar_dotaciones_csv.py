"""
Actualiza base_dotaciones con datos de datos_importar/DOTACIONES.csv.
- Orden: registros desde 001 en adelante (numéricos primero), luego códigos que inician con letra.
- Códigos con letra: máximo 5 caracteres (ej. F-00, E001).
- Estado: se elimina prefijo/sufijo "DOTACION" (ej. DOTACION ASIGNADA -> ASIGNADA).

Columnas en el módulo (no se modifican): codigo, cantidad, talla, estado (+ area_uso en formulario).

Ejecutar desde la raíz: python database/importar_dotaciones_csv.py
"""
import csv
import re
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


def normalize_estado(estado):
    """Quita prefijo y sufijo 'DOTACION' del estado."""
    if not estado or not isinstance(estado, str):
        return (estado or "disponible").strip()
    s = estado.strip()
    s = re.sub(r"^DOTACION\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s*DOTACION\s*$", "", s, flags=re.IGNORECASE).strip()
    return s if s else "disponible"


def codigo_sort_key(codigo):
    """Orden: numéricos primero (001, 002, ...), luego los que inician con letra (E001, M001, ...)."""
    c = (codigo or "").strip()
    if not c:
        return (1, 0, "")
    # ¿Es solo dígitos (con ceros a la izq)?
    if c.isdigit():
        return (0, int(c), "")
    # Empieza con letra: después de los numéricos, ordenar por string
    return (1, 0, c)


def main():
    import pymysql

    host = os.environ.get("MYSQL_HOST", "127.0.0.1")
    port = int(os.environ.get("MYSQL_PORT", "3306"))
    user = os.environ.get("MYSQL_USER", "root")
    password = os.environ.get("MYSQL_PASSWORD", "")
    database = os.environ.get("MYSQL_DATABASE", "gestor_lockers")

    csv_path = raiz / "datos_importar" / "DOTACIONES.csv"
    if not csv_path.exists():
        print(f"No se encontró {csv_path}")
        sys.exit(1)

    rows = []
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            codigo = (row.get("Codigo de Dotacion") or row.get("Codigo de dotacion") or row.get("codigo") or "").strip()
            if not codigo:
                continue
            # Códigos que inician con letra: máximo 5 caracteres
            if codigo[0].isalpha() and len(codigo) > 5:
                codigo = codigo[:5]
            cantidad_raw = row.get("Cantidad") or row.get("cantidad") or "0"
            try:
                cantidad = int(cantidad_raw)
            except (TypeError, ValueError):
                cantidad = None
            area_uso = (row.get("Area de USO") or row.get("Area de Uso") or row.get("area_uso") or "").strip()
            talla = (row.get("Talla") or row.get("talla") or "").strip()
            estado = normalize_estado(row.get("ESTADO") or row.get("Estado") or row.get("estado") or "")
            rows.append({
                "codigo": codigo,
                "cantidad": cantidad,
                "area_uso": area_uso,
                "talla": talla,
                "estado": estado,
            })

    # Ordenar: 001, 002, ... luego E001, M001, ...
    rows.sort(key=lambda r: codigo_sort_key(r["codigo"]))

    conn = pymysql.connect(
        host=host, port=port, user=user, password=password,
        database=database, charset="utf8mb4",
    )
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM base_dotaciones")
            deleted = cur.rowcount
            print(f"Eliminados {deleted} registros anteriores.")

            for r in rows:
                cur.execute(
                    "INSERT INTO base_dotaciones (codigo, cantidad, area_uso, talla, estado) VALUES (%s, %s, %s, %s, %s)",
                    (r["codigo"], r["cantidad"], r["area_uso"], r["talla"], r["estado"]),
                )
        conn.commit()
        print(f"Importados {len(rows)} registros desde DOTACIONES.csv (orden: 001 en adelante, luego códigos con letra máx. 5 caracteres).")
        print("Estado normalizado: sin prefijo/sufijo 'DOTACION'.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
