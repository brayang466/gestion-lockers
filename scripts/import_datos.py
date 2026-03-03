"""
Importar CSV a las tablas (cabeceras según tus hojas).
Uso: python scripts/import_datos.py archivo.csv -t base_lockers [--replace]
INGRESO DE LOCKERS e INGRESO DE DOTACION no se importan desde CSV (son para registro manual).
"""
import argparse, csv, sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")
from app import create_app, db
from app.models import (
    RegistroPersonal, RegistroAsignaciones, DotacionesDisponibles,
    PersonalPresupuestado, LockerDisponibles, HistorialRetiros,
    BaseLockers, BaseDotaciones,
)

def normalizar(h):
    return (h or "").strip().lower()
def find_idx(row, names):
    for i, x in enumerate(row):
        if normalizar(x) in names:
            return i
    return None
def safe(row, i, default=""):
    return (str(row[i]).strip() if i is not None and len(row) > i else default)
DATE_FMT = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y"]
def parse_fecha(t):
    if not t or not str(t).strip():
        return None
    for f in DATE_FMT:
        try:
            return datetime.strptime(str(t).strip(), f)
        except ValueError:
            continue
    return None

def _import(rows, replace, app, Model, config, label):
    with app.app_context():
        if replace:
            Model.query.delete()
            db.session.commit()
        first = rows[0]
        idx = {}
        for headers, attr, *opt in config:
            i = find_idx(first, headers)
            if i is not None:
                idx[attr] = (i, opt[0] if opt else None)
        imp, skip = 0, 0
        for row in rows[1:]:
            data = {}
            for attr, (i, opt) in idx.items():
                v = safe(row, i)
                if opt == "date":
                    v = parse_fecha(v) if v else None
                elif opt == "int":
                    try:
                        v = int(float(v)) if v else None
                    except (ValueError, TypeError):
                        v = None
                data[attr] = v
            try:
                db.session.add(Model(**data))
                imp += 1
            except Exception:
                skip += 1
        db.session.commit()
        print(f"{label}: importados {imp}, omitidos {skip}.")
        return True

# REGISTRO DE PERSONAL: ID PERSONAL, Operario, identificacion, Area, Talla, Area de Lockers, estado
def import_registro_personal(r, rep, app):
    c = [
        (("id personal",), "id_personal"),
        (("operario",), "nombre"),
        (("identificacion",), "documento"),
        (("area",), "area"),
        (("talla",), "talla"),
        (("area de lockers",), "area_lockers"),
        (("estado",), "estado"),
    ]
    return _import(r, rep, app, RegistroPersonal, c, "registro_personal")

# REGISTRO DE ASIGNACIONES: ID asignaciones, Codigo de Dotacion, Fecha de Entrega, Operario, Codigo de Lockets, identificacion, Codigo de Seca Botas, Area, Talla de Operarios, Talla de dotacion asignada, Area de Lockers, Observaciones
def import_registro_asignaciones(r, rep, app):
    c = [
        (("id asignaciones",), "id_asignaciones"),
        (("codigo de dotacion",), "codigo_dotacion"),
        (("fecha de entrega",), "fecha_entrega", "date"),
        (("operario",), "operario"),
        (("codigo de lockets",), "codigo_lockets"),
        (("identificacion",), "identificacion"),
        (("codigo de seca botas",), "codigo_seca_botas"),
        (("area",), "area"),
        (("talla de operarios",), "talla_operarios"),
        (("talla de dotacion asignada",), "talla_dotacion"),
        (("area de lockers",), "area_lockers"),
        (("observaciones",), "observaciones"),
    ]
    with app.app_context():
        if rep:
            RegistroAsignaciones.query.delete()
            db.session.commit()
        first = r[0]
        idx = {}
        for headers, attr, *opt in c:
            i = find_idx(first, headers)
            if i is not None:
                idx[attr] = (i, opt[0] if opt else None)
        imp, skip = 0, 0
        for row in r[1:]:
            data = {}
            for attr, (i, opt) in idx.items():
                v = safe(row, i)
                if opt == "date":
                    v = parse_fecha(v) if v else None
                data[attr] = v
            if data.get("fecha_entrega"):
                data["fecha_asignacion"] = data["fecha_entrega"]
            else:
                data["fecha_asignacion"] = datetime.utcnow()
            try:
                db.session.add(RegistroAsignaciones(**data))
                imp += 1
            except Exception:
                skip += 1
        db.session.commit()
        print(f"registro_asignaciones: importados {imp}, omitidos {skip}.")
        return True

