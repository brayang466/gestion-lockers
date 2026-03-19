"""Asigna el rol 'superadmin' al usuario con id = 1. Uso: python scripts/asignar_superadmin.py"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")
from app import create_app, db
from app.models import Usuario


def main():
    app = create_app()
    with app.app_context():
        user = Usuario.query.get(1)
        if not user:
            print("No existe usuario con id = 1. Crea primero un usuario.")
            sys.exit(1)
        user.rol = "superadmin"
        db.session.commit()
        print(f"Rol 'superadmin' asignado a: {user.email} (id=1)")


if __name__ == "__main__":
    main()
