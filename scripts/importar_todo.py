"""Importar todos los CSV de datos_importar/. Uso: python scripts/importar_todo.py [--replace]"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SCRIPTS))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")
from app import create_app
import import_datos

CARPETA = PROJECT_ROOT / "datos_importar"
# INGRESO DE LOCKERS e INGRESO DE DOTACION no se importan desde CSV (registro manual en la app).
# Cada tabla: lista de nombres de archivo a probar (el primero que exista y tenga ≥2 filas gana).
# Así se usan los CSV con nombres de tus exportaciones (PERSONAL.csv, ASIGNACIONES.csv, etc.).
ORDEN = [
    ("base_lockers", ["base_lockers.csv", "LOCKERES.csv"]),
    ("base_dotaciones", ["base_dotaciones.csv", "DOTACIONES.csv"]),
    ("registro_personal", ["registro_personal.csv", "PERSONAL.csv"]),
    ("personal_presupuestado", ["personal_presupuestado.csv", "PERSONAL PRESUPUESTADO.csv"]),
    ("dotaciones_disponibles", ["dotaciones_disponibles.csv", "DOT DISP.csv", "DOTACIONES DISPONIBLES.csv"]),
    (
        "locker_disponibles",
        ["locker_disponibles.csv", "LOCKER DISP ACTUALIZADO.csv", "LOCKER DISPONIBLES.csv"],
    ),
    ("seca_botas_disponibles", ["seca_botas_disponibles.csv", "SECA BOTAS.csv"]),
    (
        "registro_asignaciones",
        ["registro_asignaciones.csv", "ASIGNACIONES ACTUALIZADO.csv", "ASIGNACIONES.csv"],
    ),
    ("historial_retiros", ["historial_retiros.csv", "RETIROS.csv"]),
]


def _first_csv_with_data(carpeta: Path, candidatos: list) -> tuple:
    """Devuelve (ruta, filas) del primer CSV usable; si ninguno, (None, None)."""
    for nombre in candidatos:
        ruta = carpeta / nombre
        if not ruta.exists():
            continue
        rows = import_datos.load_csv(str(ruta))
        if rows and len(rows) >= 2:
            return ruta, rows
    return None, None


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--replace", action="store_true")
    args = p.parse_args()
    if not CARPETA.exists():
        print("Crea datos_importar/ y pon los CSV ahí.")
        sys.exit(1)
    app = create_app()
    for nombre, candidatos in ORDEN:
        ruta, rows = _first_csv_with_data(CARPETA, candidatos)
        if not ruta:
            print(f"[{nombre}] No encontrado o vacío. Probados: {', '.join(candidatos)}")
            continue
        print(f"[{nombre}] Usando: {ruta.name}")
        try:
            import_datos.IMPORTERS[nombre](rows, args.replace, app)
        except Exception as e:
            print(f"[{nombre}] Error: {e}")
    print("Listo.")

if __name__ == "__main__":
    main()
