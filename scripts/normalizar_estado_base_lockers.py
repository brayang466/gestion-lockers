"""Normaliza la columna estado en base_lockers: quita el prefijo 'LOCKERT' en todos
los registros actuales para que queden como los nuevos. Uso: python scripts/normalizar_estado_base_lockers.py"""
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")
from app import create_app, db
from app.models import BaseLockers


def _normalize_estado(estado):
    """Quita el prefijo 'LOCKERT' del campo estado y deja solo el estado real."""
    if not estado or not isinstance(estado, str):
        return (estado or "disponible").strip()
    s = estado.strip()
    s = re.sub(r"^LOCKERT\s*", "", s, flags=re.IGNORECASE).strip()
    return s if s else "disponible"


def main():
    app = create_app()
    with app.app_context():
        rows = BaseLockers.query.all()
        updated = 0
        for row in rows:
            nuevo = _normalize_estado(row.estado)
            if nuevo != (row.estado or "").strip():
                row.estado = nuevo
                updated += 1
        db.session.commit()
        print(f"Registros en base_lockers: {len(rows)}. Actualizados: {updated}.")


if __name__ == "__main__":
    main()
