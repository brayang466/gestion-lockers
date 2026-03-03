"""Atajo: importar base_lockers. Equivalente a import_datos.py archivo.csv -t base_lockers"""
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
argv = sys.argv[1:]
if "--table" not in argv and "-t" not in argv:
    argv += ["--table", "base_lockers"]
sys.argv = [sys.argv[0]] + argv
import import_datos
if __name__ == "__main__":
    import_datos.main()
