"""
Actualiza en todas las tablas con columna área (area, area_uso, area_lockers):
  LN -> BENEFICIO, DES/Des/des -> DESPOSTE, CAL -> CALIDAD, etc.
Crea la tabla area_trabajo e inserta: BENEFICIO, DESPOSTE, CALIDAD, LYD, PCC, LOGISTICA.

Módulos afectados (dashboard por área):
  - Lockers: base_lockers, locker_disponibles
  - Dotaciones: base_dotaciones (area_uso)
  - Personal: registro_personal, personal_presupuestado
  - Operaciones: registro_asignaciones, historial_retiros
  - Usuarios: usuarios (área asignada)

Uso: python scripts/actualizar_areas_y_crear_area_trabajo.py
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

from app import create_app, db
from app.models import AreaTrabajo
from sqlalchemy import text

# Reemplazos a aplicar (valor actual -> valor final en MAYÚSCULAS)
REEMPLAZOS = [
    ("LN", "BENEFICIO"),
    ("DES", "DESPOSTE"),
    ("Des", "DESPOSTE"),
    ("des", "DESPOSTE"),
    ("Desposte", "DESPOSTE"),
    ("CAL", "CALIDAD"),
    ("VIS", "VISITA"),
    ("LOG", "LOGISTICA"),
    ("EXT", "EXTERNO"),
    ("Beneficio", "BENEFICIO"),
    ("Calidad", "CALIDAD"),
    ("Visita", "VISITA"),
    ("Logistica", "LOGISTICA"),
    ("logistica", "LOGISTICA"),
    ("Externo", "EXTERNO"),
]

# Todas las tablas y columnas que almacenan área de trabajo (por módulo)
# Formato: (tabla, columna) — usado para filtrar dashboard y listados por área
TABLAS_Y_COLUMNAS_AREA = [
    # Usuarios (área asignada)
    ("usuarios", "area"),
    # Lockers
    ("base_lockers", "area"),
    ("base_lockers", "area_lockers"),
    ("locker_disponibles", "area"),
    ("locker_disponibles", "area_lockers"),
    # Dotaciones
    ("base_dotaciones", "area_uso"),
    # Personal
    ("registro_personal", "area"),
    ("registro_personal", "area_lockers"),
    ("personal_presupuestado", "area"),
    # Operaciones
    ("registro_asignaciones", "area"),
    ("registro_asignaciones", "area_lockers"),
    ("historial_retiros", "area"),
    ("historial_retiros", "area_lockers"),
]

# Sin duplicados para no ejecutar dos veces la misma tabla.columna
TABLAS_Y_COLUMNAS_AREA = list(dict.fromkeys(TABLAS_Y_COLUMNAS_AREA))

AREAS_TRABAJO = ["BENEFICIO", "DESPOSTE", "CALIDAD", "LYD", "PCC", "LOGISTICA"]


def main():
    app = create_app()
    with app.app_context():
        db.create_all()

        # 1) DES -> DESPOSTE (insensible a mayúsculas)
        print("--- Normalizando DES -> DESPOSTE ---")
        for tabla, col in TABLAS_Y_COLUMNAS_AREA:
            try:
                q = text(
                    f"UPDATE `{tabla}` SET `{col}` = 'DESPOSTE' "
                    f"WHERE UPPER(TRIM(COALESCE(`{col}`,''))) IN ('DES', 'DESPOSTE')"
                )
                res = db.session.execute(q)
                if res.rowcount and res.rowcount > 0:
                    print(f"  {tabla}.{col}: {res.rowcount} fila(s) -> DESPOSTE")
            except Exception as e:
                print(f"  {tabla}.{col}: {e}")
        db.session.commit()

        # 2) LOG -> LOGISTICA (insensible a mayúsculas: LOG, Log, log, Logistica, LOGISTICA)
        print("--- Normalizando LOG / LOGISTICA ---")
        for tabla, col in TABLAS_Y_COLUMNAS_AREA:
            try:
                q = text(
                    f"UPDATE `{tabla}` SET `{col}` = 'LOGISTICA' "
                    f"WHERE UPPER(TRIM(COALESCE(`{col}`,''))) IN ('LOG', 'LOGISTICA')"
                )
                res = db.session.execute(q)
                if res.rowcount and res.rowcount > 0:
                    print(f"  {tabla}.{col}: {res.rowcount} fila(s) -> LOGISTICA")
            except Exception as e:
                print(f"  {tabla}.{col}: {e}")
        db.session.commit()

        # 3) Resto de reemplazos (por valor exacto TRIM)
        print("--- Resto de reemplazos (LN, CAL, etc.) ---")
        for tabla, col in TABLAS_Y_COLUMNAS_AREA:
            for codigo, nombre in REEMPLAZOS:
                if codigo in ("DES", "Des", "des", "Desposte", "LOG", "Logistica", "logistica"):
                    continue
                try:
                    q = text(
                        f"UPDATE `{tabla}` SET `{col}` = :nombre WHERE TRIM(COALESCE(`{col}`,'')) = :codigo"
                    )
                    res = db.session.execute(q, {"nombre": nombre, "codigo": codigo})
                    if res.rowcount and res.rowcount > 0:
                        print(f"  {tabla}.{col}: {res.rowcount} fila(s) {codigo} -> {nombre}")
                except Exception as e:
                    print(f"  {tabla}.{col} ({codigo}->{nombre}): {e}")
        db.session.commit()

        # 4) Rellenar area_trabajo (incluye LOGISTICA para el menú de áreas)
        for nombre in AREAS_TRABAJO:
            existe = AreaTrabajo.query.filter_by(nombre=nombre).first()
            if not existe:
                db.session.add(AreaTrabajo(nombre=nombre))
                print(f"  area_trabajo: insertado '{nombre}'")
        db.session.commit()

        # 5) Mayúsculas en area_trabajo
        db.session.execute(text("UPDATE `area_trabajo` SET `nombre` = UPPER(TRIM(`nombre`))"))
        db.session.commit()

        print("Listo: DES y variantes asignados a DESPOSTE; tabla area_trabajo actualizada.")


if __name__ == "__main__":
    main()
