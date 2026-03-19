from app import db
from datetime import datetime


class PersonalPresupuestado(db.Model):
    __tablename__ = "personal_presupuestado"
    id = db.Column(db.Integer, primary_key=True)
    area = db.Column(db.String(100), default="")
    aprobados = db.Column(db.Integer, nullable=True)
    contratados = db.Column(db.Integer, nullable=True)
    por_contratar = db.Column(db.Integer, nullable=True)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<PersonalPresupuestado {self.area or self.id}>"
