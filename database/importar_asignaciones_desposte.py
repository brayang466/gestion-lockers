"""
Importa ASIGNACIONES DESPOSTE.csv al módulo Registro de Asignaciones.

Reglas:
- Solo se importan registros del contexto DESPOSTE (DES, CAL, LYD, SST, MTTO, LOG, EXT, TIC).
- Se eliminan antes los registros existentes de esas áreas en registro_asignaciones.
- El campo `area` conserva la subárea del CSV (DES/CAL/LYD/...) para poder filtrar por ubicación.
- Para visualización, la app muestra "(ubic. Desposte)" en subáreas distintas de DES.

Ejecutar desde raíz del proyecto:
  python database/importar_asignaciones_desposte.py
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
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y %H:%M:%S"):
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
    from app.models import RegistroAsignaciones

    csv_path = raiz / "datos_importar" / "ASIGNACIONES DESPOSTE.csv"
    if not csv_path.exists():
        print(f"No se encontró {csv_path}")
        sys.exit(1)

    rows = []
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            operario = (row.get("Operario") or "").strip()
            identificacion = (row.get("identificacion") or row.get("Identificacion") or "").strip()
            codigo_lockets = (row.get("Codigo de Lockets") or "").strip()
            codigo_dotacion = (row.get("Codigo de Dotacion") or "").strip()
            area = normalize_area(row.get("Area"))
            if area not in DESPOSTE_AREAS:
                continue
            if not any([operario, identificacion, codigo_lockets, codigo_dotacion]):
                continue

            fecha_entrega = parse_fecha(row.get("Fecha de Entrega"))
            rows.append(
                {
                    "id_asignaciones": (row.get("ID asignaciones") or "").strip(),
                    "codigo_dotacion": codigo_dotacion,
                    "fecha_asignacion": fecha_entrega,
                    "fecha_entrega": fecha_entrega,
                    "operario": operario,
                    "codigo_lockets": codigo_lockets,
                    "identificacion": identificacion,
                    "area": area,
                    "talla_operarios": (row.get("Talla de Operarios") or "").strip(),
                    "talla_dotacion": (row.get("Talla de dotacion asignada") or "").strip(),
                    "area_lockers": (row.get("Area de Lockers") or "").strip(),
                    "observaciones": (row.get("Observaciones") or "").strip(),
                }
            )

    app = create_app()
    with app.app_context():
        deleted = (
            RegistroAsignaciones.query.filter(RegistroAsignaciones.es_planta_desposte.is_(True)).delete(
                synchronize_session=False
            )
        )
        db.session.commit()
        print(f"Eliminados {deleted} registros previos de asignaciones DESPOSTE/subáreas.")

        for r in rows:
            db.session.add(
                RegistroAsignaciones(
                    id_asignaciones=r["id_asignaciones"],
                    codigo_dotacion=r["codigo_dotacion"],
                    fecha_asignacion=r["fecha_asignacion"],
                    fecha_entrega=r["fecha_entrega"],
                    operario=r["operario"],
                    codigo_lockets=r["codigo_lockets"],
                    identificacion=r["identificacion"],
                    area=r["area"],
                    talla_operarios=r["talla_operarios"],
                    talla_dotacion=r["talla_dotacion"],
                    area_lockers=r["area_lockers"],
                    estado="ACTIVO",
                    observaciones=r["observaciones"],
                    es_planta_desposte=True,
                )
            )
        db.session.commit()
        print(f"Importados {len(rows)} registros desde ASIGNACIONES DESPOSTE.csv.")


if __name__ == "__main__":
    main()
