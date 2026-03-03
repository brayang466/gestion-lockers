from app import db
from datetime import datetime


class BaseLockers(db.Model):
    __tablename__ = "base_lockers"
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(50), nullable=False)  # Codigo de Lockets
    area = db.Column(db.String(100), default="")
    area_lockers = db.Column(db.String(100), default="")
    estado = db.Column(db.String(40), default="disponible")
    unidad = db.Column(db.String(30), default="")
    observaciones = db.Column(db.Text)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<BaseLockers {self.codigo}>"
