"""
Importa dotaciones exclusivas del área DESPOSTE desde datos_importar/DOTACION DESPOSTE.csv.
- Elimina de base_dotaciones todos los registros con area_uso = 'DESPOSTE'.
- Inserta los registros del CSV con area_uso = 'DESPOSTE' (no se agregan a otras áreas).
- Mismo orden que otras áreas: códigos numéricos primero (001, 002, ...), luego con letra.
- Estado normalizado: DOTACION DISPONIBLE -> DISPONIBLE, DOTACION ASIGNADA -> ASIGNADA,
  NO HAY ESE CODIGO -> NO EXISTE.

Columnas CSV esperadas: Cantidad, Codigo de Dotacion, Area de USO, Talla, ESTADO.
El área en el CSV se ignora; siempre se asigna area_uso = 'DESPOSTE'.

Ejecutar desde la raíz del proyecto: python database/importar_dotacion_desposte.py
"""
import csv
import re
import os
import sys
from pathlib import Path

raiz = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(raiz))

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
    """Misma lógica que _normalize_estado_base_dotaciones: NO HAY ESE CODIGO -> NO EXISTE; quita DOTACION."""
    if not estado or not isinstance(estado, str):
        return "DISPONIBLE"
    s = estado.strip()
    if re.search(r"no\s*hay\s*ese\s*codigo", s, re.IGNORECASE):
        return "NO EXISTE"
    s = re.sub(r"^DOTACION\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s*DOTACION\s*$", "", s, flags=re.IGNORECASE).strip()
    if not s:
        return "DISPONIBLE"
    u = s.upper()
    if u in ("ASIGNADA", "DISPONIBLE", "NO EXISTE"):
        return u
    return s


def codigo_sort_key(codigo):
    """Orden: numéricos primero (001, 002, ...), luego los que inician con letra."""
    c = (codigo or "").strip()
    if not c:
        return (1, 0, "")
    if c.isdigit():
        return (0, int(c), "")
    return (1, 0, c)


def main():
    from app import create_app, db
    from app.models import BaseDotaciones

    csv_path = raiz / "datos_importar" / "DOTACION DESPOSTE.csv"
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
            if codigo[0].isalpha() and len(codigo) > 5:
                codigo = codigo[:5]
            cantidad_raw = row.get("Cantidad") or row.get("cantidad") or "0"
            try:
                cantidad = int(cantidad_raw)
            except (TypeError, ValueError):
                cantidad = None
            talla = (row.get("Talla") or row.get("talla") or "").strip()
            estado = normalize_estado(row.get("ESTADO") or row.get("Estado") or row.get("estado") or "")
            rows.append({
                "codigo": codigo,
                "cantidad": cantidad,
                "talla": talla,
                "estado": estado,
            })

    rows.sort(key=lambda r: codigo_sort_key(r["codigo"]))

    app = create_app()
    with app.app_context():
        deleted = BaseDotaciones.query.filter(BaseDotaciones.area_uso == "DESPOSTE").delete()
        db.session.commit()
        print(f"Eliminados {deleted} registros previos con area_uso = DESPOSTE.")

        for r in rows:
            obj = BaseDotaciones(
                codigo=r["codigo"],
                cantidad=r["cantidad"],
                talla=r["talla"],
                estado=r["estado"],
                area_uso="DESPOSTE",
            )
            db.session.add(obj)
        db.session.commit()
        print(f"Importados {len(rows)} registros desde DOTACION DESPOSTE.csv para el área DESPOSTE.")
        print("Estado normalizado: DISPONIBLE / ASIGNADA / NO EXISTE.")


if __name__ == "__main__":
    main()
