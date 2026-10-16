"""
Actualiza la BD local desde «GESTOR LOCKERS ACTUALIZADO.xlsx».

Hojas usadas (tal cual el pedido):
  - ASIGNACIONES          → registro_asignaciones
  - LOCKERES              → base_lockers
  - SECA BOTAS            → seca_botas_disponibles
  - DOTACIONES            → base_dotaciones
  - DOTACIONES DISPONIBLES→ (verificación / tabla auxiliar; el módulo lee BaseDotaciones DISPONIBLE)
  - LOCKER DISPONIBLES    → locker_disponibles
  - AREAS                 → crea área ADMINISTRATIVA (SST, TIC, ADM, EXT, PYP, GG, SEG, ASUR, MTTO)

NO importa: RETIROS, PERSONAL (ni otras hojas no listadas).
NO toca: historial_retiros, historial_cambios, ni filas de planta DESPOSTE.

Uso (desde la raíz del proyecto, con el venv activo):
  python scripts/actualizar_desde_excel_gestor_actualizado.py
  python scripts/actualizar_desde_excel_gestor_actualizado.py --excel "GESTOR LOCKERS ACTUALIZADO.xlsx"
  python scripts/actualizar_desde_excel_gestor_actualizado.py --sql-out database/sync_gestor_actualizado.sql
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SCRIPTS))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

try:
    import openpyxl
except ImportError:
    print("Falta openpyxl. Instala con: pip install openpyxl")
    sys.exit(1)

from app import create_app, db
from app.models import (
    AreaTrabajo,
    BaseDotaciones,
    BaseLockers,
    DotacionesDisponibles,
    HistorialRetiros,
    LockerDisponibles,
    RegistroAsignaciones,
    SecaBotasDisponibles,
)
from import_datos import (
    IMPORTERS,
    _normalize_area_general,
)

DEFAULT_EXCEL = PROJECT_ROOT / "GESTOR LOCKERS ACTUALIZADO.xlsx"

# Solo lo pedido (sin RETIROS ni PERSONAL).
HOJAS_A_IMPORTAR = [
    ("LOCKERES", "base_lockers"),
    ("DOTACIONES", "base_dotaciones"),
    ("SECA BOTAS", "seca_botas_disponibles"),
    ("ASIGNACIONES", "registro_asignaciones"),
    ("LOCKER DISPONIBLES", "locker_disponibles"),
]


def _cell_to_str(cell) -> str:
    if cell is None:
        return ""
    if isinstance(cell, datetime):
        return cell.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(cell, bool):
        return str(cell)
    if isinstance(cell, int):
        return str(cell)
    if isinstance(cell, float):
        if cell.is_integer():
            return str(int(cell))
        return str(cell)
    return str(cell).strip()


def _sheet_to_rows(ws) -> list[list[str]]:
    rows: list[list[str]] = []
    for row in ws.iter_rows(values_only=True):
        rows.append([_cell_to_str(c) for c in row])
    if not rows:
        return rows
    last = 0
    for i, h in enumerate(rows[0]):
        if (h or "").strip():
            last = i
    width = last + 1
    return [r[:width] for r in rows]


def _asegurar_area_administrativa(app) -> None:
    with app.app_context():
        db.create_all()
        existe = AreaTrabajo.query.filter(
            db.func.upper(AreaTrabajo.nombre) == "ADMINISTRATIVA"
        ).first()
        if not existe:
            db.session.add(AreaTrabajo(nombre="ADMINISTRATIVA"))
            db.session.commit()
            print("area_trabajo: creada ADMINISTRATIVA.")
        else:
            print("area_trabajo: ADMINISTRATIVA ya existía.")


def _sync_dotaciones_disponibles_tabla(rows: list[list[str]], app) -> int:
    """Rellena la tabla auxiliar dotaciones_disponibles desde la hoja (el módulo usa BaseDotaciones)."""
    if not rows or len(rows) < 2:
        return 0
    from import_datos import find_idx, safe

    hdr = rows[0]
    i_cod = find_idx(hdr, ("codigo de dotacion", "codigo"))
    i_talla = find_idx(hdr, ("talla",))
    i_cant = find_idx(hdr, ("cantidad", "cantidad "))
    with app.app_context():
        DotacionesDisponibles.query.delete()
        db.session.commit()
        n = 0
        for row in rows[1:]:
            codigo = safe(row, i_cod).strip()
            if not codigo:
                continue
            talla = safe(row, i_talla).strip().upper()
            cant_raw = safe(row, i_cant).strip()
            try:
                cantidad = int(float(cant_raw)) if cant_raw else 0
            except (TypeError, ValueError):
                cantidad = 0
            db.session.add(
                DotacionesDisponibles(codigo=codigo, talla=talla, cantidad=cantidad)
            )
            n += 1
        db.session.commit()
        print(f"dotaciones_disponibles(tabla auxiliar): {n} filas.")
        return n


def _validar(app, excel_counts: dict) -> bool:
    ok = True
    with app.app_context():
        pairs = [
            (
                "base_lockers (no DESPOSTE)",
                BaseLockers.query.filter(
                    db.func.upper(db.func.trim(BaseLockers.area)) != "DESPOSTE"
                ).count(),
                excel_counts.get("base_lockers"),
            ),
            (
                "base_dotaciones (no DESPOSTE)",
                BaseDotaciones.query.filter(
                    db.func.upper(db.func.trim(BaseDotaciones.area_uso)) != "DESPOSTE"
                ).count(),
                excel_counts.get("base_dotaciones"),
            ),
            (
                "seca_botas_disponibles",
                SecaBotasDisponibles.query.count(),
                excel_counts.get("seca_botas_disponibles"),
            ),
            (
                "registro_asignaciones (no desposte)",
                RegistroAsignaciones.query.filter(
                    RegistroAsignaciones.es_planta_desposte.is_(False)
                ).count(),
                excel_counts.get("registro_asignaciones"),
            ),
            (
                "locker_disponibles (no DESPOSTE)",
                LockerDisponibles.query.filter(
                    db.func.upper(db.func.trim(LockerDisponibles.area)) != "DESPOSTE"
                ).count(),
                excel_counts.get("locker_disponibles"),
            ),
            (
                "historial_retiros (intactos)",
                HistorialRetiros.query.filter(
                    HistorialRetiros.es_planta_desposte.is_(False)
                ).count(),
                excel_counts.get("historial_retiros_antes"),
            ),
            (
                "desposte asignaciones (intactos)",
                RegistroAsignaciones.query.filter(
                    RegistroAsignaciones.es_planta_desposte.is_(True)
                ).count(),
                excel_counts.get("desposte_asig_antes"),
            ),
            (
                "desposte lockers (intactos)",
                BaseLockers.query.filter(
                    db.func.upper(db.func.trim(BaseLockers.area)) == "DESPOSTE"
                ).count(),
                excel_counts.get("desposte_lock_antes"),
            ),
            (
                "ADMINISTRATIVA en asignaciones",
                RegistroAsignaciones.query.filter(
                    db.func.upper(db.func.trim(RegistroAsignaciones.area))
                    == "ADMINISTRATIVA"
                ).count(),
                None,
            ),
            (
                "ADMINISTRATIVA en lockers",
                BaseLockers.query.filter(
                    db.func.upper(db.func.trim(BaseLockers.area)) == "ADMINISTRATIVA"
                ).count(),
                None,
            ),
        ]
        print("\n=== Validación ===")
        for label, got, expected in pairs:
            if expected is None:
                print(f"  [i] {label}: BD={got}")
                continue
            mark = "OK" if got == expected else "DIFF"
            if mark == "DIFF":
                ok = False
            print(f"  [{mark}] {label}: BD={got} excel/antes={expected}")
    return ok


def _export_sql(out_path: Path) -> None:
    """Genera mysqldump de las tablas afectadas para aplicar en el servidor."""
    import os

    user = os.environ.get("MYSQL_USER", "root")
    password = os.environ.get("MYSQL_PASSWORD", "")
    host = os.environ.get("MYSQL_HOST", "127.0.0.1")
    port = os.environ.get("MYSQL_PORT", "3306")
    database = os.environ.get("MYSQL_DATABASE", "gestor_lockers")
    tables = [
        "area_trabajo",
        "registro_asignaciones",
        "base_lockers",
        "base_dotaciones",
        "seca_botas_disponibles",
        "locker_disponibles",
        "dotaciones_disponibles",
    ]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "mysqldump",
        f"-h{host}",
        f"-P{port}",
        f"-u{user}",
        f"-p{password}",
        "--routines=false",
        "--triggers=false",
        "--set-gtid-purged=OFF",
        "--column-statistics=0",
        database,
        *tables,
    ]
    try:
        with out_path.open("w", encoding="utf-8", newline="\n") as fh:
            fh.write(
                "-- Sync GESTOR LOCKERS ACTUALIZADO\n"
                "-- Tablas: " + ", ".join(tables) + "\n"
                "-- Aplicar en servidor: mysql -u USER -p DATABASE < "
                f"{out_path.name}\n"
                "SET NAMES utf8mb4;\n"
                "SET FOREIGN_KEY_CHECKS=0;\n\n"
            )
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
            if proc.returncode != 0:
                err = proc.stderr.decode("utf-8", errors="replace")
                print(f"mysqldump falló ({proc.returncode}): {err}")
                print("Se generará SQL vía SQLAlchemy como alternativa...")
                _export_sql_alchemy(out_path, tables)
                return
            fh.write(proc.stdout.decode("utf-8", errors="replace"))
            fh.write("\nSET FOREIGN_KEY_CHECKS=1;\n")
        print(f"SQL exportado: {out_path}")
    except FileNotFoundError:
        print("mysqldump no está en PATH; usando export SQLAlchemy...")
        _export_sql_alchemy(out_path, tables)


def _sql_escape(val) -> str:
    if val is None:
        return "NULL"
    if isinstance(val, bool):
        return "1" if val else "0"
    if isinstance(val, (int, float)):
        return str(val)
    if isinstance(val, datetime):
        return "'" + val.strftime("%Y-%m-%d %H:%M:%S") + "'"
    s = str(val).replace("\\", "\\\\").replace("'", "''")
    return f"'{s}'"


def _export_sql_alchemy(out_path: Path, tables: list[str]) -> None:
    from sqlalchemy import text

    app = create_app()
    with app.app_context(), out_path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(
            "-- Sync GESTOR LOCKERS ACTUALIZADO (export SQLAlchemy)\n"
            "-- Aplicar: mysql -u USER -p DATABASE < archivo.sql\n"
            "SET NAMES utf8mb4;\n"
            "SET FOREIGN_KEY_CHECKS=0;\n\n"
        )
        for table in tables:
            rows = db.session.execute(text(f"SELECT * FROM `{table}`")).mappings().all()
            cols = list(rows[0].keys()) if rows else [
                c["name"]
                for c in db.session.execute(text(f"SHOW COLUMNS FROM `{table}`")).mappings()
            ]
            fh.write(f"-- Tabla {table}\n")
            fh.write(f"DELETE FROM `{table}`;\n")
            if not rows:
                fh.write("\n")
                continue
            col_list = ", ".join(f"`{c}`" for c in cols)
            for row in rows:
                vals = ", ".join(_sql_escape(row[c]) for c in cols)
                fh.write(f"INSERT INTO `{table}` ({col_list}) VALUES ({vals});\n")
            fh.write("\n")
        fh.write("SET FOREIGN_KEY_CHECKS=1;\n")
    print(f"SQL exportado (SQLAlchemy): {out_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Actualizar BD desde GESTOR LOCKERS ACTUALIZADO.xlsx"
    )
    parser.add_argument("--excel", default=str(DEFAULT_EXCEL), help="Ruta al Excel")
    parser.add_argument(
        "--sql-out",
        default=str(PROJECT_ROOT / "database" / "sync_gestor_actualizado.sql"),
        help="Ruta del SQL para el servidor",
    )
    parser.add_argument("--no-sql", action="store_true", help="No generar archivo SQL")
    args = parser.parse_args()
    path = Path(args.excel)
    if not path.exists():
        print(f"No se encuentra el Excel: {path}")
        sys.exit(1)

    app = create_app()
    excel_counts: dict = {}

    with app.app_context():
        excel_counts["historial_retiros_antes"] = HistorialRetiros.query.filter(
            HistorialRetiros.es_planta_desposte.is_(False)
        ).count()
        excel_counts["desposte_asig_antes"] = RegistroAsignaciones.query.filter(
            RegistroAsignaciones.es_planta_desposte.is_(True)
        ).count()
        excel_counts["desposte_lock_antes"] = BaseLockers.query.filter(
            db.func.upper(db.func.trim(BaseLockers.area)) == "DESPOSTE"
        ).count()

    _asegurar_area_administrativa(app)

    print(f"Leyendo {path.name} ...")
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    available = set(wb.sheetnames)
    for omit in ("RETIROS", "PERSONAL"):
        if omit in available:
            print(f"Omitido (pedido): hoja {omit}.")

    sheets: dict[str, list[list[str]]] = {}
    for hoja, _tabla in HOJAS_A_IMPORTAR:
        if hoja in available:
            sheets[hoja] = _sheet_to_rows(wb[hoja])
    dot_disp_rows = (
        _sheet_to_rows(wb["DOTACIONES DISPONIBLES"])
        if "DOTACIONES DISPONIBLES" in available
        else []
    )
    wb.close()

    # base_lockers hace sync de locker_disponibles; luego se sobrescribe con la hoja.
    for hoja, tabla in HOJAS_A_IMPORTAR:
        rows = sheets.get(hoja)
        if not rows or len(rows) < 2:
            print(f"[{tabla}] Hoja '{hoja}' vacía o ausente — omitida.")
            continue
        if hoja == "SECA BOTAS":
            utiles = sum(1 for row in rows[1:] if (row[0] or "").strip())
        else:
            utiles = sum(1 for row in rows[1:] if any((c or "").strip() for c in row))
        excel_counts[tabla] = utiles
        print(f"\n>>> {hoja} -> {tabla} ({utiles} filas, replace)")
        fn = IMPORTERS.get(tabla)
        if not fn:
            print(f"  Sin importador para {tabla}")
            continue
        # Evitar doble sync: al importar locker_disponibles después, el sync previo ya ocurrió.
        fn(rows, True, app)

    if dot_disp_rows:
        _sync_dotaciones_disponibles_tabla(dot_disp_rows, app)
        excel_counts["dotaciones_disponibles_sheet"] = sum(
            1 for row in dot_disp_rows[1:] if any((c or "").strip() for c in row)
        )

    # Sanity: códigos admin no deben quedar sueltos
    with app.app_context():
        leftovers = (
            RegistroAsignaciones.query.filter(
                RegistroAsignaciones.es_planta_desposte.is_(False),
                db.func.upper(db.func.trim(RegistroAsignaciones.area)).in_(
                    list(
                        {
                            "SST",
                            "TIC",
                            "ADM",
                            "EXT",
                            "PYP",
                            "GG",
                            "SEG",
                            "ASUR",
                            "MTTO",
                        }
                    )
                ),
            ).count()
        )
        print(f"Códigos admin sueltos en asignaciones (debe ser 0): {leftovers}")

    ok = _validar(app, excel_counts)

    if not args.no_sql:
        _export_sql(Path(args.sql_out))

    print("\nListo." if ok else "\nListo con diferencias — revisa validación.")
    # Normalización usada (referencia)
    print(
        "Mapeo área: LN→BENEFICIO, LOG→LOGISTICA, CAL→CALIDAD, "
        "SST/TIC/ADM/EXT/PYP/GG/SEG/ASUR/MTTO→ADMINISTRATIVA"
    )
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
