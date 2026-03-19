"""
Añade la columna subarea a base_lockers y locker_disponibles si no existe.
Ejecutar desde la raíz: python database/agregar_subarea_lockers.py
"""
import os
import sys
from pathlib import Path

raiz = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(raiz))
env_file = raiz / ".env"
if env_file.exists():
    with open(env_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                k, v = k.strip(), v.strip()
                if len(v) >= 2 and v[0] == v[-1] and v[0] in ('"', "'"):
                    v = v[1:-1]
                os.environ.setdefault(k, v)


def main():
    from app import create_app, db
    from sqlalchemy import text

    app = create_app()
    with app.app_context():
        for table in ("base_lockers", "locker_disponibles"):
            try:
                r = db.session.execute(
                    text(
                        "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
                        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t AND COLUMN_NAME = 'subarea'"
                    ),
                    {"t": table},
                ).fetchone()
                if not r:
                    sql = "ALTER TABLE {} ADD COLUMN subarea VARCHAR(30) DEFAULT ''".format(table)
                    db.session.execute(text(sql))
                    db.session.commit()
                    print("Columna 'subarea' agregada a {}.".format(table))
                else:
                    print("La tabla {} ya tiene la columna 'subarea'.".format(table))
            except Exception as e:
                print("Error en {}: {}".format(table, e))
                db.session.rollback()


if __name__ == "__main__":
    main()
