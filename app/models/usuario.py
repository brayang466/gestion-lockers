from app import db
from datetime import datetime


class Usuario(db.Model):
    __tablename__ = "usuarios"
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), default="")
    rol = db.Column(db.String(30), default="usuario")  # superadmin | admin | coordinador | usuario
    area = db.Column(db.String(100), default="")  # área asignada (para coordinador)
    palabra_clave = db.Column(db.String(80), default="")  # pista para recordar contraseña (se muestra al fallar login)
    activo = db.Column(db.Boolean, default=True)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Usuario {self.email}>"
