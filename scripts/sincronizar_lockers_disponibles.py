"""
Sincroniza el módulo "Lockers Disponibles" desde "Base de Lockers".

Reglas:
- Solo áreas generales (NO toca DESPOSTE; Desposte se gestiona con database/importar_lockers_desposte.py).
- Solo lockers con estado DISPONIBLE en base_lockers.
- Excluye códigos que ya estén asignados en registro_asignaciones (codigo_lockets).

Uso (desde la raíz del proyecto, con venv activado):
  python scripts/sincronizar_lockers_disponibles.py
"""
from dotenv import load_dotenv
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")


def main():
    from app import create_app
    from scripts.import_datos import _sync_locker_disponibles_from_base_lockers

    app = create_app()
    _sync_locker_disponibles_from_base_lockers(app)


if __name__ == "__main__":
    main()

