"""Crear usuario administrador. Uso: python scripts/crear_admin.py"""
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")
from app import create_app, db
from app.models import Usuario
from werkzeug.security import generate_password_hash

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--nombre", "-n", default="")
    parser.add_argument("--email", "-e", default="")
    parser.add_argument("--password", "-p", default="")
    args = parser.parse_args()
    app = create_app()
    with app.app_context():
        nombre = (args.nombre or input("Nombre del admin: ").strip()) or "Administrador"
        email = args.email or input("Email: ").strip()
        if not email:
            print("Email obligatorio.")
            sys.exit(1)
        if Usuario.query.filter_by(email=email).first():
            print(f"Ya existe {email}.")
            sys.exit(0)
        password = args.password or input("Contraseña (min 6): ").strip()
        if not password or len(password) < 6:
            print("Contraseña mínimo 6 caracteres.")
            sys.exit(1)
        usuario = Usuario(nombre=nombre, email=email,
            password_hash=generate_password_hash(password, method="pbkdf2:sha256"),
            rol="admin", activo=True)
        db.session.add(usuario)
        db.session.commit()
        print(f"Admin creado: {email}")

if __name__ == "__main__":
    main()
