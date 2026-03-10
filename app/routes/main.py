import os
from datetime import datetime, timedelta
from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, request, session, flash, current_app
from itsdangerous import URLSafeTimedSerializer, BadSignature
from app import db
from werkzeug.security import check_password_hash, generate_password_hash
from app.utils.email import send_password_reset_email, send_password_changed_notification
from app.models import (
    BaseLockers, BaseDotaciones, Usuario,
    RegistroPersonal, RegistroAsignaciones, DotacionesDisponibles,
    LockerDisponibles, HistorialRetiros, PersonalPresupuestado,
    IngresoLockers, IngresoDotacion, AreaTrabajo,
)

bp = Blueprint("main", __name__)

# Paginación: máximo registros por página en módulos (evita cargar miles de filas)
PER_PAGE = 50

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
        "icon": "locker",
        "area_key": "area",
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
        "icon": "key",
        "area_key": "area",
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
        "icon": "package",
        "area_key": "area_uso",
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
        "icon": "boxes",
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
        "icon": "users",
        "area_key": "area",
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
        "icon": "user-group",
        "area_key": "area",
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
        "icon": "clipboard-check",
        "area_key": "area",
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
        "icon": "archive",
        "area_key": "area",
        "columnas": [
            {"key": "operario", "label": "Operario"},
            {"key": "codigo_dotacion", "label": "Cód. Dotación"},
            {"key": "fecha_retiro", "label": "Fecha retiro"},
        ],
        "form_fields": [
            {"name": "identificacion", "label": "Identificación", "type": "text"},
            {"name": "codigo_dotacion", "label": "Código dotación", "type": "text"},
            {"name": "fecha_retiro", "label": "Fecha retiro", "type": "date"},
            {"name": "operario", "label": "Operario", "type": "text"},
            {"name": "codigo_lockets", "label": "Código lockers", "type": "text"},
            {"name": "area", "label": "Área", "type": "text"},
            {"name": "talla_operarios", "label": "Talla operarios", "type": "text"},
            {"name": "talla_dotacion", "label": "Talla dotación", "type": "text"},
            {"name": "area_lockers", "label": "Área lockers", "type": "text"},
        ],
        "date_fields": ["fecha_retiro"],
    },
    "ingreso-lockers": {
        "model": IngresoLockers,
        "titulo": "Ingreso de Lockers",
        "icon": "box-arrow-in",
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
        "icon": "box-dotacion",
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
        recordarme = request.form.get("recordarme") == "1"
        if not email or not password:
            flash("Ingresa email y contraseña.", "error")
            return render_template("login.html", email_value=email, recordarme_checked=recordarme)
        user = Usuario.query.filter_by(email=email).first()
        if not user or not user.password_hash:
            flash("Email o contraseña incorrectos.", "error")
            return render_template("login.html", email_value=email, recordarme_checked=recordarme)
        if not getattr(user, "activo", True):
            flash("Tu cuenta está inactiva. Contacta al administrador para reactivarla.", "error")
            return render_template("login.html", email_value=email, recordarme_checked=recordarme)
        if not check_password_hash(user.password_hash, password):
            flash("Email o contraseña incorrectos.", "error")
            palabra_clave_hint = (user.palabra_clave or "").strip() if getattr(user, "palabra_clave", None) else ""
            return render_template("login.html", email_value=email, recordarme_checked=recordarme, palabra_clave_hint=palabra_clave_hint)
        session["user_id"] = user.id
        session["user_nombre"] = user.nombre or user.email
        session["user_rol"] = (user.rol or "usuario").strip().lower()
        session["user_area"] = (user.area or "").strip()
        session.pop("current_area", None)
        if recordarme:
            session.permanent = True
        resp = redirect(url_for("main.areas"))
        if recordarme:
            resp.set_cookie("remember_email", email, max_age=30 * 24 * 3600, httponly=False, samesite="Lax")
        else:
            resp.delete_cookie("remember_email")
        return resp
    email_value = request.cookies.get("remember_email", "")
    recordarme_checked = bool(email_value)
    show_register = request.args.get("show_register") == "1"
    registro_form = session.pop("registro_form", None)
    if show_register or registro_form:
        show_register = True
        if registro_form:
            nombre_value = registro_form.get("nombre_value", "")
            email_value = registro_form.get("email_value", email_value)
            palabra_clave_value = registro_form.get("palabra_clave_value", "")
        else:
            nombre_value = ""
            palabra_clave_value = ""
    else:
        show_register = False
        nombre_value = ""
        palabra_clave_value = ""
    return render_template(
        "login.html",
        email_value=email_value,
        recordarme_checked=recordarme_checked,
        show_register=show_register,
        nombre_value=nombre_value,
        palabra_clave_value=palabra_clave_value,
    )


@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("main.login"))


