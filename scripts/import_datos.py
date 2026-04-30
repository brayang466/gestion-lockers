"""
Importar CSV a las tablas (cabeceras según tus hojas).
Uso: python scripts/import_datos.py archivo.csv -t base_lockers [--replace]
INGRESO DE LOCKERS e INGRESO DE DOTACION no se importan desde CSV (son para registro manual).
"""
import argparse, csv, sys, re
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
    BaseLockers, BaseDotaciones, SecaBotasDisponibles,
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


def _normalize_area_registro_asignaciones_csv(area_raw):
    """CSV general: códigos cortos al nombre usado en sesión / area_trabajo (como scripts/actualizar_areas)."""
    if area_raw is None:
        return None
    s = str(area_raw).strip()
    if not s:
        return s
    u = s.upper()
    if u == "LN":
        return "BENEFICIO"
    if u == "LOG":
        return "LOGISTICA"
    if u == "CAL":
        return "CALIDAD"
    return s


def _normalize_area_general(area_raw):
    """Normaliza códigos de área al nombre de sesión (LN→BENEFICIO, LOG→LOGISTICA, CAL→CALIDAD)."""
    if area_raw is None:
        return ""
    s = str(area_raw).strip()
    if not s:
        return ""
    u = s.upper()
    if u == "LN":
        return "BENEFICIO"
    if u == "LOG":
        return "LOGISTICA"
    if u == "CAL":
        return "CALIDAD"
    return u


def _normalize_estado_locker(estado_raw):
    """Normaliza estado lockers a: disponible / asignado / visita."""
    s = (estado_raw or "").strip()
    if not s:
        return "disponible"
    s = re.sub(r"^LOCKERT\s*", "", s, flags=re.IGNORECASE).strip()
    if not s:
        return "disponible"
    u = s.upper()
    if u == "ASIGNADA":
        u = "ASIGNADO"
    if u in ("DISPONIBLE", "ASIGNADO", "VISITA"):
        return u.lower()
    # heurística
    if "DISP" in u:
        return "disponible"
    if "VIS" in u:
        return "visita"
    if "ASIG" in u:
        return "asignado"
    return s.lower()


def _sync_locker_disponibles_from_base_lockers(app):
    """Recrea locker_disponibles (áreas generales) desde base_lockers en estado disponible. Omite DESPOSTE.

    Regla de negocio (áreas generales): DISPONIBLE en BaseLockers => visible en LockerDisponibles.
    No descuenta por asignaciones; Desposte se gestiona aparte.
    """
    with app.app_context():
        # Borrar solo áreas generales (DESPOSTE se maneja en database/importar_lockers_desposte.py)
        LockerDisponibles.query.filter(db.func.upper(db.func.trim(LockerDisponibles.area)) != "DESPOSTE").delete(
            synchronize_session=False
        )
        db.session.commit()
        q = BaseLockers.query.filter(
            db.func.upper(db.func.trim(BaseLockers.area)) != "DESPOSTE",
            db.func.lower(db.func.trim(BaseLockers.estado)) == "disponible",
        )
        added = 0
        for bl in q.all():
            cod = (bl.codigo or "").strip()
            if not cod:
                continue
            db.session.add(
                LockerDisponibles(
                    codigo=cod,
                    area=(bl.area or "").strip(),
                    subarea="",  # subárea aplica a DESPOSTE
                    area_lockers=(bl.area_lockers or "").strip(),
                    estado="disponible",
                    observaciones=(bl.observaciones or None),
                )
            )
            added += 1
        db.session.commit()
        print(f"locker_disponibles(sync): recreados {added} desde base_lockers (sin DESPOSTE).")


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

