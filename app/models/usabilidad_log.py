from app import db
from datetime import datetime


class UsabilidadLog(db.Model):
    """Registro de navegación / usabilidad por usuario dentro del sistema."""

    __tablename__ = "usabilidad_log"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=True, index=True)
    user_nombre = db.Column(db.String(120), default="")
    user_email = db.Column(db.String(120), default="")
    user_rol = db.Column(db.String(30), default="")
    area = db.Column(db.String(100), default="")
    path = db.Column(db.String(255), nullable=False, default="")
    metodo = db.Column(db.String(10), default="GET")
    accion = db.Column(db.String(255), default="")
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f"<UsabilidadLog {self.user_email} {self.path}>"
