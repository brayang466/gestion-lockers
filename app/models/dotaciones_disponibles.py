from app import db
from datetime import datetime


class DotacionesDisponibles(db.Model):
    __tablename__ = "dotaciones_disponibles"
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(50), default="")  # CODIGO DE DOTACION
    talla = db.Column(db.String(20), default="")
    descripcion = db.Column(db.String(255), default="")
    cantidad = db.Column(db.Integer, default=0)
    unidad = db.Column(db.String(30), default="")
    observaciones = db.Column(db.Text)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<DotacionesDisponibles {self.codigo or self.id}>"
