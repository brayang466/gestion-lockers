from app import db
from datetime import datetime


class RegistroPersonal(db.Model):
    __tablename__ = "registro_personal"
    id = db.Column(db.Integer, primary_key=True)
    id_personal = db.Column(db.String(50), default="")
    nombre = db.Column(db.String(120), default="")  # Operario
    documento = db.Column(db.String(40), default="")  # identificacion
    email = db.Column(db.String(120), default="")
    telefono = db.Column(db.String(30), default="")
    cargo = db.Column(db.String(100), default="")
    area = db.Column(db.String(100), default="")
    talla = db.Column(db.String(20), default="")
    area_lockers = db.Column(db.String(100), default="")
    estado = db.Column(db.String(40), default="")
    observaciones = db.Column(db.Text)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<RegistroPersonal {self.nombre or self.documento}>"
