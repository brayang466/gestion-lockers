from app import db
from datetime import datetime


class IngresoLockers(db.Model):
    __tablename__ = "ingreso_lockers"
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(50), default="")
    cantidad = db.Column(db.Integer, default=1)
    fecha_ingreso = db.Column(db.DateTime, nullable=False)
    observaciones = db.Column(db.Text)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<IngresoLockers {self.id}>"
