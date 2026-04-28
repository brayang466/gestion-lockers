from app import db
from datetime import datetime


class RegistroAsignaciones(db.Model):
    __tablename__ = "registro_asignaciones"
    id = db.Column(db.Integer, primary_key=True)
    id_asignaciones = db.Column(db.String(50), default="")
    codigo_dotacion = db.Column(db.String(50), default="")
    fecha_asignacion = db.Column(db.DateTime, nullable=False)
    fecha_entrega = db.Column(db.DateTime, nullable=True)
    operario = db.Column(db.String(120), default="")
    codigo_lockets = db.Column(db.String(50), default="")
    identificacion = db.Column(db.String(40), default="")
    email = db.Column(db.String(120), default="")
    telefono = db.Column(db.String(30), default="")
    cargo = db.Column(db.String(100), default="")
    codigo_seca_botas = db.Column(db.String(50), default="")
    area = db.Column(db.String(100), default="")
    talla_operarios = db.Column(db.String(20), default="")
    talla_dotacion = db.Column(db.String(20), default="")
    area_lockers = db.Column(db.String(100), default="")
    estado = db.Column(db.String(40), default="Activo")
    observaciones = db.Column(db.Text)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)
    # True solo si el registro viene de ASIGNACIONES DESPOSTE.csv o alta manual en planta (no CSV general).
    es_planta_desposte = db.Column(db.Boolean, nullable=False, default=False)

    def __repr__(self):
        return f"<RegistroAsignaciones {self.id}>"
