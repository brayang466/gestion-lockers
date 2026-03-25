"""
Asigna el rol 'superadmin'.

Uso:
  python scripts/asignar_superadmin.py
    - Si solo hay 1 usuario en la tabla usuarios, le asigna superadmin.
    - Si hay varios, asigna a id=1 si existe; si no, lista usuarios y sale con error.

  python scripts/asignar_superadmin.py correo@ejemplo.com
    - Asigna superadmin al usuario con ese email (sin importar el id).

No recupera usuarios borrados: sin respaldo de BD (dump) esos datos no vuelven.
"""
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
        users = Usuario.query.order_by(Usuario.id).all()
        if not users:
            print("No hay usuarios. Crea uno con: python scripts/crear_admin.py")
            sys.exit(1)

        target = None

        if len(sys.argv) > 1:
            email = sys.argv[1].strip().lower()
            target = Usuario.query.filter(db.func.lower(Usuario.email) == email).first()
            if not target:
                print(f"No existe usuario con email: {sys.argv[1]}")
                sys.exit(1)
        elif len(users) == 1:
            target = users[0]
            print(f"Solo hay un usuario registrado (id={target.id}).")
        else:
            target = Usuario.query.get(1)
            if target:
                print("Varios usuarios: usando id=1 como en asignar_superadmin.sql")
            else:
                print("Varios usuarios y no existe id=1. Indica el email:")
                print("  python scripts/asignar_superadmin.py tu@correo.com\n")
                for u in users:
                    print(f"  id={u.id}  email={u.email}  rol={u.rol}")
                sys.exit(1)

        old = target.rol
        target.rol = "superadmin"
        db.session.commit()
        print(f"Listo: {target.email} (id={target.id})  rol: {old!r} -> 'superadmin'")


if __name__ == "__main__":
    main()
