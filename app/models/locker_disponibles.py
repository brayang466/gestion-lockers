from app import db
from datetime import datetime


class LockerDisponibles(db.Model):
    __tablename__ = "locker_disponibles"
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(50), nullable=False)  # # LOCKER
    area = db.Column(db.String(100), default="")
    subarea = db.Column(db.String(30), default="")  # DES, CAL, LYD, etc. (ubicación en Desposte)
    area_lockers = db.Column(db.String(100), default="")  # AREAS DE LOCKER
    estado = db.Column(db.String(40), default="disponible")
    observaciones = db.Column(db.Text)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<LockerDisponibles {self.codigo}>"