def _make_reset_token(user_id):
    s = URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="password-reset")
    return s.dumps(user_id)


def _verify_reset_token(token, max_age_seconds=None):
    if max_age_seconds is None:
        max_age_seconds = current_app.config.get("PASSWORD_RESET_EXPIRE_MINUTES", 15) * 60
    s = URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="password-reset")
    try:
        return s.loads(token, max_age=max_age_seconds)
    except (BadSignature, Exception):
        return None


@bp.route("/restablecer-contrasena", methods=["GET", "POST"])
def restablecer_contrasena():
    if session.get("user_id"):
        return redirect(url_for("main.dashboard"))
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        if not email:
            flash("Ingresa tu correo electrónico.", "error")
            return render_template("restablecer_contrasena.html")
        user = Usuario.query.filter_by(email=email, activo=True).first()
        if user and user.password_hash:
            token = _make_reset_token(user.id)
            # Usar APP_URL del .env (prioridad) para que el enlace use la IP/host de la red, no localhost
            base = (
                current_app.config.get("APP_URL") or os.environ.get("APP_URL") or ""
            ).strip()
            if not base:
                base = request.url_root.rstrip("/")
            reset_url = base + url_for("main.restablecer_contrasena_confirmar", token=token)
            # Leer de config y, si faltan, de os.environ (p. ej. con reloader de Flask)
            mail_user = (
                current_app.config.get("MAIL_USERNAME") or os.environ.get("MAIL_USERNAME") or ""
            ).strip()
            mail_pass = current_app.config.get("MAIL_PASSWORD") or os.environ.get("MAIL_PASSWORD") or ""
            if mail_user and mail_pass:
                if send_password_reset_email(user.email, reset_url):
                    flash("Revisa tu correo: te enviamos un enlace para restablecer tu contraseña. Si no lo ves, revisa la carpeta de spam.", "success")
                else:
                    flash("No pudimos enviar el correo. Revisa la configuración del servidor de correo o intenta más tarde.", "error")
            else:
                flash("El envío de correo no está configurado. Contacta al administrador. Enlace de prueba (válido 1 h): " + reset_url, "error")
        else:
            flash("Si este correo está registrado, recibirás instrucciones para restablecer tu contraseña.", "success")
        return redirect(url_for("main.login"))
    return render_template("restablecer_contrasena.html")


@bp.route("/restablecer-contrasena/confirmar", methods=["GET", "POST"])
def restablecer_contrasena_confirmar():
    token = request.args.get("token") or (request.form.get("token") if request.method == "POST" else None)
    if not token:
        flash("Enlace no válido o expirado.", "error")
        return redirect(url_for("main.restablecer_contrasena"))
    if request.method == "POST":
        user_id = _verify_reset_token(token)
        if not user_id:
            flash("El enlace ha expirado o no es válido. Solicita uno nuevo desde la pantalla de restablecer contraseña.", "error")
            return redirect(url_for("main.restablecer_contrasena"))
        password = (request.form.get("password") or "").strip()
        password2 = (request.form.get("password2") or "").strip()
        if not password or len(password) < 8:
            flash("La contraseña debe tener al menos 8 caracteres.", "error")
            return render_template("restablecer_contrasena_confirmar.html", token=token)
        if not any(c.isupper() for c in password):
            flash("La contraseña debe incluir al menos una mayúscula.", "error")
            return render_template("restablecer_contrasena_confirmar.html", token=token)
        if not any(c.isdigit() for c in password):
            flash("La contraseña debe incluir al menos un número.", "error")
            return render_template("restablecer_contrasena_confirmar.html", token=token)
        if not any(not c.isalnum() for c in password):
            flash("La contraseña debe incluir al menos un símbolo (ej. @ $ ! #).", "error")
            return render_template("restablecer_contrasena_confirmar.html", token=token)
        if password != password2:
            flash("Las contraseñas no coinciden.", "error")
            return render_template("restablecer_contrasena_confirmar.html", token=token)
        user = Usuario.query.get(user_id)
        if not user:
            flash("Usuario no encontrado.", "error")
            return redirect(url_for("main.restablecer_contrasena"))
        user.password_hash = generate_password_hash(password)
        db.session.commit()
        # Notificar al usuario por correo que su contraseña fue cambiada
        try:
            send_password_changed_notification(user.email, user.nombre)
        except Exception:
            pass
        flash("Contraseña actualizada correctamente. Ya puedes iniciar sesión. Revisa tu correo para la confirmación.", "success")
        return redirect(url_for("main.login"))
    return render_template("restablecer_contrasena_confirmar.html", token=token)


