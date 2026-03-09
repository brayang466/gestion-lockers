from app import db
from sqlalchemy.orm import validates


class AreaTrabajo(db.Model):
    """Tabla de referencia: áreas de trabajo (BENEFICIO, DESPOSTE, CALIDAD, LYD, PCC)."""
    __tablename__ = "area_trabajo"
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False, unique=True)

    @validates("nombre")
    def nombre_upper(self, key, value):
        """Guarda siempre el nombre en mayúsculas."""
        return (value or "").strip().upper()

    def __repr__(self):
        return f"<AreaTrabajo {self.nombre}>"
