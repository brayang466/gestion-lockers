"""
Actualiza id_asignaciones de todos los registros existentes a ASG-000, ASG-001, ASG-002, ...
(3 dígitos) según el orden por id.
Ejecutar desde la raíz: python database/actualizar_id_asignaciones_asg.py
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
    from app.models import RegistroAsignaciones

    app = create_app()
    with app.app_context():
        rows = RegistroAsignaciones.query.order_by(RegistroAsignaciones.id).all()
        for i, r in enumerate(rows):
            r.id_asignaciones = "ASG-{:03d}".format(i)
        db.session.commit()
        print("Actualizados {} registros con ID ASG-000, ASG-001, ...".format(len(rows)))


if __name__ == "__main__":
    main()