def _registro_form_session(nombre, email, palabra_clave):
    """Guarda datos del formulario de registro en sesión para mostrarlos en login (misma vista)."""
    session["registro_form"] = {
        "nombre_value": nombre,
        "email_value": email,
        "palabra_clave_value": palabra_clave[:80] if palabra_clave else "",
    }


@bp.route("/registro", methods=["GET", "POST"])
def registro():
    if session.get("user_id"):
        return redirect(url_for("main.dashboard"))
    if request.method == "POST":
        nombre = (request.form.get("nombre") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        password2 = request.form.get("password2") or ""
        palabra_clave = (request.form.get("palabra_clave") or "").strip()
        if not nombre or not email or not password:
            flash("Completa todos los campos obligatorios.", "error")
            _registro_form_session(nombre, email, palabra_clave)
            return redirect(url_for("main.login", show_register=1))
        if password != password2:
            flash("Las contraseñas no coinciden.", "error")
            _registro_form_session(nombre, email, palabra_clave)
            return redirect(url_for("main.login", show_register=1))
        if len(password) < 8:
            flash("La contraseña debe tener al menos 8 caracteres.", "error")
            _registro_form_session(nombre, email, palabra_clave)
            return redirect(url_for("main.login", show_register=1))
        if not any(c.isupper() for c in password):
            flash("La contraseña debe incluir al menos una mayúscula.", "error")
            _registro_form_session(nombre, email, palabra_clave)
            return redirect(url_for("main.login", show_register=1))
        if not any(c.isdigit() for c in password):
            flash("La contraseña debe incluir al menos un número.", "error")
            _registro_form_session(nombre, email, palabra_clave)
            return redirect(url_for("main.login", show_register=1))
        if not any(not c.isalnum() for c in password):
            flash("La contraseña debe incluir al menos un símbolo (ej. @ $ ! #).", "error")
            _registro_form_session(nombre, email, palabra_clave)
            return redirect(url_for("main.login", show_register=1))
        if Usuario.query.filter_by(email=email).first():
            flash("El correo que intenta registrar ya está en el sistema. Pruebe con otro.", "error")
            _registro_form_session(nombre, email, palabra_clave)
            return redirect(url_for("main.login", show_register=1))
        user = Usuario(
            nombre=nombre,
            email=email,
            password_hash=generate_password_hash(password),
            rol="usuario",
            activo=True,
            palabra_clave=palabra_clave[:80] if palabra_clave else "",
        )
        db.session.add(user)
        db.session.commit()
        flash("Cuenta creada correctamente. Ya puedes iniciar sesión.", "success")
        return redirect(url_for("main.login"))
    return redirect(url_for("main.login", show_register=1))


def _allowed_areas_for_user():
    """Áreas a las que el usuario puede entrar. Admin: todas; otro: solo su área asignada."""
    rol = (session.get("user_rol") or "usuario").strip().lower()
    user_area = (session.get("user_area") or "").strip()
    if rol == "admin":
        return [a.nombre for a in AreaTrabajo.query.order_by(AreaTrabajo.nombre).all()]
    if user_area:
        return [user_area]
    return []


def _require_current_area(f):
    """Redirige a /areas si no hay área en sesión (para dashboard y módulos)."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect(url_for("main.login"))
        if not session.get("current_area"):
            return redirect(url_for("main.areas"))
        return f(*args, **kwargs)
    return decorated


@bp.route("/")
def index():
    if session.get("user_id"):
        if session.get("current_area"):
            return redirect(url_for("main.dashboard"))
        return redirect(url_for("main.areas"))
    return redirect(url_for("main.login"))


@bp.route("/areas")
@login_required
def areas():
    """Selector de área de trabajo. Sin área asignada (y no admin) no puede entrar a ninguna."""
    allowed = _allowed_areas_for_user()
    sin_area = len(allowed) == 0
    areas_list = AreaTrabajo.query.order_by(AreaTrabajo.nombre).all()
    # Para mostrar: admin ve todas; usuario/coordinador solo las permitidas
    if sin_area:
        areas_para_elegir = []
    else:
        areas_para_elegir = [a for a in areas_list if a.nombre in allowed]
    return render_template("areas.html", areas_para_elegir=areas_para_elegir, sin_area=sin_area)


@bp.route("/entrar-area/<nombre>")
@login_required
def entrar_area(nombre):
    """Fija el área actual y redirige al dashboard."""
    nombre = (nombre or "").strip().upper()
    allowed = _allowed_areas_for_user()
    if nombre not in allowed:
        flash("No tienes acceso a esa área.", "error")
        return redirect(url_for("main.areas"))
    area_obj = AreaTrabajo.query.filter_by(nombre=nombre).first()
    if not area_obj:
        flash("Área no encontrada.", "error")
        return redirect(url_for("main.areas"))
    session["current_area"] = area_obj.nombre
    return redirect(url_for("main.dashboard"))


@bp.route("/dashboard")
@login_required
@_require_current_area
def dashboard():
    from sqlalchemy import func
    current_area = (session.get("current_area") or "").strip()
    total_lockers = BaseLockers.query.filter(BaseLockers.area == current_area).count()
    disponibles = BaseLockers.query.filter(BaseLockers.area == current_area, BaseLockers.estado == "disponible").count()
    total_dotaciones = BaseDotaciones.query.filter(BaseDotaciones.area_uso == current_area).count()
    dotaciones_disponibles = DotacionesDisponibles.query.count()
    total_personal = RegistroPersonal.query.filter(RegistroPersonal.area == current_area).count()
    total_asignaciones = RegistroAsignaciones.query.filter(RegistroAsignaciones.area == current_area).count()
    total_retiros = HistorialRetiros.query.filter(HistorialRetiros.area == current_area).count()
    es_admin = (session.get("user_rol") or "").strip().lower() == "admin"
    today = datetime.utcnow().date()
    seven_days_ago = today - timedelta(days=6)
    chart_by_date = dict(
        db.session.query(
            func.date(RegistroAsignaciones.creado_en).label("d"),
            func.count(RegistroAsignaciones.id).label("c"),
        )
        .filter(
            RegistroAsignaciones.area == current_area,
            func.date(RegistroAsignaciones.creado_en) >= seven_days_ago,
        )
        .group_by(func.date(RegistroAsignaciones.creado_en))
        .all()
    )
    dias_nombres = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
    chart_labels = []
    chart_data = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        chart_labels.append(dias_nombres[d.weekday()] + " " + d.strftime("%d/%m")[:5])
        chart_data.append(chart_by_date.get(d, 0))
    # Categorías para filtros del dashboard (Gestión de Módulos)
    MODULE_CATEGORIES = {
        "base-lockers": "Lockers",
        "locker-disponibles": "Lockers",
        "ingreso-lockers": "Lockers",
        "base-dotaciones": "Dotaciones",
        "dotaciones-disponibles": "Dotaciones",
        "ingreso-dotacion": "Dotaciones",
        "registro-personal": "Personal",
        "personal-presupuestado": "Personal",
        "registro-asignaciones": "Operaciones",
        "historial-retiros": "Operaciones",
    }
    unique_categories = sorted(set(MODULE_CATEGORIES.values()))
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
        show_usuarios_module=es_admin,
        chart_labels=chart_labels,
        chart_data=chart_data,
        module_categories=MODULE_CATEGORIES,
        unique_categories=unique_categories,
        current_area=current_area,
    )


def _user_can_edit():
    return (session.get("user_rol") or "usuario") in ("admin", "coordinador")


def _admin_required(f):
    """Decorator: solo administrador."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect(url_for("main.login"))
        if (session.get("user_rol") or "").strip().lower() != "admin":
            flash("Solo el administrador puede acceder a esta sección.", "error")
            return redirect(url_for("main.dashboard"))
        return f(*args, **kwargs)
    return decorated


@bp.route("/dashboard/usuarios", methods=["GET", "POST"])
@login_required
@_admin_required
def usuarios():
    """Módulo solo admin: listar usuarios, editar Área e inactivar/activar."""
    areas = AreaTrabajo.query.order_by(AreaTrabajo.nombre).all()
    if request.method == "POST":
        toggle_id = request.form.get("toggle_activo_id", type=int)
        if toggle_id:
            user = Usuario.query.get(toggle_id)
            if user:
                nuevo_activo = not user.activo
                # Actualizar solo la columna activo para no tocar password_hash ni otros campos
                Usuario.query.filter_by(id=toggle_id).update({"activo": nuevo_activo}, synchronize_session=False)
                db.session.commit()
                estado = "activado" if nuevo_activo else "inactivado"
                flash(f"Usuario {estado} correctamente.", "success")
            return redirect(url_for("main.usuarios"))
        edit_id = request.form.get("edit_id", type=int)
        area_val = (request.form.get("area") or "").strip()
        if edit_id:
            user = Usuario.query.get(edit_id)
            if user:
                user.area = area_val
                db.session.commit()
                flash("Área del usuario actualizada.", "success")
            return redirect(url_for("main.usuarios"))
    users = Usuario.query.order_by(Usuario.creado_en.desc()).all()
    item_edit = None
    edit_area = ""
    edit_id = request.args.get("edit_id", type=int)
    if edit_id:
        item_edit = Usuario.query.get(edit_id)
        if item_edit:
            edit_area = (item_edit.area or "").strip()
    return render_template(
        "usuarios.html",
        users=users,
        areas=areas,
        item_edit=item_edit,
        edit_area=edit_area,
    )


@bp.route("/dashboard/<modulo_id>", methods=["GET", "POST"])
@login_required
@_require_current_area
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
    area_key = config.get("area_key")
    user_rol = (session.get("user_rol") or "usuario").strip().lower()
    user_area = (session.get("user_area") or "").strip()
    current_area = (session.get("current_area") or "").strip()
    can_edit = _user_can_edit()

    # POST: crear, editar o eliminar
    if request.method == "POST":
        if not can_edit:
            flash("No tiene permiso para realizar esta acción. Solo puede consultar.", "error")
            return redirect(url_for("main.modulo", modulo_id=modulo_id))

        eliminar_id = request.form.get("eliminar_id", type=int)
        edit_id = request.form.get("edit_id", type=int)
        next_page = max(1, request.form.get("page", 1, type=int))

        if eliminar_id:
            obj = Model.query.get(eliminar_id)
            if obj:
                if user_rol == "coordinador" and area_key and user_area:
                    if getattr(obj, area_key, None) != user_area:
                        flash("No puede eliminar registros de otra área.", "error")
                        return redirect(url_for("main.modulo", modulo_id=modulo_id, page=next_page))
                db.session.delete(obj)
                db.session.commit()
                flash("Registro eliminado.", "success")
            return redirect(url_for("main.modulo", modulo_id=modulo_id, page=next_page))

        if edit_id:
            obj = Model.query.get(edit_id)
            if not obj:
                flash("Registro no encontrado.", "error")
                return redirect(url_for("main.modulo", modulo_id=modulo_id))
            if user_rol == "coordinador" and area_key and user_area:
                if getattr(obj, area_key, None) != user_area:
                    flash("No puede editar registros de otra área.", "error")
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
            return redirect(url_for("main.modulo", modulo_id=modulo_id, page=next_page))

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
        # Asignar área actual en módulos con area_key
        if area_key and current_area and hasattr(obj, area_key):
            setattr(obj, area_key, current_area)
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

    # GET: listar con paginación filtrada por área actual y búsqueda
    query = Model.query
    if area_key and current_area and hasattr(Model, area_key):
        query = query.filter(getattr(Model, area_key) == current_area)
    search_q = (request.args.get("q") or "").strip()
    if search_q:
        from sqlalchemy import or_, cast, String
        search_conds = []
        for col in columnas:
            if not hasattr(Model, col["key"]):
                continue
            attr = getattr(Model, col["key"])
            try:
                search_conds.append(attr.ilike(f"%{search_q}%"))
            except Exception:
                try:
                    search_conds.append(cast(attr, String).ilike(f"%{search_q}%"))
                except Exception:
                    pass
        if search_conds:
            query = query.filter(or_(*search_conds))
    total = query.count()
    page = max(1, request.args.get("page", 1, type=int))
    total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
    page = min(page, total_pages)
    rows = (
        query.order_by(Model.id.desc())
        .limit(PER_PAGE)
        .offset((page - 1) * PER_PAGE)
        .all()
    )
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
            if user_rol == "coordinador" and area_key and user_area:
                if getattr(item_edit, area_key, None) != user_area:
                    item_edit = None
                    edit_data = {}
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
        can_edit=can_edit,
        page=page,
        total_pages=total_pages,
        total=total,
        per_page=PER_PAGE,
        search_q=search_q,
    )
