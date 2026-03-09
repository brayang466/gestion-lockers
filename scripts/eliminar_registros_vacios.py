"""
Elimina registros vacíos (sin información útil) de las tablas que se importan desde Excel.
Un registro se considera vacío cuando todos los campos, excepto id y creado_en, están vacíos o son None.

Uso: python scripts/eliminar_registros_vacios.py
     python scripts/eliminar_registros_vacios.py -t registro_personal base_lockers  # solo esas tablas
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

from app import create_app, db
from app.models import (
    RegistroPersonal, RegistroAsignaciones, DotacionesDisponibles,
    PersonalPresupuestado, LockerDisponibles, HistorialRetiros,
    BaseLockers, BaseDotaciones,
)

TABLAS_IMPORTABLES = {
    "registro_personal": RegistroPersonal,
    "registro_asignaciones": RegistroAsignaciones,
    "dotaciones_disponibles": DotacionesDisponibles,
    "personal_presupuestado": PersonalPresupuestado,
    "locker_disponibles": LockerDisponibles,
    "historial_retiros": HistorialRetiros,
    "base_lockers": BaseLockers,
    "base_dotaciones": BaseDotaciones,
}


def valor_vacio(v):
    """True si el valor se considera vacío (sin información)."""
    if v is None:
        return True
    if isinstance(v, str):
        return (v or "").strip() == ""
    # Números 0 suelen venir de celdas vacías en Excel
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return v == 0
    return False


def registro_vacio(obj, Model):
    """True si el registro tiene todos los campos (excepto id, creado_en) vacíos."""
    excluir = {"id", "creado_en"}
    for col in Model.__table__.columns:
        if col.name in excluir:
            continue
        v = getattr(obj, col.name, None)
        if not valor_vacio(v):
            return False
    return True


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Eliminar registros vacíos de tablas importables")
    parser.add_argument("-t", "--tablas", nargs="*", default=None,
                        choices=list(TABLAS_IMPORTABLES),
                        help="Solo limpiar estas tablas (por defecto todas)")
    args = parser.parse_args()
    tablas_a_limpiar = args.tablas if args.tablas else list(TABLAS_IMPORTABLES.keys())

    app = create_app()
    total_eliminados = 0
    with app.app_context():
        for nombre, Model in TABLAS_IMPORTABLES.items():
            if nombre not in tablas_a_limpiar:
                continue
            eliminados = 0
            for obj in Model.query.all():
                if registro_vacio(obj, Model):
                    db.session.delete(obj)
                    eliminados += 1
            if eliminados:
                db.session.commit()
                total_eliminados += eliminados
                print(f"  {nombre}: {eliminados} registro(s) vacío(s) eliminado(s).")
    if total_eliminados:
        print(f"\nTotal: {total_eliminados} registro(s) eliminado(s).")
    else:
        print("No se encontraron registros vacíos en las tablas revisadas.")


if __name__ == "__main__":
    main()
