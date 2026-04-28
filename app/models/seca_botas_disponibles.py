from app import db


class SecaBotasDisponibles(db.Model):
    __tablename__ = "seca_botas_disponibles"
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(50), nullable=False)
    area_locker = db.Column(db.String(100), default="")
    area = db.Column(db.String(100), default="SIN ASIGNAR")
    estado = db.Column(db.String(40), default="DISPONIBLE")

    def __repr__(self):
        return f"<SecaBotasDisponibles {self.codigo}>"

