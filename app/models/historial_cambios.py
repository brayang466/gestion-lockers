from app import db
from datetime import datetime


class HistorialCambios(db.Model):
    """Auditoría de altas, ediciones y eliminaciones en todos los módulos."""

    __tablename__ = "historial_cambios"

    id = db.Column(db.Integer, primary_key=True)
    modulo = db.Column(db.String(80), default="", index=True)
    accion = db.Column(db.String(20), default="", index=True)  # CREAR | EDITAR | ELIMINAR
    registro_id = db.Column(db.Integer, nullable=True)
    resumen = db.Column(db.String(255), default="")
    detalle = db.Column(db.Text, default="")
    usuario_id = db.Column(db.Integer, nullable=True, index=True)
    usuario_nombre = db.Column(db.String(120), default="")
    area = db.Column(db.String(100), default="")
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f"<HistorialCambios {self.accion} {self.modulo}#{self.registro_id}>"