# DOTACIONES DISPONIBLES: CODIGO DE DOTACION, TALLA, CANTIDAD
def import_dotaciones_disponibles(r, rep, app):
    c = [
        (("codigo de dotacion", "codigo"), "codigo"),
        (("talla",), "talla"),
        (("cantidad",), "cantidad", "int"),
    ]
    return _import(r, rep, app, DotacionesDisponibles, c, "dotaciones_disponibles")

# PERSONAL PRESUPUESTADO: AREA, APROBADOS, CONTRATADOS, POR CONTRATAR
def import_personal_presupuestado(r, rep, app):
    c = [
        (("area",), "area"),
        (("aprobados",), "aprobados", "int"),
        (("contratados",), "contratados", "int"),
        (("por contratar",), "por_contratar", "int"),
    ]
    return _import(r, rep, app, PersonalPresupuestado, c, "personal_presupuestado")

# LOCKER DISPONIBLES: # LOCKER, AREA, AREAS DE LOCKER
def import_locker_disponibles(r, rep, app):
    c = [
        (("# locker", "numero locker", "codigo"), "codigo"),
        (("area",), "area"),
        (("areas de locker", "area de lockers"), "area_lockers"),
    ]
    return _import(r, rep, app, LockerDisponibles, c, "locker_disponibles")

# HISTORIAL DE RETIROS: ID RETIRO, identificacion, Codigo de Dotacion, Fecha de Retiro, Operario, Codigo de Lockets, Area, Talla de Operarios, Talla de dotacion asignada, Area de Lockers, Observaciones
def import_historial_retiros(r, rep, app):
    c = [
        (("id retiro",), "id_retiro"),
        (("identificacion",), "identificacion"),
        (("codigo de dotacion",), "codigo_dotacion"),
        (("fecha de retiro", "fecha retiro"), "fecha_retiro", "date"),
        (("operario",), "operario"),
        (("codigo de lockets",), "codigo_lockets"),
        (("area",), "area"),
        (("talla de operarios",), "talla_operarios"),
        (("talla de dotacion asignada",), "talla_dotacion"),
        (("area de lockers",), "area_lockers"),
        (("observaciones",), "observaciones"),
    ]
    return _import(r, rep, app, HistorialRetiros, c, "historial_retiros")

# BASE DE LOCKERS: Codigo de Lockets, Area, Area de Lockers, ESTADO, UNIDAD
def import_base_lockers(r, rep, app):
    c = [
        (("codigo de lockets", "codigo"), "codigo"),
        (("area",), "area"),
        (("area de lockers",), "area_lockers"),
        (("estado",), "estado"),
        (("unidad",), "unidad"),
    ]
    return _import(r, rep, app, BaseLockers, c, "base_lockers")

# BASE DE DOTACIONES: Cantidad, Codigo de Dotacion, Area de USO, Talla, ESTADO
def import_base_dotaciones(r, rep, app):
    c = [
        (("cantidad",), "cantidad", "int"),
        (("codigo de dotacion", "codigo"), "codigo"),
        (("area de uso", "area de uso"), "area_uso"),
        (("talla",), "talla"),
        (("estado",), "estado"),
    ]
    return _import(r, rep, app, BaseDotaciones, c, "base_dotaciones")

IMPORTERS = {
    "registro_personal": import_registro_personal,
    "registro_asignaciones": import_registro_asignaciones,
    "dotaciones_disponibles": import_dotaciones_disponibles,
    "personal_presupuestado": import_personal_presupuestado,
    "locker_disponibles": import_locker_disponibles,
    "historial_retiros": import_historial_retiros,
    "base_lockers": import_base_lockers,
    "base_dotaciones": import_base_dotaciones,
}

def load_csv(path):
    p = Path(path)
    if not p.exists():
        return None
    with open(p, newline="", encoding="utf-8-sig") as f:
        return list(csv.reader(f))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_file", nargs="?")
    parser.add_argument("--table", "-t", choices=list(IMPORTERS), default="base_lockers")
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()
    if not args.csv_file:
        print("Uso: python scripts/import_datos.py archivo.csv -t nombre_tabla")
        print("Tablas (sin ingreso_lockers/ingreso_dotacion):", ", ".join(IMPORTERS))
        sys.exit(1)
    rows = load_csv(args.csv_file)
    if not rows or len(rows) < 2:
        print("Archivo vacío o sin datos.")
        sys.exit(1)
    app = create_app()
    ok = IMPORTERS[args.table](rows, args.replace, app)
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
