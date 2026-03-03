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
ORDEN = [
    ("base_lockers", "base_lockers.csv"),
    ("base_dotaciones", "base_dotaciones.csv"),
    ("registro_personal", "registro_personal.csv"),
    ("personal_presupuestado", "personal_presupuestado.csv"),
    ("dotaciones_disponibles", "dotaciones_disponibles.csv"),
    ("locker_disponibles", "locker_disponibles.csv"),
    ("registro_asignaciones", "registro_asignaciones.csv"),
    ("historial_retiros", "historial_retiros.csv"),
]

def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--replace", action="store_true")
    args = p.parse_args()
    if not CARPETA.exists():
        print("Crea datos_importar/ y pon los CSV ahí.")
        sys.exit(1)
    app = create_app()
    for nombre, archivo in ORDEN:
        ruta = CARPETA / archivo
        if not ruta.exists():
            print(f"[{nombre}] No encontrado: {ruta}")
            continue
        rows = import_datos.load_csv(str(ruta))
        if not rows or len(rows) < 2:
            print(f"[{nombre}] Sin datos")
            continue
        try:
            import_datos.IMPORTERS[nombre](rows, args.replace, app)
        except Exception as e:
            print(f"[{nombre}] Error: {e}")
    print("Listo.")

if __name__ == "__main__":
    main()
