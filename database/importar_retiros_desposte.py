"""
Importa RETIROS DESPOSTE.csv al módulo Historial de Retiros.

Reglas:
- Solo se importan registros del contexto DESPOSTE (DES, CAL, LYD, SST, MTTO, LOG, EXT, TIC).
- Se eliminan antes los registros existentes de esas áreas en historial_retiros.
- El campo `area` conserva la subárea del CSV para filtrar y visualizar ubicación.

Ejecutar desde raíz:
  python database/importar_retiros_desposte.py
"""
import csv
import os
import sys
from datetime import datetime
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

DESPOSTE_AREAS = {"DESPOSTE", "DES", "CAL", "LYD", "SST", "MTTO", "LOG", "EXT", "TIC"}


def parse_fecha(s):
    s = (s or "").strip()
    if not s:
        return datetime.utcnow()
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    try:
        d, m, y = [p.strip() for p in s.split("/")]
        if len(y) == 2:
            y = "20" + y
        return datetime(int(y), int(m), int(d))
    except Exception:
        return datetime.utcnow()


def normalize_area(raw):
    a = (raw or "").strip().upper()
    if not a:
        return "DES"
    if a == "DESPOSTE":
        return "DES"
    return a


def main():
    from app import create_app, db
    from app.models import HistorialRetiros

    csv_path = raiz / "datos_importar" / "RETIROS DESPOSTE.csv"
    if not csv_path.exists():
        print(f"No se encontró {csv_path}")
        sys.exit(1)

    rows = []
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            area = normalize_area(row.get("Area"))
            if area not in DESPOSTE_AREAS:
                continue
            operario = (row.get("Operario") or "").strip()
            identificacion = (row.get("identificacion") or row.get("Identificacion") or "").strip()
            codigo_lockets = (row.get("Codigo de Lockets") or "").strip()
            codigo_dotacion = (row.get("Codigo de Dotacion") or "").strip()
            if not any([operario, identificacion, codigo_lockets, codigo_dotacion]):
                continue
            rows.append(
                {
                    "identificacion": identificacion,
                    "codigo_dotacion": codigo_dotacion,
                    "fecha_retiro": parse_fecha(row.get("Fecha de Retiro")),
                    "operario": operario,
                    "codigo_lockets": codigo_lockets,
                    "area": area,
                    "talla_operarios": (row.get("Talla de Operarios") or "").strip(),
                    "talla_dotacion": (row.get("Talla de dotacion asignada") or "").strip(),
                    "area_lockers": (row.get("Area de Lockers") or "").strip(),
                    "es_planta_desposte": True,
                }
            )

    app = create_app()
    with app.app_context():
        deleted = HistorialRetiros.query.filter(HistorialRetiros.es_planta_desposte.is_(True)).delete(
            synchronize_session=False
        )
        db.session.commit()
        print(f"Eliminados {deleted} retiros previos de DESPOSTE/subáreas.")

        for r in rows:
            db.session.add(HistorialRetiros(**r))
        db.session.commit()
        print(f"Importados {len(rows)} retiros desde RETIROS DESPOSTE.csv.")


if __name__ == "__main__":
    main()
