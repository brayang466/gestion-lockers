from datetime import datetime
from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, request, session, flash
from app import db
from werkzeug.security import check_password_hash, generate_password_hash
from app.models import (
    BaseLockers, BaseDotaciones, Usuario,
    RegistroPersonal, RegistroAsignaciones, DotacionesDisponibles,
    LockerDisponibles, HistorialRetiros, PersonalPresupuestado,
    IngresoLockers, IngresoDotacion,
)

bp = Blueprint("main", __name__)

# Configuración de cada módulo: model, título, columnas para tabla, campos del formulario, campos fecha
def _parse_date(s):
    if not s:
        return None
    s = (s.replace("Z", "").split(".")[0][:10].strip())
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d")
    except (ValueError, TypeError):
        return None

MODULOS_CONFIG = {
    "base-lockers": {
        "model": BaseLockers,
        "titulo": "Base de Lockers",
        "columnas": [
            {"key": "codigo", "label": "Código"},
            {"key": "area", "label": "Área"},
            {"key": "area_lockers", "label": "Área Lockers"},
            {"key": "estado", "label": "Estado"},
            {"key": "unidad", "label": "Unidad"},
        ],
        "form_fields": [
            {"name": "codigo", "label": "Código", "type": "text", "required": True},
            {"name": "area", "label": "Área", "type": "text"},
            {"name": "area_lockers", "label": "Área Lockers", "type": "text"},
            {"name": "estado", "label": "Estado", "type": "text"},
            {"name": "unidad", "label": "Unidad", "type": "text"},
            {"name": "observaciones", "label": "Observaciones", "type": "textarea"},
        ],
        "date_fields": [],
    },
    "locker-disponibles": {
        "model": LockerDisponibles,
        "titulo": "Locker Disponibles",
        "columnas": [
            {"key": "codigo", "label": "Código"},
            {"key": "area", "label": "Área"},
            {"key": "area_lockers", "label": "Área Lockers"},
            {"key": "estado", "label": "Estado"},
        ],
        "form_fields": [
            {"name": "codigo", "label": "Código", "type": "text", "required": True},
            {"name": "area", "label": "Área", "type": "text"},
            {"name": "area_lockers", "label": "Área Lockers", "type": "text"},
            {"name": "estado", "label": "Estado", "type": "text"},
            {"name": "observaciones", "label": "Observaciones", "type": "textarea"},
        ],
        "date_fields": [],
    },
    "base-dotaciones": {
        "model": BaseDotaciones,
        "titulo": "Base de Dotaciones",
        "columnas": [
            {"key": "codigo", "label": "Código"},
            {"key": "descripcion", "label": "Descripción"},
            {"key": "cantidad", "label": "Cantidad"},
            {"key": "talla", "label": "Talla"},
            {"key": "estado", "label": "Estado"},
        ],
        "form_fields": [
            {"name": "codigo", "label": "Código", "type": "text"},
            {"name": "cantidad", "label": "Cantidad", "type": "number"},
            {"name": "descripcion", "label": "Descripción", "type": "text"},
            {"name": "area_uso", "label": "Área uso", "type": "text"},
            {"name": "talla", "label": "Talla", "type": "text"},
            {"name": "estado", "label": "Estado", "type": "text"},
            {"name": "unidad", "label": "Unidad", "type": "text"},
            {"name": "observaciones", "label": "Observaciones", "type": "textarea"},
        ],
        "date_fields": [],
    },
    "dotaciones-disponibles": {
        "model": DotacionesDisponibles,
        "titulo": "Dotaciones Disponibles",
        "columnas": [
            {"key": "codigo", "label": "Código"},
            {"key": "talla", "label": "Talla"},
            {"key": "descripcion", "label": "Descripción"},
            {"key": "cantidad", "label": "Cantidad"},
            {"key": "unidad", "label": "Unidad"},
        ],
        "form_fields": [
            {"name": "codigo", "label": "Código", "type": "text"},
            {"name": "talla", "label": "Talla", "type": "text"},
            {"name": "descripcion", "label": "Descripción", "type": "text"},
            {"name": "cantidad", "label": "Cantidad", "type": "number"},
            {"name": "unidad", "label": "Unidad", "type": "text"},
            {"name": "observaciones", "label": "Observaciones", "type": "textarea"},
        ],
        "date_fields": [],
    },
    "registro-personal": {
        "model": RegistroPersonal,
        "titulo": "Registro de Personal",
        "columnas": [
            {"key": "id_personal", "label": "ID Personal"},
            {"key": "nombre", "label": "Nombre"},
            {"key": "documento", "label": "Documento"},
            {"key": "cargo", "label": "Cargo"},
            {"key": "area", "label": "Área"},
        ],
        "form_fields": [
            {"name": "id_personal", "label": "ID Personal", "type": "text"},
            {"name": "nombre", "label": "Nombre", "type": "text"},
            {"name": "documento", "label": "Documento", "type": "text"},
            {"name": "email", "label": "Email", "type": "text"},
            {"name": "telefono", "label": "Teléfono", "type": "text"},
            {"name": "cargo", "label": "Cargo", "type": "text"},
            {"name": "area", "label": "Área", "type": "text"},
            {"name": "talla", "label": "Talla", "type": "text"},
            {"name": "area_lockers", "label": "Área Lockers", "type": "text"},
            {"name": "estado", "label": "Estado", "type": "text"},
            {"name": "observaciones", "label": "Observaciones", "type": "textarea"},
        ],
        "date_fields": [],
    },
    "personal-presupuestado": {
        "model": PersonalPresupuestado,
        "titulo": "Personal Presupuestado",
        "columnas": [
            {"key": "nombre", "label": "Nombre"},
            {"key": "documento", "label": "Documento"},
            {"key": "cargo", "label": "Cargo"},
            {"key": "area", "label": "Área"},
            {"key": "aprobados", "label": "Aprobados"},
            {"key": "contratados", "label": "Contratados"},
            {"key": "por_contratar", "label": "Por contratar"},
        ],
        "form_fields": [
            {"name": "nombre", "label": "Nombre", "type": "text"},
            {"name": "documento", "label": "Documento", "type": "text"},
            {"name": "cargo", "label": "Cargo", "type": "text"},
            {"name": "area", "label": "Área", "type": "text"},
            {"name": "aprobados", "label": "Aprobados", "type": "number"},
            {"name": "contratados", "label": "Contratados", "type": "number"},
            {"name": "por_contratar", "label": "Por contratar", "type": "number"},
            {"name": "observaciones", "label": "Observaciones", "type": "textarea"},
        ],
        "date_fields": [],
    },
    "registro-asignaciones": {
        "model": RegistroAsignaciones,
        "titulo": "Registro de Asignaciones",
        "columnas": [
            {"key": "id_asignaciones", "label": "ID"},
            {"key": "operario", "label": "Operario"},
            {"key": "codigo_dotacion", "label": "Cód. Dotación"},
            {"key": "codigo_lockets", "label": "Cód. Lockers"},
            {"key": "fecha_asignacion", "label": "Fecha asignación"},
            {"key": "estado", "label": "Estado"},
        ],
        "form_fields": [
            {"name": "id_asignaciones", "label": "ID Asignaciones", "type": "text"},
            {"name": "codigo_dotacion", "label": "Código dotación", "type": "text"},
            {"name": "fecha_asignacion", "label": "Fecha asignación", "type": "date"},
            {"name": "fecha_entrega", "label": "Fecha entrega", "type": "date"},
            {"name": "operario", "label": "Operario", "type": "text"},
            {"name": "codigo_lockets", "label": "Código lockers", "type": "text"},
            {"name": "identificacion", "label": "Identificación", "type": "text"},
            {"name": "codigo_seca_botas", "label": "Código seca botas", "type": "text"},
            {"name": "area", "label": "Área", "type": "text"},
            {"name": "talla_operarios", "label": "Talla operarios", "type": "text"},
            {"name": "talla_dotacion", "label": "Talla dotación", "type": "text"},
            {"name": "area_lockers", "label": "Área lockers", "type": "text"},
            {"name": "estado", "label": "Estado", "type": "text"},
            {"name": "observaciones", "label": "Observaciones", "type": "textarea"},
        ],
        "date_fields": ["fecha_asignacion", "fecha_entrega"],
    },
    "historial-retiros": {
        "model": HistorialRetiros,
        "titulo": "Historial de Retiros",
        "columnas": [
            {"key": "id_retiro", "label": "ID Retiro"},
            {"key": "operario", "label": "Operario"},
            {"key": "codigo_dotacion", "label": "Cód. Dotación"},
            {"key": "fecha_retiro", "label": "Fecha retiro"},
            {"key": "motivo", "label": "Motivo"},
        ],
        "form_fields": [
            {"name": "id_retiro", "label": "ID Retiro", "type": "text"},
            {"name": "identificacion", "label": "Identificación", "type": "text"},
            {"name": "codigo_dotacion", "label": "Código dotación", "type": "text"},
            {"name": "fecha_retiro", "label": "Fecha retiro", "type": "date"},
            {"name": "operario", "label": "Operario", "type": "text"},
            {"name": "codigo_lockets", "label": "Código lockers", "type": "text"},
            {"name": "area", "label": "Área", "type": "text"},
            {"name": "talla_operarios", "label": "Talla operarios", "type": "text"},
            {"name": "talla_dotacion", "label": "Talla dotación", "type": "text"},
            {"name": "area_lockers", "label": "Área lockers", "type": "text"},
            {"name": "motivo", "label": "Motivo", "type": "text"},
            {"name": "observaciones", "label": "Observaciones", "type": "textarea"},
        ],
        "date_fields": ["fecha_retiro"],
    },
    "ingreso-lockers": {
        "model": IngresoLockers,
        "titulo": "Ingreso de Lockers",
        "columnas": [
            {"key": "codigo", "label": "Código"},
            {"key": "cantidad", "label": "Cantidad"},
            {"key": "fecha_ingreso", "label": "Fecha ingreso"},
        ],
        "form_fields": [
            {"name": "codigo", "label": "Código", "type": "text"},
            {"name": "cantidad", "label": "Cantidad", "type": "number"},
            {"name": "fecha_ingreso", "label": "Fecha ingreso", "type": "date"},
            {"name": "observaciones", "label": "Observaciones", "type": "textarea"},
        ],
        "date_fields": ["fecha_ingreso"],
    },
    "ingreso-dotacion": {
        "model": IngresoDotacion,
        "titulo": "Ingreso de Dotación",
        "columnas": [
            {"key": "codigo", "label": "Código"},
            {"key": "descripcion", "label": "Descripción"},
            {"key": "cantidad", "label": "Cantidad"},
            {"key": "fecha_ingreso", "label": "Fecha ingreso"},
        ],
        "form_fields": [
            {"name": "codigo", "label": "Código", "type": "text"},
            {"name": "descripcion", "label": "Descripción", "type": "text"},
            {"name": "cantidad", "label": "Cantidad", "type": "number"},
            {"name": "fecha_ingreso", "label": "Fecha ingreso", "type": "date"},
            {"name": "observaciones", "label": "Observaciones", "type": "textarea"},
        ],
        "date_fields": ["fecha_ingreso"],
    },
}


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect(url_for("main.login"))
        return f(*args, **kwargs)
    return decorated


@bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("main.dashboard"))
    if request.method == "POST":
        email = (request.form.get("email") or "").strip()
        password = request.form.get("password") or ""
        if not email or not password:
            flash("Ingresa email y contraseña.", "error")
            return render_template("login.html")
        user = Usuario.query.filter_by(email=email, activo=True).first()
        if not user or not user.password_hash:
            flash("Email o contraseña incorrectos.", "error")
            return render_template("login.html")
        if not check_password_hash(user.password_hash, password):
            flash("Email o contraseña incorrectos.", "error")
            return render_template("login.html")
        session["user_id"] = user.id
        session["user_nombre"] = user.nombre or user.email
        return redirect(url_for("main.dashboard"))
    return render_template("login.html")


@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("main.login"))


@bp.route("/restablecer-contrasena", methods=["GET", "POST"])
def restablecer_contrasena():
    if session.get("user_id"):
        return redirect(url_for("main.dashboard"))
    if request.method == "POST":
        email = (request.form.get("email") or "").strip()
        if not email:
            flash("Ingresa tu correo electrónico.", "error")
            return render_template("restablecer_contrasena.html")
        flash("Si este correo está registrado, recibirás instrucciones para restablecer tu contraseña.", "success")
        return redirect(url_for("main.login"))
    return render_template("restablecer_contrasena.html")


