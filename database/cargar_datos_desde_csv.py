"""
Carga masiva de datos desde datos_importar/ (y CSV específicos DESPOSTE).

Orden:
  1) Inserta filas en area_trabajo si faltan (menú "Cambiar área"), sin tocar el resto de tablas.
  2) scripts/importar_todo.py [--replace] → CSV estándar (base_lockers, base_dotaciones, etc.).
  3) Si existen los archivos, ejecuta los importadores DESPOSTE (sustituyen solo el bloque DESPOSTE/subáreas).

Uso (desde la raíz del proyecto, con .env y venv activos):
  python database/cargar_datos_desde_csv.py
  python database/cargar_datos_desde_csv.py --replace

  --replace  Vacía cada tabla antes de importar el CSV correspondiente (recomendado en BD nueva).

Nota: esto NO sustituye un respaldo completo (gestor_lockers_dump.sql). Si tienes dump, usa:
  python scripts/restaurar_bd.py
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
DATOS = ROOT / "datos_importar"

# Mismo criterio que scripts/actualizar_areas_y_crear_area_trabajo.py (solo inserción, sin UPDATE masivos)
AREAS_TRABAJO = ["BENEFICIO", "DESPOSTE", "CALIDAD", "LYD", "PCC", "LOGISTICA"]

DESPOSTE_IMPORTS = [
    ("DOTACION DESPOSTE.csv", ROOT / "database" / "importar_dotacion_desposte.py"),
    ("LOCKERS DES.csv", ROOT / "database" / "importar_lockers_desposte.py"),
    ("ASIGNACIONES DESPOSTE.csv", ROOT / "database" / "importar_asignaciones_desposte.py"),
    ("RETIROS DESPOSTE.csv", ROOT / "database" / "importar_retiros_desposte.py"),
]


def _seed_area_trabajo():
    import os

    env = ROOT / ".env"
    if env.exists():
        with open(env, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    k, v = k.strip(), v.strip()
                    if len(v) >= 2 and v[0] == v[-1] and v[0] in ('"', "'"):
                        v = v[1:-1]
                    os.environ.setdefault(k, v)

    sys.path.insert(0, str(ROOT))
    from app import create_app, db
    from app.models import AreaTrabajo

    app = create_app()
    with app.app_context():
        for nombre in AREAS_TRABAJO:
            if not AreaTrabajo.query.filter_by(nombre=nombre).first():
                db.session.add(AreaTrabajo(nombre=nombre))
                print(f"  area_trabajo: insertado '{nombre}'")
        db.session.commit()
    print("Áreas de trabajo: listo.")


def _run(cmd: list[str]) -> int:
    print("\n>>>", " ".join(cmd))
    return subprocess.call(cmd, cwd=str(ROOT))


def main():
    p = argparse.ArgumentParser(description="Cargar datos desde datos_importar/ y CSV DESPOSTE.")
    p.add_argument(
        "--replace",
        action="store_true",
        help="Pasar --replace a importar_todo.py (vaciar tablas antes de cada CSV estándar).",
    )
    p.add_argument(
        "--skip-desposte",
        action="store_true",
        help="No ejecutar importadores DESPOSTE aunque existan los CSV.",
    )
    args = p.parse_args()

    if not DATOS.is_dir():
        print(f"No existe la carpeta {DATOS}. Créala y coloca los CSV.")
        sys.exit(1)

    print("=== 1) Áreas de trabajo (area_trabajo) ===")
    _seed_area_trabajo()

    print("\n=== 2) CSV estándar (importar_todo) ===")
    cmd = [sys.executable, str(SCRIPTS / "importar_todo.py")]
    if args.replace:
        cmd.append("--replace")
    code = _run(cmd)
    if code != 0:
        print("importar_todo terminó con código", code)

    if args.skip_desposte:
        print("\n(Omitidos importadores DESPOSTE por --skip-desposte)")
        print("Listo.")
        sys.exit(0)

    print("\n=== 3) CSV específicos DESPOSTE (si existen) ===")
    for csv_name, script_path in DESPOSTE_IMPORTS:
        csv_path = DATOS / csv_name
        if not csv_path.exists():
            print(f"  [omitido] No está {csv_path.name}")
            continue
        if not script_path.is_file():
            print(f"  [error] No existe script {script_path}")
            continue
        code = _run([sys.executable, str(script_path)])
        if code != 0:
            print(f"  Advertencia: {script_path.name} salió con código {code}")

    print("\nListo. Reinicia la app si ya estaba en ejecución.")
    print(
        "Si necesitas normalizar códigos de área antiguos (LN→BENEFICIO, etc.), "
        "revisa scripts/actualizar_areas_y_crear_area_trabajo.py (puede afectar subáreas DESPOSTE)."
    )


if __name__ == "__main__":
    main()
