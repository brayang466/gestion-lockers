from app import db
from datetime import datetime


class PersonalPresupuestado(db.Model):
    __tablename__ = "personal_presupuestado"
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(120), default="")
    documento = db.Column(db.String(40), default="")
    cargo = db.Column(db.String(100), default="")
    area = db.Column(db.String(100), default="")
    aprobados = db.Column(db.Integer, nullable=True)
    contratados = db.Column(db.Integer, nullable=True)
    por_contratar = db.Column(db.Integer, nullable=True)
    observaciones = db.Column(db.Text)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<PersonalPresupuestado {self.area or self.id}>"