# REGISTRO DE ASIGNACIONES — CSV típico: todas las áreas excepto Desposte (Desposte va en otros CSV).
# Columnas: ID asignaciones, Codigo de Dotacion, Fecha de Entrega, Operario, Codigo de Lockets, identificacion,
# Codigo de Seca Botas, Area, Talla de Operarios, Talla de dotacion asignada, Area de Lockers, Observaciones.
# Área en CSV: LN→BENEFICIO, LOG→LOGISTICA, CAL→CALIDAD (plant Desposte usa otros CSV con códigos cortos).
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
            # No borrar filas de planta Desposte (ASIGNACIONES DESPOSTE.csv); solo el CSV general.
            RegistroAsignaciones.query.filter(RegistroAsignaciones.es_planta_desposte.is_(False)).delete(
                synchronize_session=False
            )
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
            # Fila vacía (solo separadores en Excel): no importar
            if not any(
                (data.get(k) or "").strip()
                for k in ("operario", "identificacion", "codigo_lockets", "codigo_dotacion", "area")
            ):
                skip += 1
                continue
            if data.get("fecha_entrega"):
                data["fecha_asignacion"] = data["fecha_entrega"]
            else:
                data["fecha_asignacion"] = datetime.utcnow()
            if "area" in data:
                data["area"] = _normalize_area_registro_asignaciones_csv(data.get("area"))
            data["es_planta_desposte"] = False
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
    """
    Importa el CSV de dotaciones disponibles (ej. "DOT DISP.csv") al origen usado por el módulo:
    `BaseDotaciones` con `estado=DISPONIBLE` para áreas generales (NO toca DESPOSTE).
    """
    c = [
        (("codigo de dotacion", "codigo"), "codigo"),
        (("talla",), "talla"),
        (("cantidad",), "cantidad", "int"),
    ]
    with app.app_context():
        if rep:
            # Solo refresca el "pool" disponible general, sin tocar DESPOSTE ni ASIGNADAS.
            BaseDotaciones.query.filter(BaseDotaciones.area_uso != "DESPOSTE").filter(
                db.func.lower(BaseDotaciones.estado) == "disponible"
            ).delete(synchronize_session=False)
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
                if opt == "int":
                    try:
                        v = int(float((v or "").strip())) if (v or "").strip() else None
                    except Exception:
                        v = None
                data[attr] = v
            codigo = (data.get("codigo") or "").strip()
            if not codigo:
                skip += 1
                continue
            talla = (data.get("talla") or "").strip().upper()
            cantidad = data.get("cantidad")
            try:
                db.session.add(
                    BaseDotaciones(
                        codigo=codigo,
                        talla=talla,
                        cantidad=cantidad,
                        area_uso="",  # General (≠ DESPOSTE)
                        estado="DISPONIBLE",
                    )
                )
                imp += 1
            except Exception:
                skip += 1
        db.session.commit()
        print(f"dotaciones_disponibles: importados {imp}, omitidos {skip}.")
        return True

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
        (("subarea", "subárea", "sub área"), "subarea"),
        (("areas de locker", "area de lockers"), "area_lockers"),
        (("estado",), "estado"),
        (("observaciones",), "observaciones"),
    ]
    with app.app_context():
        if rep:
            # No borrar lockers de planta Desposte; se cargan con database/importar_lockers_desposte.py
            LockerDisponibles.query.filter(db.func.upper(db.func.trim(LockerDisponibles.area)) != "DESPOSTE").delete(
                synchronize_session=False
            )
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
                data[attr] = v
            codigo = (data.get("codigo") or "").strip()
            if not codigo:
                skip += 1
                continue
            area_u = (data.get("area") or "").strip().upper()
            if area_u == "DESPOSTE":
                # Este CSV es para áreas generales; Desposte va aparte
                skip += 1
                continue
            data["codigo"] = codigo
            data["area"] = (data.get("area") or "").strip()
            data["subarea"] = (data.get("subarea") or "").strip() if "subarea" in data else ""
            data["area_lockers"] = (data.get("area_lockers") or "").strip()
            if "estado" in data and data.get("estado") is not None:
                data["estado"] = (data.get("estado") or "").strip() or "disponible"
            if "observaciones" in data and data.get("observaciones") is not None:
                data["observaciones"] = (data.get("observaciones") or "").strip()
            try:
                db.session.add(LockerDisponibles(**data))
                imp += 1
            except Exception:
                skip += 1
        db.session.commit()
        print(f"locker_disponibles: importados {imp}, omitidos {skip}.")
        return True