@bp.route("/registro", methods=["GET", "POST"])
def registro():
    if session.get("user_id"):
        return redirect(url_for("main.dashboard"))
    if request.method == "POST":
        nombre = (request.form.get("nombre") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        password2 = request.form.get("password2") or ""
        if not nombre or not email or not password:
            flash("Completa todos los campos obligatorios.", "error")
            return render_template("registro.html")
        if password != password2:
            flash("Las contraseñas no coinciden.", "error")
            return render_template("registro.html")
        if len(password) < 6:
            flash("La contraseña debe tener al menos 6 caracteres.", "error")
            return render_template("registro.html")
        if Usuario.query.filter_by(email=email).first():
            flash("Ya existe una cuenta con ese correo.", "error")
            return render_template("registro.html")
        user = Usuario(
            nombre=nombre,
            email=email,
            password_hash=generate_password_hash(password),
            activo=True,
        )
        db.session.add(user)
        db.session.commit()
        flash("Cuenta creada correctamente. Ya puedes iniciar sesión.", "success")
        return redirect(url_for("main.login"))
    return render_template("registro.html")


@bp.route("/")
def index():
    if session.get("user_id"):
        return redirect(url_for("main.dashboard"))
    return redirect(url_for("main.login"))


@bp.route("/dashboard")
@login_required
def dashboard():
    total_lockers = BaseLockers.query.count()
    disponibles = BaseLockers.query.filter_by(estado="disponible").count()
    total_dotaciones = BaseDotaciones.query.count()
    dotaciones_disponibles = DotacionesDisponibles.query.count()
    total_personal = RegistroPersonal.query.count()
    total_asignaciones = RegistroAsignaciones.query.count()
    total_retiros = HistorialRetiros.query.count()
    return render_template(
        "dashboard.html",
        total_lockers=total_lockers,
        disponibles=disponibles,
        total_dotaciones=total_dotaciones,
        dotaciones_disponibles=dotaciones_disponibles,
        total_personal=total_personal,
        total_asignaciones=total_asignaciones,
        total_retiros=total_retiros,
        modulos_config=MODULOS_CONFIG,
    )


@bp.route("/dashboard/<modulo_id>", methods=["GET", "POST"])
@login_required
def modulo(modulo_id):
    if modulo_id not in MODULOS_CONFIG:
        flash("Módulo no encontrado.", "error")
        return redirect(url_for("main.dashboard"))
    config = MODULOS_CONFIG[modulo_id]
    Model = config["model"]
    columnas = config["columnas"]
    form_fields = config["form_fields"]
    date_fields = config.get("date_fields") or []
    titulo = config["titulo"]

    # POST: crear, editar o eliminar
    if request.method == "POST":
        eliminar_id = request.form.get("eliminar_id", type=int)
        edit_id = request.form.get("edit_id", type=int)

        if eliminar_id:
            obj = Model.query.get(eliminar_id)
            if obj:
                db.session.delete(obj)
                db.session.commit()
                flash("Registro eliminado.", "success")
            return redirect(url_for("main.modulo", modulo_id=modulo_id))

        if edit_id:
            obj = Model.query.get(edit_id)
            if not obj:
                flash("Registro no encontrado.", "error")
                return redirect(url_for("main.modulo", modulo_id=modulo_id))
            for f in form_fields:
                name = f["name"]
                val = request.form.get(name)
                if name in date_fields:
                    setattr(obj, name, _parse_date(val) or getattr(obj, name, None))
                elif f["type"] == "number":
                    setattr(obj, name, int(val) if val != "" and val is not None else None)
                else:
                    setattr(obj, name, (val or "").strip() if val is not None else "")
            # Fechas obligatorias sin valor: usar hoy si aplica
            for df in date_fields:
                if getattr(obj, df, None) is None and Model == RegistroAsignaciones and df == "fecha_asignacion":
                    setattr(obj, df, datetime.utcnow())
                if getattr(obj, df, None) is None and Model == HistorialRetiros and df == "fecha_retiro":
                    setattr(obj, df, datetime.utcnow())
                if getattr(obj, df, None) is None and Model == IngresoLockers and df == "fecha_ingreso":
                    setattr(obj, df, datetime.utcnow())
                if getattr(obj, df, None) is None and Model == IngresoDotacion and df == "fecha_ingreso":
                    setattr(obj, df, datetime.utcnow())
            db.session.commit()
            flash("Registro actualizado.", "success")
            return redirect(url_for("main.modulo", modulo_id=modulo_id))

        # Crear
        obj = Model()
        for f in form_fields:
            name = f["name"]
            val = request.form.get(name)
            if name in date_fields:
                setattr(obj, name, _parse_date(val) or (datetime.utcnow() if "fecha" in name else None))
            elif f["type"] == "number":
                setattr(obj, name, int(val) if val != "" and val is not None else None)
            else:
                setattr(obj, name, (val or "").strip() if val is not None else "")
        # Asegurar fechas obligatorias
        if Model == RegistroAsignaciones and getattr(obj, "fecha_asignacion", None) is None:
            obj.fecha_asignacion = datetime.utcnow()
        if Model == HistorialRetiros and getattr(obj, "fecha_retiro", None) is None:
            obj.fecha_retiro = datetime.utcnow()
        if Model == IngresoLockers and getattr(obj, "fecha_ingreso", None) is None:
            obj.fecha_ingreso = datetime.utcnow()
        if Model == IngresoDotacion and getattr(obj, "fecha_ingreso", None) is None:
            obj.fecha_ingreso = datetime.utcnow()
        db.session.add(obj)
        db.session.commit()
        flash("Registro creado.", "success")
        return redirect(url_for("main.modulo", modulo_id=modulo_id))

    # GET: listar y opcionalmente formulario de edición
    rows = Model.query.order_by(Model.id.desc()).all()
    items = []
    for row in rows:
        d = {"id": row.id}
        for col in columnas:
            val = getattr(row, col["key"], None)
            if val is not None and hasattr(val, "strftime"):
                d[col["key"]] = val.strftime("%Y-%m-%d")
            else:
                d[col["key"]] = val
        items.append(d)
    item_edit = None
    edit_data = {}
    edit_id = request.args.get("edit_id", type=int)
    if edit_id:
        item_edit = Model.query.get(edit_id)
        if item_edit:
            for f in form_fields:
                name = f["name"]
                val = getattr(item_edit, name, None)
                if val is not None and name in date_fields and hasattr(val, "strftime"):
                    edit_data[name] = val.strftime("%Y-%m-%d")
                else:
                    edit_data[name] = val
    return render_template(
        "modulo.html",
        modulo_id=modulo_id,
        titulo=titulo,
        columnas=columnas,
        form_fields=form_fields,
        items=items,
        item_edit=item_edit,
        edit_data=edit_data,
        modulos_config=MODULOS_CONFIG,
    )
