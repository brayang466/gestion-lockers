"""
Añade la columna palabra_clave a la tabla usuarios si no existe.
Ejecutar una vez: python scripts/agregar_palabra_clave.py
"""
import sys
from pathlib import Path

raiz = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(raiz))

from dotenv import load_dotenv
load_dotenv(raiz / ".env", override=True, encoding="utf-8")

from app import create_app, db

def main():
    app = create_app()
    with app.app_context():
        try:
            # Intentar con AFTER area; si falla, añadir al final
            try:
                db.session.execute(db.text("ALTER TABLE usuarios ADD COLUMN palabra_clave VARCHAR(80) DEFAULT '' AFTER area"))
            except Exception:
                db.session.rollback()
                db.session.execute(db.text("ALTER TABLE usuarios ADD COLUMN palabra_clave VARCHAR(80) DEFAULT ''"))
            db.session.commit()
            print("Columna palabra_clave añadida correctamente.")
        except Exception as e:
            err = str(e)
            if "Duplicate column name" in err or "1060" in err:
                print("La columna palabra_clave ya existe. No es necesario hacer nada.")
            else:
                print("Error:", e)
                sys.exit(1)

if __name__ == "__main__":
    main()