# HISTORIAL DE RETIROS: ID RETIRO, identificacion, Codigo de Dotacion, Fecha de Retiro, Operario, Codigo de Lockets, Area, ...
def import_historial_retiros(r, rep, app):
    c = [
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
    with app.app_context():
        if rep:
            HistorialRetiros.query.filter(HistorialRetiros.es_planta_desposte.is_(False)).delete(
                synchronize_session=False
            )
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
            # Fila vacía (solo separadores en Excel): no importar
            if not any(
                (data.get(k) or "").strip()
                for k in ("operario", "identificacion", "codigo_lockets", "codigo_dotacion", "area")
            ):
                skip += 1
                continue
            # Omite filas explícitas de DESPOSTE (planta va en RETIROS DESPOSTE.csv)
            if (data.get("area") or "").strip().upper() == "DESPOSTE":
                skip += 1
                continue
            if "area" in data:
                data["area"] = _normalize_area_registro_asignaciones_csv(data.get("area"))
            # fecha_retiro es NOT NULL en BD: si falta, usar hoy (manteniendo import)
            if data.get("fecha_retiro") is None:
                data["fecha_retiro"] = datetime.utcnow()
            if "observaciones" in data and data.get("observaciones") is not None:
                data["observaciones"] = (data.get("observaciones") or "").strip().upper()
            data["es_planta_desposte"] = False
            try:
                db.session.add(HistorialRetiros(**data))
                imp += 1
            except Exception:
                skip += 1
        db.session.commit()
        print(f"historial_retiros: importados {imp}, omitidos {skip}.")
        return True

# BASE DE LOCKERS: Codigo de Lockets, Area, Area de Lockers, ESTADO, UNIDAD
def import_base_lockers(r, rep, app):
    c = [
        (("codigo de lockets", "codigo de lockers", "codigo", "código", "# locker", "numero locker", "número locker"), "codigo"),
        (("area", "área"), "area"),
        (("subarea", "subárea", "sub área"), "subarea"),
        (("area de lockers", "área de lockers", "areas de locker", "áreas de locker", "area lockers", "área lockers"), "area_lockers"),
        (("estado",), "estado"),
        (("unidad",), "unidad"),
        (("observaciones",), "observaciones"),
    ]
    with app.app_context():
        if rep:
            # Igual que asignaciones: actualizar solo áreas generales (no tocar DESPOSTE).
            BaseLockers.query.filter(db.func.upper(db.func.trim(BaseLockers.area)) != "DESPOSTE").delete(
                synchronize_session=False
            )
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
                data[attr] = safe(row, i)
            codigo = (data.get("codigo") or "").strip()
            if not codigo:
                skip += 1
                continue
            area_norm = _normalize_area_general(data.get("area"))
            if area_norm == "DESPOSTE":
                skip += 1
                continue
            estado_norm = _normalize_estado_locker(data.get("estado"))
            obj = BaseLockers(
                codigo=codigo,
                area=area_norm,
                subarea=(data.get("subarea") or "").strip(),
                area_lockers=(data.get("area_lockers") or "").strip(),
                estado=estado_norm,
                unidad=(data.get("unidad") or "").strip(),
                observaciones=(data.get("observaciones") or "").strip() if (data.get("observaciones") is not None) else None,
            )
            try:
                db.session.add(obj)
                imp += 1
            except Exception:
                skip += 1
        db.session.commit()
        print(f"base_lockers: importados {imp}, omitidos {skip}.")
        _sync_locker_disponibles_from_base_lockers(app)
        return True

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


# SECA BOTAS DISPONIBLES: CODIGO, AREA LOCKER, AREA, ESTADO
def import_seca_botas_disponibles(r, rep, app):
    def norm_estado(x: str) -> str:
        s = (x or "").strip().upper()
        if not s:
            return "DISPONIBLE"
        if s in ("DISPONIBLE", "ASIGNADO"):
            return s
        if s == "ASIGNADA":
            return "ASIGNADO"
        if "DISP" in s:
            return "DISPONIBLE"
        if "ASIG" in s:
            return "ASIGNADO"
        return "DISPONIBLE"

    c = [
        (("codigo de seca botas", "código de seca botas", "codigo", "código", "codigo seca botas", "código seca botas"), "codigo"),
        (("area de lockers", "área de lockers", "area locker", "área locker", "area de locker", "área de locker", "area lockers", "área lockers"), "area_locker"),
        (("area", "área"), "area"),
        (("estado",), "estado"),
        (("observaciones",), "observaciones"),
    ]
    with app.app_context():
        if rep:
            SecaBotasDisponibles.query.delete()
            db.session.commit()
        first = r[0]
        idx = {}
        for headers, attr, *opt in c:
            i = find_idx(first, headers)
            if i is not None:
                idx[attr] = (i, opt[0] if opt else None)
        imp, skip = 0, 0
        def split_codigo_y_area(raw: str) -> tuple[str, str]:
            t = (raw or "").strip()
            if not t:
                return "", ""
            parts = [p for p in t.split() if p]
            if len(parts) < 2:
                return t, ""
            code = parts[0].strip()
            area = parts[1].strip().upper()
            mapa = {
                "LN": "BENEFICIO",
                "LOG": "LOGISTICA",
            }
            return code, mapa.get(area, area)

        for row in r[1:]:
            data = {}
            for attr, (i, opt) in idx.items():
                v = safe(row, i)
                data[attr] = v
            raw_codigo = data.get("codigo", "")
            codigo, area_from_codigo = split_codigo_y_area(raw_codigo)
            if not codigo.strip():
                skip += 1
                continue
            estado_norm = norm_estado(data.get("estado", ""))
            data["codigo"] = codigo.strip()
            data["estado"] = estado_norm
            data["area"] = area_from_codigo or "SIN ASIGNAR"
            try:
                db.session.add(SecaBotasDisponibles(**data))
                imp += 1
            except Exception:
                skip += 1
        db.session.commit()
        print(f"seca_botas_disponibles: importados {imp}, omitidos {skip}.")
        return True


IMPORTERS = {
    "registro_personal": import_registro_personal,
    "registro_asignaciones": import_registro_asignaciones,
    "dotaciones_disponibles": import_dotaciones_disponibles,
    "personal_presupuestado": import_personal_presupuestado,
    "locker_disponibles": import_locker_disponibles,
    "historial_retiros": import_historial_retiros,
    "base_lockers": import_base_lockers,
    "base_dotaciones": import_base_dotaciones,
    "seca_botas_disponibles": import_seca_botas_disponibles,
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
