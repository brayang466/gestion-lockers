from app import db
from datetime import datetime


class BaseDotaciones(db.Model):
    __tablename__ = "base_dotaciones"
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(50), default="")  # Codigo de Dotacion
    cantidad = db.Column(db.Integer, nullable=True)
    descripcion = db.Column(db.String(255), default="")
    area_uso = db.Column(db.String(100), default="")
    talla = db.Column(db.String(20), default="")
    estado = db.Column(db.String(40), default="")
    unidad = db.Column(db.String(30), default="")
    observaciones = db.Column(db.Text)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<BaseDotaciones {self.codigo or self.id}>"
