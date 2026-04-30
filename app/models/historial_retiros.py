from app import db
from datetime import datetime


class HistorialRetiros(db.Model):
    __tablename__ = "historial_retiros"
    id = db.Column(db.Integer, primary_key=True)
    identificacion = db.Column(db.String(40), default="")
    codigo_dotacion = db.Column(db.String(50), default="")
    fecha_retiro = db.Column(db.DateTime, nullable=False)
    operario = db.Column(db.String(120), default="")
    codigo_lockets = db.Column(db.String(50), default="")
    area = db.Column(db.String(100), default="")
    talla_operarios = db.Column(db.String(20), default="")
    talla_dotacion = db.Column(db.String(20), default="")
    area_lockers = db.Column(db.String(100), default="")
    observaciones = db.Column(db.String(500), default="")
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)
    es_planta_desposte = db.Column(db.Boolean, nullable=False, default=False)

    def __repr__(self):
        return f"<HistorialRetiros {self.id}>"
