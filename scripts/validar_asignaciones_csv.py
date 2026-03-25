"""
Valida datos_importar/ASIGNACIONES.csv (áreas generales; sin lote Desposte).

Comprueba cabeceras, filas vacías, que no figure el área literal DESPOSTE,
fechas, filas sin locker ni dotación, IDs duplicados y (si hay BD) códigos
en base_lockers y base_dotaciones excluyendo area_uso=DESPOSTE en dotaciones.

Uso (desde la raíz del proyecto):
  python scripts/validar_asignaciones_csv.py
  python scripts/validar_asignaciones_csv.py --csv datos_importar/ASIGNACIONES.csv --no-db
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SCRIPTS_DIR))

# Área de trabajo Desposte (sesión agregada): no debe aparecer en este CSV.
AREA_DESPOSTE_LITERAL = "DESPOSTE"

# Códigos de área habituales en exportaciones (menú + negocio); no incluye DESPOSTE literal.
AREAS_REFERENCIA = frozenset(
    s.upper()
    for s in (
        "BENEFICIO",
        "CALIDAD",
        "LYD",
        "PCC",
        "LOGISTICA",
        "TIC",
        "ASUR",
        "LN",
        "LOG",
        "MUJ",
        "CAL",
        "ADM",
        "EXT",
        "MTTO",
        "SST",
        "SEG",
        "DES",
    )
)

# Mismos códigos que en planta Desposte (import aparte). Si solo usas CSV general, revisa duplicidad con ASIGNACIONES DESPOSTE.csv.
CODIGOS_AMBOS_AMBITOS = frozenset({"DES", "CAL", "LYD", "SST", "MTTO", "LOG", "EXT", "TIC"})


def normalizar(h: str) -> str:
    return (h or "").strip().lower()


def find_idx(row, names):
    for i, x in enumerate(row):
        if normalizar(x) in names:
            return i
    return None


def safe(row, i, default=""):
    return str(row[i]).strip() if i is not None and len(row) > i else default


def load_csv_rows(path: Path):
    import csv

    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.reader(f))


# Misma configuración que scripts/import_datos.import_registro_asignaciones
DATE_FMT = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y"]


def parse_fecha(t):
    from datetime import datetime

    if not t or not str(t).strip():
        return None
    for f in DATE_FMT:
        try:
            return datetime.strptime(str(t).strip(), f)
        except ValueError:
            continue
    return None


COLS = [
    (("id asignaciones",), "id_asignaciones"),
    (("codigo de dotacion",), "codigo_dotacion"),
    (("fecha de entrega",), "fecha_entrega"),
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


def build_idx(header_row):
    idx = {}
    for headers, attr in COLS:
        i = find_idx(header_row, headers)
        if i is not None:
            idx[attr] = i
    return idx


def row_is_empty(data: dict) -> bool:
    keys = ("operario", "identificacion", "codigo_lockets", "codigo_dotacion", "area")
    return not any((data.get(k) or "").strip() for k in keys)


def main():
    try:
        from dotenv import load_dotenv

        load_dotenv(PROJECT_ROOT / ".env")
    except ImportError:
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", type=Path, default=PROJECT_ROOT / "datos_importar" / "ASIGNACIONES.csv")
    ap.add_argument("--no-db", action="store_true", help="Solo validación de archivo (sin MySQL)")
    args = ap.parse_args()

    if not args.csv.exists():
        print(f"No existe: {args.csv}")
        return 2

    rows = load_csv_rows(args.csv)
    if len(rows) < 2:
        print("CSV sin datos.")
        return 2

    header = rows[0]
    idx = build_idx(header)
    required = ("operario", "codigo de lockets", "codigo de dotacion", "area", "fecha de entrega")
    missing = [h for h in required if find_idx(header, (h,)) is None]
    if missing:
        print("ERROR: Faltan columnas obligatorias (cabeceras):", ", ".join(missing))
        return 1

    id_counts = Counter()
    areas = Counter()
    errores = []
    advertencias = []
    areas_desconocidas = Counter()
    filas_codigo_tambien_desposte = 0
    vacias = 0
    sin_locker_ni_dot = 0
    fechas_malas = 0
    filas_datos = 0

    for line_no, row in enumerate(rows[1:], start=2):
        data = {attr: safe(row, idx.get(attr)) for attr in [a for _, a in COLS]}
        if row_is_empty(data):
            vacias += 1
            continue
        filas_datos += 1

        area_u = (data.get("area") or "").strip().upper()
        if area_u == AREA_DESPOSTE_LITERAL:
            errores.append(f"Línea {line_no}: Area='DESPOSTE'. Este CSV es solo áreas generales; Desposte va en otro archivo/proceso.")

        if area_u in CODIGOS_AMBOS_AMBITOS:
            filas_codigo_tambien_desposte += 1

        if area_u and area_u not in AREAS_REFERENCIA:
            areas_desconocidas[area_u] += 1

        fid = (data.get("id_asignaciones") or "").strip()
        if fid:
            id_counts[fid] += 1

        cd = (data.get("codigo_dotacion") or "").strip()
        cl = (data.get("codigo_lockets") or "").strip()
        if not cd and not cl:
            sin_locker_ni_dot += 1

        fe = (data.get("fecha_entrega") or "").strip()
        if fe and parse_fecha(fe) is None:
            fechas_malas += 1

        if area_u:
            areas[area_u] += 1

    dup_ids = [k for k, v in id_counts.items() if v > 1]
    if dup_ids:
        advertencias.append(
            f"IDs de asignación repetidos en CSV ({len(dup_ids)} id(s) con más de una fila); al crear en la app se usa formato ASG-xxx."
        )

    if areas_desconocidas:
        advertencias.append(
            "Áreas no listadas en referencia: "
            + ", ".join(f"{a} ({n} filas)" for a, n in sorted(areas_desconocidas.items(), key=lambda x: -x[1]))
        )
    if filas_codigo_tambien_desposte:
        advertencias.append(
            f"Filas con Area en códigos también usados en planta Desposte ({filas_codigo_tambien_desposte}): "
            "si son solo Desposte, conviene `ASIGNACIONES DESPOSTE.csv` + importar_asignaciones_desposte.py; "
            "este CSV es para el resto de áreas / visión general."
        )
    if sin_locker_ni_dot:
        advertencias.append(
            f"{sin_locker_ni_dot} fila(s) sin código de dotación ni locker (no cuentan como asignación completa en el módulo)."
        )
    if fechas_malas:
        advertencias.append(f"{fechas_malas} fecha(s) de entrega no reconocidas (revisar formato).")

    print(f"Archivo: {args.csv}")
    print(f"Filas de datos (no vacías): {filas_datos} | Filas vacías omitidas: {vacias}")
    print(f"Áreas distintas (columna Area): {', '.join(sorted(areas)) or '—'}")
    print(f"Filas sin locker ni dotación: {sin_locker_ni_dot}")
    print(f"Fechas no parseables: {fechas_malas}")

    db_ok = False
    if not args.no_db:
        try:
            from app import create_app, db
            from app.models import BaseLockers, BaseDotaciones

            app = create_app()
            with app.app_context():
                lock_codes = {r[0] for r in BaseLockers.query.with_entities(BaseLockers.codigo).all() if r[0]}
                dot_rows = BaseDotaciones.query.with_entities(BaseDotaciones.codigo, BaseDotaciones.area_uso).all()
                dot_no_desposte = {
                    (c or "").strip()
                    for c, au in dot_rows
                    if c and (au or "").strip().upper() != AREA_DESPOSTE_LITERAL
                }
                dot_todos = {(c or "").strip() for c, _ in dot_rows if c}

                missing_l, missing_d = 0, 0
                solo_desposte_dot = 0
                for line_no, row in enumerate(rows[1:], start=2):
                    data = {attr: safe(row, idx.get(attr)) for attr in [a for _, a in COLS]}
                    if row_is_empty(data):
                        continue
                    cl = (data.get("codigo_lockets") or "").strip()
                    cd = (data.get("codigo_dotacion") or "").strip()
                    if cl and cl not in lock_codes:
                        missing_l += 1
                    if cd:
                        if cd not in dot_todos:
                            missing_d += 1
                        elif cd not in dot_no_desposte:
                            solo_desposte_dot += 1
                print(f"BD: códigos locker ausentes en base_lockers: {missing_l}")
                print(f"BD: códigos dotación ausentes en base_dotaciones: {missing_d}")
                print(f"BD: dotaciones solo registradas como area_uso=DESPOSTE (revisar vs áreas generales): {solo_desposte_dot}")
                if missing_l or missing_d or solo_desposte_dot:
                    advertencias.append(
                        f"BD: lockers faltantes={missing_l}, dotaciones faltantes={missing_d}, "
                        f"dotación solo DESPOSTE={solo_desposte_dot}."
                    )
                db_ok = True
        except Exception as e:
            print(f"BD: no se pudo validar ({e}). Usa --no-db para solo CSV.")

    if errores:
        print("\n--- ERRORES ---")
        for e in errores[:50]:
            print(e)
        if len(errores) > 50:
            print(f"... y {len(errores) - 50} más")
        return 1

    if advertencias:
        print("\n--- ADVERTENCIAS (muestra) ---")
        for a in advertencias[:40]:
            print(a)
        if len(advertencias) > 40:
            print(f"... total advertencias: {len(advertencias)}")

    print("\nOK: sin errores bloqueantes" + ("; revisa advertencias." if advertencias else "."))
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
