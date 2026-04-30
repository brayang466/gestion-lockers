import os
import re
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
    IngresoLockers, IngresoDotacion, AreaTrabajo, SecaBotasDisponibles,
)

bp = Blueprint("main", __name__)

DESPOSTE_AREAS = ("DESPOSTE", "DES", "CAL", "LYD", "SST", "MTTO", "LOG", "EXT", "TIC")
_DESPOSTE_CODES_UPPER = frozenset((a or "").upper() for a in DESPOSTE_AREAS)
# Códigos de subárea en planta Desposte (DES, LYD, CAL, …) — sin la palabra DESPOSTE como “subárea”
_DESPOSTE_SUBAREA_CODES = frozenset(x for x in _DESPOSTE_CODES_UPPER if x != "DESPOSTE")

# Cierre por inactividad (segundos). Valor prudente: 25 min.
IDLE_TIMEOUT_SECONDS = 25 * 60


@bp.before_app_request
def _idle_timeout_guard():
    """Cierra sesión si no hay actividad en un tiempo prudente."""
    path = (request.path or "").lower()
    if path.startswith("/static/"):
        return None
    if path in ("/login", "/acceso-integrado", "/logout"):
        return None
    if session.get("user_id") is None:
        return None
    now = int(datetime.utcnow().timestamp())
    last = session.get("last_activity_ts")
    try:
        last_i = int(last) if last is not None else None
    except Exception:
        last_i = None
    if last_i is not None and (now - last_i) > IDLE_TIMEOUT_SECONDS:
        session.clear()
        return redirect(url_for("main.login", reason="idle"))
    session["last_activity_ts"] = now
    return None


def _is_desposte_context(area):
    return ((area or "").strip().upper() == "DESPOSTE")


def _registro_manual_es_planta_desposte(current_area):
    """True si el alta manual corresponde a planta Desposte (sesión DESPOSTE o subárea LYD/CAL/…)."""
    ca_u = (current_area or "").strip().upper()
    return _is_desposte_context(current_area) or ca_u in _DESPOSTE_SUBAREA_CODES


def _lockers_por_sesion_filter(Model, current_area):
    """Lockers: sesión DESPOSTE = solo planta (area=DESPOSTE), independiente de otras áreas generales.

    Sesión LYD/CAL/… (código de subárea): unión de (1) lockers con area=DESPOSTE y subárea = sesión
    y (2) lockers con area = código de sesión (área general), sin mezclar otras subáreas."""
    from sqlalchemy import and_, or_

    ca_u = (current_area or "").strip().upper()
    if not ca_u:
        return None
    a = getattr(Model, "area")
    sub = getattr(Model, "subarea", None)
    if ca_u == "DESPOSTE":
        return db.func.upper(db.func.trim(a)) == "DESPOSTE"
    if sub is not None and ca_u in _DESPOSTE_SUBAREA_CODES:
        return or_(
            and_(
                db.func.upper(db.func.trim(a)) == "DESPOSTE",
                db.func.upper(db.func.trim(sub)) == ca_u,
            ),
            db.func.upper(db.func.trim(a)) == ca_u,
        )
    return getattr(Model, "area") == current_area


def _registro_area_scope_filter(Model, current_area):
    """Filtra registro/historial por área de sesión, sin cruzar Desposte con otras áreas generales.

    - Sesión DESPOSTE: solo filas `es_planta_desposte` del CSV/import de planta y área en subáreas DESPOSTE.
      El CSV general puede repetir códigos (LYD, LOG…); no entran aquí.
    - Sesión LYD/CAL/… (subárea): unión de registro “general” (mismo código en area/area_lockers)
      y asignaciones ligadas a locker en planta Desposte con esa misma subárea (no CAL≠LYD).
    - CALIDAD / LOGISTICA / BENEFICIO (nombre en sesión): el CSV general suele traer CAL / LOG / LN;
      se cruza con es_planta_desposte=False para CAL/LOG (no mezclar con subáreas de planta)."""
    from sqlalchemy import and_, or_, exists, select, true as sql_true

    ca = (current_area or "").strip().upper()
    if not ca:
        return None
    ac = getattr(Model, "area")
    if _is_desposte_context(current_area):
        flag = getattr(Model, "es_planta_desposte", None)
        zone = db.func.upper(db.func.trim(ac)).in_(DESPOSTE_AREAS)
        if flag is not None:
            return and_(flag.is_(True), zone)
        return zone

    tu = db.func.upper(db.func.trim(ac))
    flag = getattr(Model, "es_planta_desposte", None)

    def _no_es_planta_desposte():
        if flag is None:
            return sql_true()
        return or_(flag.is_(False), flag.is_(None))

    # Área en sesión = nombre largo (area_trabajo); CSV histórico = código corto.
    if ca == "CALIDAD":
        return or_(tu == "CALIDAD", and_(tu == "CAL", _no_es_planta_desposte()))
    if ca == "LOGISTICA":
        return or_(tu == "LOGISTICA", and_(tu == "LOG", _no_es_planta_desposte()))
    if ca == "BENEFICIO":
        return or_(tu == "BENEFICIO", tu == "LN")

    cond = tu == ca

    if ca in _DESPOSTE_SUBAREA_CODES:
        lk = getattr(Model, "area_lockers", None)
        if lk is not None:
            cond = or_(cond, db.func.upper(db.func.trim(lk)) == ca)
        if hasattr(Model, "codigo_lockets"):
            cod_col = getattr(Model, "codigo_lockets")
            locker_sub = exists(
                select(1).where(
                    BaseLockers.codigo == cod_col,
                    db.func.upper(db.func.trim(BaseLockers.area)) == "DESPOSTE",
                    db.func.upper(db.func.trim(BaseLockers.subarea)) == ca,
                )
            )
            cond = or_(cond, locker_sub)
        return cond

    return tu == ca


def _normalize_estado_base_lockers(estado):
    """En base_lockers: quita prefijo LOCKERT; normaliza a DISPONIBLE, ASIGNADO o VISITA."""
    if not estado or not isinstance(estado, str):
        return "DISPONIBLE"
    s = estado.strip()
    s = re.sub(r"^LOCKERT\s*", "", s, flags=re.IGNORECASE).strip()
    if not s:
        return "DISPONIBLE"
    u = s.upper()
    if u in ("DISPONIBLE", "ASIGNADO", "VISITA"):
        return u
    if u == "ASIGNADA":
        return "ASIGNADO"
    return u


def _normalize_estado_seca_botas(estado):
    """Normaliza estado para seca_botas: devuelve solo ASIGNADO o DISPONIBLE."""
    if not estado or not isinstance(estado, str):
        return "DISPONIBLE"
    s = estado.strip()
    if not s:
        return "DISPONIBLE"
    u = s.upper()
    if u in ("DISPONIBLE", "ASIGNADO"):
        return u
    if u == "ASIGNADA":
        return "ASIGNADO"
    if "DISP" in u:
        return "DISPONIBLE"
    if "ASIG" in u:
        return "ASIGNADO"
    return "DISPONIBLE"


def _normalize_estado_base_dotaciones(estado):
    """Normaliza estado de base_dotaciones: quita DOTACION, 'NO HAY ESE CODIGO' -> 'NO EXISTE'; devuelve ASIGNADA/DISPONIBLE/NO EXISTE."""
    if not estado or not isinstance(estado, str):
        return "DISPONIBLE"
    s = estado.strip()
    if re.search(r"no\s*hay\s*ese\s*codigo", s, re.IGNORECASE):
        return "NO EXISTE"
    s = re.sub(r"^DOTACION\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s*DOTACION\s*$", "", s, flags=re.IGNORECASE).strip()
    if not s:
        return "DISPONIBLE"
    u = s.upper()
    if u in ("ASIGNADA", "DISPONIBLE", "NO EXISTE"):
        return u
    return s


def _norm_codigo_cmp(codigo):
    """Trim + minúsculas para detectar códigos duplicados."""
    return (codigo or "").strip().lower()


def _codigo_base_dotaciones_duplicado(codigo, exclude_id=None):
    c = _norm_codigo_cmp(codigo)
    if not c:
        return False
    q = BaseDotaciones.query.filter(db.func.lower(db.func.trim(BaseDotaciones.codigo)) == c)
    if exclude_id is not None:
        q = q.filter(BaseDotaciones.id != exclude_id)
    return q.first() is not None


def _codigo_base_lockers_duplicado(codigo, exclude_id=None):
    c = _norm_codigo_cmp(codigo)
    if not c:
        return False
    q = BaseLockers.query.filter(db.func.lower(db.func.trim(BaseLockers.codigo)) == c)
    if exclude_id is not None:
        q = q.filter(BaseLockers.id != exclude_id)
    return q.first() is not None


def _codigo_locker_disponibles_duplicado(codigo, exclude_id=None):
    c = _norm_codigo_cmp(codigo)
    if not c:
        return False
    q = LockerDisponibles.query.filter(db.func.lower(db.func.trim(LockerDisponibles.codigo)) == c)
    if exclude_id is not None:
        q = q.filter(LockerDisponibles.id != exclude_id)
    return q.first() is not None


def _get_next_id_asignaciones():
    """Devuelve el siguiente ID en formato ASG-000, ASG-001, ... para RegistroAsignaciones. Regla: al insertar aplicar este formato."""
    rows = (
        RegistroAsignaciones.query.with_entities(RegistroAsignaciones.id_asignaciones)
        .filter(RegistroAsignaciones.id_asignaciones.isnot(None))
        .filter(RegistroAsignaciones.id_asignaciones != "")
        .all()
    )
    max_num = -1
    for (val,) in rows:
        if not val:
            continue
        m = re.match(r"^ASG-(\d+)$", (val or "").strip(), re.IGNORECASE)
        if m:
            try:
                max_num = max(max_num, int(m.group(1)))
            except ValueError:
                pass
    return "ASG-{:03d}".format(max_num + 1)


def _codigo_dotacion_disponible(codigo, area=None):
    """True si el código existe en Base de Dotaciones con estado DISPONIBLE. Si area='DESPOSTE' solo busca en dotaciones DESPOSTE; si area es otra, excluye DESPOSTE."""
    if not (codigo or "").strip():
        return True
    q = BaseDotaciones.query.filter(
        BaseDotaciones.codigo == (codigo or "").strip(),
        BaseDotaciones.estado.ilike("%disponible%"),
    ).filter(~BaseDotaciones.estado.ilike("%asignada%"))
    if area == "DESPOSTE":
        q = q.filter(BaseDotaciones.area_uso == "DESPOSTE")
    elif area:
        q = q.filter(BaseDotaciones.area_uso != "DESPOSTE")
    return q.first() is not None


def _codigo_locker_disponible(codigo):
    """True si el código existe en Lockers Disponibles con estado DISPONIBLE."""
    if not (codigo or "").strip():
        return True
    return (
        LockerDisponibles.query.filter_by(codigo=(codigo or "").strip())
        .filter(db.func.lower(LockerDisponibles.estado) == "disponible")
        .first()
        is not None
    )


def _marcar_dotacion_asignada(codigo, area=None):
    """Marca la primera dotación disponible con ese código como ASIGNADA en BaseDotaciones. Si area='DESPOSTE' solo toca dotaciones DESPOSTE."""
    if not (codigo or "").strip():
        return
    q = (
        BaseDotaciones.query.filter(BaseDotaciones.codigo == (codigo or "").strip())
        .filter(BaseDotaciones.estado.ilike("%disponible%"))
        .filter(~BaseDotaciones.estado.ilike("%asignada%"))
    )
    if area == "DESPOSTE":
        q = q.filter(BaseDotaciones.area_uso == "DESPOSTE")
    elif area:
        q = q.filter(BaseDotaciones.area_uso != "DESPOSTE")
    reg = q.first()
    if reg:
        reg.estado = "ASIGNADA"


def _marcar_locker_asignado(codigo, area=None):
    """Marca el locker con ese código como ASIGNADO en LockerDisponibles y en Base de Lockers."""
    if not (codigo or "").strip():
        return
    cod = (codigo or "").strip()
    reg = (
        LockerDisponibles.query.filter_by(codigo=cod)
        .filter(db.func.lower(LockerDisponibles.estado) == "disponible")
        .first()
    )
    if reg:
        reg.estado = "ASIGNADO"
    q_base = BaseLockers.query.filter(BaseLockers.codigo == cod)
    if area:
        lf = _lockers_por_sesion_filter(BaseLockers, area)
        if lf is not None:
            q_base = q_base.filter(lf)
    reg_base = q_base.filter(db.func.lower(BaseLockers.estado) == "disponible").first()
    if reg_base:
        reg_base.estado = "ASIGNADO"


def _liberar_dotacion(codigo, area=None):
    """Vuelve a DISPONIBLE la dotación con ese código en BaseDotaciones. Si area='DESPOSTE' solo toca dotaciones DESPOSTE."""
    if not (codigo or "").strip():
        return
    q = BaseDotaciones.query.filter(BaseDotaciones.codigo == (codigo or "").strip()).filter(BaseDotaciones.estado.ilike("%asignada%"))
    if area == "DESPOSTE":
        q = q.filter(BaseDotaciones.area_uso == "DESPOSTE")
    elif area:
        q = q.filter(BaseDotaciones.area_uso != "DESPOSTE")
    reg = q.first()
    if reg:
        reg.estado = "DISPONIBLE"


def _liberar_locker(codigo, area=None):
    """Vuelve a DISPONIBLE el locker con ese código en LockerDisponibles y en Base de Lockers."""
    if not (codigo or "").strip():
        return
    cod = (codigo or "").strip()
    reg = LockerDisponibles.query.filter_by(codigo=cod).first()
    if reg:
        reg.estado = "disponible"
    q_base = BaseLockers.query.filter(BaseLockers.codigo == cod)
    if area:
        lf = _lockers_por_sesion_filter(BaseLockers, area)
        if lf is not None:
            q_base = q_base.filter(lf)
    for reg_base in q_base.filter(BaseLockers.estado.ilike("%asignado%")).all():
        reg_base.estado = "disponible"


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


# Opciones estándar para campos de talla (formularios de encabezado y módulos)
TALLAS_SELECT_OPCIONES = ["", "M", "L", "S", "XXL", "XL", "XXXL", "XS", "S-M-L-XL"]

MODULOS_CONFIG = {
    "base-lockers": {
        "model": BaseLockers,
        "titulo": "Base de Lockers",
        "icon": "locker",
        "area_key": "area",
        "columnas": [
            {"key": "codigo", "label": "Código"},
            {"key": "area", "label": "Área"},
            {"key": "subarea", "label": "Subárea (ubic. Desposte)"},
            {"key": "area_lockers", "label": "Área Lockers"},
            {"key": "estado", "label": "Estado"},
            {"key": "unidad", "label": "Unidad"},
        ],
        "form_fields": [
            {"name": "codigo", "label": "Código", "type": "text", "required": True},
            {"name": "area", "label": "Área", "type": "text"},
            {"name": "subarea", "label": "Subárea (ubic. Desposte)", "type": "text"},
            {"name": "area_lockers", "label": "Área Lockers", "type": "text"},
            {"name": "estado", "label": "Estado", "type": "select", "options": ["DISPONIBLE", "ASIGNADO", "VISITA"]},
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
        "no_crear": True,
        "solo_lectura": True,
        "solo_estado_disponible_locker": True,
        "columnas": [
            {"key": "codigo", "label": "Código"},
            {"key": "area", "label": "Área"},
            {"key": "subarea", "label": "Subárea (ubic. Desposte)"},
            {"key": "area_lockers", "label": "Área Lockers"},
            {"key": "estado", "label": "Estado"},
        ],
        "form_fields": [
            {"name": "codigo", "label": "Código", "type": "text", "required": True},
            {"name": "area", "label": "Área", "type": "text"},
            {"name": "subarea", "label": "Subárea (ubic. Desposte)", "type": "text"},
            {"name": "area_lockers", "label": "Área Lockers", "type": "text"},
            {"name": "estado", "label": "Estado", "type": "select", "options": ["DISPONIBLE", "ASIGNADO"]},
            {"name": "observaciones", "label": "Observaciones", "type": "textarea"},
        ],
        "date_fields": [],
    },
    "seca-botas-disponibles": {
        "model": SecaBotasDisponibles,
        "titulo": "Seca Botas Disponibles",
        "icon": "boot",
        "area_key": "area",
        "no_crear": True,
        "solo_lectura": True,
        "solo_estado_disponible_seca_botas": True,
        "columnas": [
            {"key": "codigo", "label": "CODIGO"},
            {"key": "area", "label": "AREA"},
            {"key": "area_locker", "label": "AREA LOCKER"},
        ],
        "form_fields": [
            {"name": "codigo", "label": "CODIGO", "type": "text", "required": True},
            {"name": "area", "label": "AREA", "type": "select", "options": []},
            {"name": "area_locker", "label": "AREA LOCKER", "type": "text"},
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
            {"key": "area_uso", "label": "Área uso"},
            {"key": "cantidad", "label": "Cantidad"},
            {"key": "talla", "label": "Talla"},
            {"key": "estado", "label": "Estado"},
        ],
        "form_fields": [
            {"name": "codigo", "label": "Código", "type": "text"},
            {"name": "cantidad", "label": "Cantidad", "type": "number"},
            {"name": "area_uso", "label": "Área uso", "type": "text"},
            {"name": "talla", "label": "Talla", "type": "select", "options": TALLAS_SELECT_OPCIONES},
            {"name": "estado", "label": "Estado", "type": "select", "options": ["ASIGNADA", "DISPONIBLE", "NO EXISTE"]},
        ],
        "date_fields": [],
    },
    "dotaciones-disponibles": {
        "model": BaseDotaciones,
        "titulo": "Dotaciones Disponibles",
        "icon": "boxes",
        "area_key": None,
        "no_crear": True,
        "solo_lectura": True,
        "solo_estado_disponible": True,
        "columnas": [
            {"key": "codigo", "label": "Código"},
            {"key": "talla", "label": "Talla"},
            {"key": "cantidad", "label": "Cantidad"},
        ],
        "form_fields": [],
        "date_fields": [],
    },
    "registro-personal": {
        "model": RegistroAsignaciones,
        "titulo": "Personal Pendiente",
        "icon": "users",
        "area_key": "area",
        "no_crear": True,
        "solo_sin_asignacion": True,
        "columnas": [
            {"key": "operario", "label": "Nombre"},
            {"key": "identificacion", "label": "Documento"},
            {"key": "area", "label": "Área"},
            {"key": "area_lockers", "label": "Área Lockers"},
            {"key": "estado", "label": "Estado"},
        ],
        "form_fields": [
            {"name": "operario", "label": "Nombre", "type": "text", "required": True},
            {"name": "identificacion", "label": "Documento", "type": "text", "required": True},
            {"name": "area", "label": "Área", "type": "text"},
            {"name": "talla_operarios", "label": "Talla", "type": "select", "options": TALLAS_SELECT_OPCIONES},
            {"name": "area_lockers", "label": "Área Lockers", "type": "text"},
            {"name": "codigo_lockets", "label": "Código lockers", "type": "text"},
            {"name": "codigo_dotacion", "label": "Código dotación", "type": "text"},
            {"name": "estado", "label": "Estado", "type": "select", "options": ["ACTIVO", "INACTIVO", "PENDIENTE"]},
            {"name": "observaciones", "label": "Observaciones", "type": "textarea"},
        ],
        "date_fields": [],
    },
    "personal-presupuestado": {
        "model": PersonalPresupuestado,
        "titulo": "Personal Presupuestado",
        "icon": "user-group",
        "area_key": None,
        "no_crear": True,
        "columnas": [
            {"key": "area", "label": "Área"},
            {"key": "aprobados", "label": "Aprobados"},
            {"key": "contratados", "label": "Contratados"},
            {"key": "por_contratar", "label": "Por contratar"},
        ],
        "form_fields": [
            {"name": "area", "label": "Área", "type": "text"},
            {"name": "aprobados", "label": "Aprobados", "type": "number"},
            {"name": "contratados", "label": "Contratados", "type": "number"},
            {"name": "por_contratar", "label": "Por contratar", "type": "number"},
        ],
        "date_fields": [],
    },
    "registro-asignaciones": {
        "model": RegistroAsignaciones,
        "titulo": "Registro de Asignaciones",
        "icon": "clipboard-check",
        "area_key": "area",
        "solo_con_asignacion": True,
        "no_crear": True,
        "columnas": [
            {"key": "identificacion", "label": "Identificación"},
            {"key": "operario", "label": "Operario"},
            {"key": "area", "label": "Área"},
            {"key": "talla_operarios", "label": "Talla"},
            {"key": "talla_dotacion", "label": "Talla Dotación Asignada"},
            {"key": "area_lockers", "label": "Área de Lockers"},
            {"key": "codigo_dotacion", "label": "Cód. Dotación"},
            {"key": "codigo_lockets", "label": "Cód. Lockers"},
            {"key": "codigo_seca_botas", "label": "Cód. Seca Botas"},
            {"key": "fecha_entrega", "label": "Fecha de Entrega"},
            {"key": "estado", "label": "Estado"},
        ],
        "form_fields": [
            {"name": "codigo_dotacion", "label": "Código dotación", "type": "text"},
            {"name": "fecha_asignacion", "label": "Fecha asignación", "type": "date"},
            {"name": "fecha_entrega", "label": "Fecha entrega", "type": "date"},
            {"name": "operario", "label": "Operario", "type": "text"},
            {"name": "identificacion", "label": "Identificación", "type": "text", "required": True},
            {"name": "codigo_lockets", "label": "Código lockers", "type": "text"},
            {"name": "codigo_seca_botas", "label": "Cód. Seca Botas", "type": "text"},
            {"name": "area", "label": "Área", "type": "text"},
            {"name": "talla_operarios", "label": "Talla operarios", "type": "select", "options": TALLAS_SELECT_OPCIONES},
            {"name": "talla_dotacion", "label": "Talla dotación", "type": "select", "options": TALLAS_SELECT_OPCIONES},
            {"name": "area_lockers", "label": "Área lockers", "type": "text"},
            {"name": "estado", "label": "Estado", "type": "select", "options": ["ACTIVO", "INACTIVO", "PENDIENTE"]},
            {"name": "observaciones", "label": "Observaciones", "type": "textarea"},
        ],
        "date_fields": ["fecha_asignacion", "fecha_entrega"],
    },
    "historial-retiros": {
        "model": HistorialRetiros,
        "titulo": "Historial de Retiros",
        "icon": "archive",
        "area_key": "area",
        "no_crear": True,
        "solo_lectura": False,
        "columnas": [
            {"key": "identificacion", "label": "Identificación"},
            {"key": "operario", "label": "Operario"},
            {"key": "codigo_lockets", "label": "Cód Lockers"},
            {"key": "area", "label": "Área"},
            {"key": "area_lockers", "label": "Área Lockers"},
            {"key": "codigo_dotacion", "label": "Cód. Dotación"},
            {"key": "fecha_retiro", "label": "Fecha retiro"},
            {"key": "observaciones", "label": "Observaciones"},
        ],
        "form_fields": [
            {"name": "identificacion", "label": "Identificación", "type": "text"},
            {"name": "codigo_dotacion", "label": "Código dotación", "type": "text"},
            {"name": "fecha_retiro", "label": "Fecha retiro", "type": "date"},
            {"name": "operario", "label": "Operario", "type": "text"},
            {"name": "codigo_lockets", "label": "Código lockers", "type": "text"},
            {"name": "area", "label": "Área", "type": "text"},
            {"name": "talla_operarios", "label": "Talla operarios", "type": "select", "options": TALLAS_SELECT_OPCIONES},
            {"name": "talla_dotacion", "label": "Talla dotación", "type": "select", "options": TALLAS_SELECT_OPCIONES},
            {"name": "area_lockers", "label": "Área lockers", "type": "text"},
            {"name": "observaciones", "label": "Observaciones", "type": "textarea"},
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

# Orden de módulos en el menú (sidebar y todas las áreas)
MODULOS_ORDER = [
    "dotaciones-disponibles",
    "locker-disponibles",
    "seca-botas-disponibles",
    "historial-retiros",
    "ingreso-lockers",
    "ingreso-dotacion",
    "base-lockers",
    "base-dotaciones",
    "registro-personal",
    "personal-presupuestado",
    "registro-asignaciones",
]
_MODULOS_RAW = dict(MODULOS_CONFIG)
MODULOS_CONFIG = {k: _MODULOS_RAW[k] for k in MODULOS_ORDER}


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
    if request.method == "GET" and request.args.get("reason") == "idle":
        flash("Tu sesión se cerró por inactividad. Por favor inicia sesión de nuevo.", "error")
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
        session["session_started_ts_ms"] = int(datetime.utcnow().timestamp() * 1000)
        session.pop("current_area", None)
        session.pop("logout_to_integrado", None)
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


@bp.route("/acceso-integrado", methods=["GET", "POST"])
def acceso_integrado():
    """Entrada desde otro aplicativo: perfiles + contraseña (misma validación que /login)."""
    if session.get("user_id"):
        return redirect(url_for("main.dashboard"))
    if request.method == "GET" and request.args.get("reason") == "idle":
        flash("Tu sesión se cerró por inactividad. Por favor inicia sesión de nuevo.", "error")

    def _usuarios_activos():
        return (
            Usuario.query.filter_by(activo=True)
            .order_by(Usuario.nombre.asc())
            .all()
        )

    if request.method == "POST":
        try:
            user_id = int(request.form.get("user_id") or 0)
        except (TypeError, ValueError):
            user_id = 0
        password = request.form.get("password") or ""
        usuarios = _usuarios_activos()

        if not user_id or not password:
            flash("Selecciona un perfil e ingresa tu contraseña.", "error")
            return render_template(
                "login_integrado.html",
                usuarios=usuarios,
                selected_user_id=user_id if user_id else None,
            )

        user = Usuario.query.filter_by(id=user_id, activo=True).first()
        if not user or not user.password_hash:
            flash("Perfil o contraseña incorrectos.", "error")
            return render_template(
                "login_integrado.html",
                usuarios=usuarios,
                selected_user_id=user_id,
            )

        if not check_password_hash(user.password_hash, password):
            flash("Contraseña incorrecta.", "error")
            palabra_clave_hint = (
                (user.palabra_clave or "").strip()
                if getattr(user, "palabra_clave", None)
                else ""
            )
            return render_template(
                "login_integrado.html",
                usuarios=usuarios,
                selected_user_id=user_id,
                palabra_clave_hint=palabra_clave_hint,
            )

        session["user_id"] = user.id
        session["user_nombre"] = user.nombre or user.email
        session["user_rol"] = (user.rol or "usuario").strip().lower()
        session["user_area"] = (user.area or "").strip()
        session["session_started_ts_ms"] = int(datetime.utcnow().timestamp() * 1000)
        session.pop("current_area", None)
        session["logout_to_integrado"] = True
        return redirect(url_for("main.areas"))

    usuarios = _usuarios_activos()
    return render_template("login_integrado.html", usuarios=usuarios)


@bp.route("/logout")
def logout():
    to_integrado = bool(session.get("logout_to_integrado"))
    session.clear()
    if to_integrado:
        return redirect(url_for("main.acceso_integrado"))
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
    """Áreas a las que el usuario puede entrar. Superadmin y Admin: todas; otro: solo su área asignada."""
    rol = (session.get("user_rol") or "usuario").strip().lower()
    user_area = (session.get("user_area") or "").strip()
    if rol in ("superadmin", "admin"):
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


@bp.route("/dashboard/api/verificar-codigos")
@login_required
@_require_current_area
def api_verificar_codigos():
    """Devuelve si codigo_dotacion y codigo_lockets están disponibles (en Dotaciones/Lockers Disponibles) o asignados."""
    from flask import jsonify
    current_area = (session.get("current_area") or "").strip()
    cod_dot = (request.args.get("codigo_dotacion") or "").strip()
    cod_lock = (request.args.get("codigo_lockets") or "").strip()
    out = {}
    if cod_dot:
        out["codigo_dotacion"] = "disponible" if _codigo_dotacion_disponible(cod_dot, area=current_area) else "asignado"
    else:
        out["codigo_dotacion"] = None
    if cod_lock:
        out["codigo_lockets"] = "disponible" if _codigo_locker_disponible(cod_lock) else "asignado"
    else:
        out["codigo_lockets"] = None
    return jsonify(out)


def _dashboard_stats(current_area):
    """Calcula estadísticas del dashboard para un área. Usado por dashboard() y por api_dashboard_stats()."""
    from sqlalchemy import func, or_, and_, false
    # Total lockers: siempre desde BaseLockers (fuente de verdad).
    lf_base = _lockers_por_sesion_filter(BaseLockers, current_area)
    q_base = BaseLockers.query.filter(lf_base) if lf_base is not None else BaseLockers.query.filter(false())
    total_lockers = q_base.count()

    # Lockers disponibles: por regla de negocio = BaseLockers estado DISPONIBLE (áreas generales; DESPOSTE por filtro de sesión).
    disponibles = q_base.filter(db.func.lower(BaseLockers.estado) == "disponible").count()
    q_dot = BaseDotaciones.query
    if current_area == "DESPOSTE":
        q_dot = q_dot.filter(BaseDotaciones.area_uso == "DESPOSTE")
    else:
        q_dot = q_dot.filter(BaseDotaciones.area_uso != "DESPOSTE")
    total_dotaciones = q_dot.count()
    # En stock: dotaciones DISPONIBLES que NO estén asignadas en RegistroAsignaciones (áreas generales; DESPOSTE se maneja aparte).
    q_dot_disp = q_dot.filter(db.func.lower(BaseDotaciones.estado) == "disponible")
    if not _is_desposte_context(current_area):
        scope_ra = _registro_area_scope_filter(RegistroAsignaciones, current_area)
        if scope_ra is not None:
            assigned_codes_sq = (
                RegistroAsignaciones.query.filter(scope_ra)
                .filter(RegistroAsignaciones.codigo_dotacion.isnot(None), RegistroAsignaciones.codigo_dotacion != "")
                .with_entities(RegistroAsignaciones.codigo_dotacion)
                .distinct()
                .subquery()
            )
            q_dot_disp = q_dot_disp.filter(~BaseDotaciones.codigo.in_(assigned_codes_sq))
    dotaciones_disponibles = q_dot_disp.count()

    # Personal presupuestado (por área; DESPOSTE excluido)
    personal_presupuestado = {"aprobados": 0, "contratados": 0, "por_contratar": 0}
    ca_u = (current_area or "").strip().upper()
    if ca_u and ca_u != "DESPOSTE":
        pp = (
            PersonalPresupuestado.query.filter(db.func.upper(db.func.trim(PersonalPresupuestado.area)) == ca_u)
            .first()
        )
        if pp:
            personal_presupuestado = {
                "aprobados": int(getattr(pp, "aprobados", 0) or 0),
                "contratados": int(getattr(pp, "contratados", 0) or 0),
                "por_contratar": int(getattr(pp, "por_contratar", 0) or 0),
            }
    sin_asig = and_(
        or_(RegistroAsignaciones.codigo_lockets.is_(None), RegistroAsignaciones.codigo_lockets == ""),
        or_(RegistroAsignaciones.codigo_dotacion.is_(None), RegistroAsignaciones.codigo_dotacion == ""),
    )
    con_asig = or_(
        and_(RegistroAsignaciones.codigo_lockets.isnot(None), RegistroAsignaciones.codigo_lockets != ""),
        and_(RegistroAsignaciones.codigo_dotacion.isnot(None), RegistroAsignaciones.codigo_dotacion != ""),
    )
    if _is_desposte_context(current_area):
        desposte_ra = and_(
            RegistroAsignaciones.es_planta_desposte.is_(True),
            db.func.upper(RegistroAsignaciones.area).in_(DESPOSTE_AREAS),
        )
        total_personal = RegistroAsignaciones.query.filter(desposte_ra, sin_asig).count()
        total_asignaciones = RegistroAsignaciones.query.filter(desposte_ra, con_asig).count()
        total_retiros = HistorialRetiros.query.filter(
            HistorialRetiros.es_planta_desposte.is_(True),
            db.func.upper(HistorialRetiros.area).in_(DESPOSTE_AREAS),
        ).count()
    else:
        scope_ra = _registro_area_scope_filter(RegistroAsignaciones, current_area)
        scope_hr = _registro_area_scope_filter(HistorialRetiros, current_area)
        total_personal = (
            RegistroAsignaciones.query.filter(scope_ra, sin_asig).count() if scope_ra is not None else 0
        )
        total_asignaciones = (
            RegistroAsignaciones.query.filter(scope_ra, con_asig).count() if scope_ra is not None else 0
        )
        total_retiros = HistorialRetiros.query.filter(scope_hr).count() if scope_hr is not None else 0
    today = datetime.utcnow().date()
    seven_days_ago = today - timedelta(days=6)
    if _is_desposte_context(current_area):
        chart_query = db.session.query(
            func.date(RegistroAsignaciones.creado_en).label("d"),
            func.count(RegistroAsignaciones.id).label("c"),
        ).filter(
            RegistroAsignaciones.es_planta_desposte.is_(True),
            db.func.upper(RegistroAsignaciones.area).in_(DESPOSTE_AREAS),
            func.date(RegistroAsignaciones.creado_en) >= seven_days_ago,
        )
        chart_by_date = dict(chart_query.group_by(func.date(RegistroAsignaciones.creado_en)).all())
    else:
        scope_chart = _registro_area_scope_filter(RegistroAsignaciones, current_area)
        if scope_chart is None:
            chart_by_date = {}
        else:
            chart_by_date = dict(
                db.session.query(
                    func.date(RegistroAsignaciones.creado_en).label("d"),
                    func.count(RegistroAsignaciones.id).label("c"),
                )
                .filter(
                    scope_chart,
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
    return {
        "total_lockers": total_lockers,
        "disponibles": disponibles,
        "total_dotaciones": total_dotaciones,
        "dotaciones_disponibles": dotaciones_disponibles,
        "total_personal": total_personal,
        "total_asignaciones": total_asignaciones,
        "total_retiros": total_retiros,
        "personal_presupuestado": personal_presupuestado,
        "chart_labels": chart_labels,
        "chart_data": chart_data,
    }


@bp.route("/dashboard/api/stats")
@login_required
@_require_current_area
def api_dashboard_stats():
    """Devuelve las estadísticas del dashboard en JSON para actualización en tiempo real."""
    from flask import jsonify
    current_area = (session.get("current_area") or "").strip()
    stats = _dashboard_stats(current_area)
    return jsonify(stats)


@bp.route("/dashboard")
@login_required
@_require_current_area
def dashboard():
    current_area = (session.get("current_area") or "").strip()
    stats = _dashboard_stats(current_area)
    total_lockers = stats["total_lockers"]
    disponibles = stats["disponibles"]
    total_dotaciones = stats["total_dotaciones"]
    dotaciones_disponibles = stats["dotaciones_disponibles"]
    total_personal = stats["total_personal"]
    total_asignaciones = stats["total_asignaciones"]
    total_retiros = stats["total_retiros"]
    chart_labels = stats["chart_labels"]
    chart_data = stats["chart_data"]
    es_superadmin = (session.get("user_rol") or "").strip().lower() == "superadmin"
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
    # Listado del sidebar: sin Ingreso de Lockers ni Ingreso de Dotación (acceso por botones del encabezado)
    modulos_sidebar = {k: v for k, v in MODULOS_CONFIG.items() if k not in ("ingreso-lockers", "ingreso-dotacion")}
    return render_template(
        "dashboard.html",
        total_lockers=total_lockers,
        disponibles=disponibles,
        total_dotaciones=total_dotaciones,
        dotaciones_disponibles=dotaciones_disponibles,
        total_personal=total_personal,
        total_asignaciones=total_asignaciones,
        total_retiros=total_retiros,
        modulos_config=modulos_sidebar,
        show_usuarios_module=es_superadmin,
        chart_labels=chart_labels,
        chart_data=chart_data,
        module_categories=MODULE_CATEGORIES,
        unique_categories=unique_categories,
        current_area=current_area,
    )


def _user_can_edit():
    """Usuario: solo consulta. Admin, coordinador y superadmin: pueden agregar, editar y eliminar en módulos."""
    return (session.get("user_rol") or "usuario").strip().lower() in ("superadmin", "admin", "coordinador")


def _superadmin_required(f):
    """Decorator: solo superadmin (acceso a Gestión de usuarios)."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect(url_for("main.login"))
        if (session.get("user_rol") or "").strip().lower() != "superadmin":
            flash("Solo el Super Administrador puede acceder a la gestión de usuarios.", "error")
            return redirect(url_for("main.dashboard"))
        return f(*args, **kwargs)
    return decorated


@bp.route("/dashboard/usuarios", methods=["GET", "POST"])
@login_required
@_superadmin_required
def usuarios():
    """Módulo solo superadmin: listar usuarios, editar info, cambiar rol, inactivar/activar y eliminar."""
    ROLES_VALIDOS = ["superadmin", "admin", "coordinador", "usuario"]
    areas = AreaTrabajo.query.order_by(AreaTrabajo.nombre).all()
    if request.method == "POST":
        # Eliminar usuario
        eliminar_id = request.form.get("eliminar_usuario_id", type=int)
        if eliminar_id:
            if eliminar_id == session.get("user_id"):
                flash("No puedes eliminar tu propia cuenta.", "error")
            else:
                user = Usuario.query.get(eliminar_id)
                if user:
                    db.session.delete(user)
                    db.session.commit()
                    flash("Usuario eliminado.", "success")
            return redirect(url_for("main.usuarios"))

        # Activar/Inactivar
        toggle_id = request.form.get("toggle_activo_id", type=int)
        if toggle_id:
            user = Usuario.query.get(toggle_id)
            if user:
                nuevo_activo = not user.activo
                Usuario.query.filter_by(id=toggle_id).update({"activo": nuevo_activo}, synchronize_session=False)
                db.session.commit()
                estado = "activado" if nuevo_activo else "inactivado"
                flash(f"Usuario {estado} correctamente.", "success")
            return redirect(url_for("main.usuarios"))

        # Editar información del usuario (nombre, email, área, rol)
        edit_id = request.form.get("edit_id", type=int)
        if edit_id:
            user = Usuario.query.get(edit_id)
            if user:
                user.nombre = (request.form.get("nombre") or "").strip() or user.nombre
                user.email = (request.form.get("email") or "").strip() or user.email
                rol_val = (request.form.get("rol") or "").strip().lower()
                if rol_val in ROLES_VALIDOS:
                    user.rol = rol_val
                if rol_val in ("superadmin", "admin"):
                    user.area = ""
                else:
                    user.area = (request.form.get("area") or "").strip()
                db.session.commit()
                flash("Información del usuario actualizada.", "success")
            return redirect(url_for("main.usuarios"))

    users = Usuario.query.order_by(Usuario.creado_en.desc()).all()
    item_edit = None
    edit_id = request.args.get("edit_id", type=int)
    if edit_id:
        item_edit = Usuario.query.get(edit_id)
    return render_template(
        "usuarios.html",
        users=users,
        areas=areas,
        item_edit=item_edit,
        roles_validos=ROLES_VALIDOS,
    )


def _registro_form_view(modulo_id):
    """Vistas independientes de solo formulario: Ingreso dotación → BaseDotaciones; Registro personal → RegistroAsignaciones; Ingreso lockers → BaseLockers."""
    current_area = (session.get("current_area") or "").strip()
    if not current_area:
        flash("Selecciona un área de trabajo.", "error")
        return redirect(url_for("main.areas"))
    can_edit = _user_can_edit()
    if request.method == "POST" and can_edit:
        if modulo_id == "ingreso-dotacion":
            codigo = (request.form.get("codigo") or "").strip()
            cantidad = request.form.get("cantidad", type=int) or 0
            talla = (request.form.get("talla") or "").strip()
            area_uso = (request.form.get("area") or "").strip()
            if not codigo:
                flash("El código es obligatorio.", "error")
                return render_template("registro_form.html", modulo_id=modulo_id, titulo="Ingreso de Dotación", form_fields=_FORM_INGRESO_DOTACION, can_edit=can_edit)
            if not talla:
                flash("Seleccione una talla.", "error")
                return render_template("registro_form.html", modulo_id=modulo_id, titulo="Ingreso de Dotación", form_fields=_FORM_INGRESO_DOTACION, can_edit=can_edit)
            if area_uso not in INGRESO_DOTACION_AREA_OPCIONES:
                flash("Seleccione un área válida.", "error")
                return render_template("registro_form.html", modulo_id=modulo_id, titulo="Ingreso de Dotación", form_fields=_FORM_INGRESO_DOTACION, can_edit=can_edit)
            if _codigo_base_dotaciones_duplicado(codigo):
                flash("El código ya está registrado en Base de Dotaciones.", "error")
                return render_template("registro_form.html", modulo_id=modulo_id, titulo="Ingreso de Dotación", form_fields=_FORM_INGRESO_DOTACION, can_edit=can_edit)
            estado = _normalize_estado_base_dotaciones("DISPONIBLE")
            obj = BaseDotaciones(codigo=codigo, cantidad=cantidad, talla=talla, estado=estado, area_uso=area_uso)
            db.session.add(obj)
            db.session.commit()
            flash("Dotación registrada en Base de Dotaciones.", "success")
            return redirect(url_for("main.registro_form", modulo_id=modulo_id))
        if modulo_id == "registro-personal":
            nombre = (request.form.get("nombre") or "").strip()
            documento = (request.form.get("documento") or "").strip()
            if not nombre or not documento:
                flash("Nombre y documento son obligatorios.", "error")
                return render_template("registro_form.html", modulo_id=modulo_id, titulo="Registro de Personal", form_fields=_FORM_REGISTRO_PERSONAL, can_edit=can_edit)
            talla_val = (request.form.get("talla") or "").strip()
            if not talla_val:
                flash("Seleccione una talla.", "error")
                return render_template(
                    "registro_form.html",
                    modulo_id=modulo_id,
                    titulo="Registro de Personal",
                    form_fields=_FORM_REGISTRO_PERSONAL,
                    can_edit=can_edit,
                    default_area=current_area,
                )
            obj = RegistroAsignaciones(
                id_asignaciones=_get_next_id_asignaciones(),
                operario=nombre,
                identificacion=documento,
                email="",
                telefono="",
                cargo="",
                area=current_area,
                talla_operarios=talla_val,
                area_lockers=(request.form.get("area_lockers") or "").strip(),
                estado="Activo",
                fecha_asignacion=datetime.utcnow(),
                codigo_lockets="",
                codigo_dotacion="",
                es_planta_desposte=_registro_manual_es_planta_desposte(current_area),
            )
            db.session.add(obj)
            db.session.commit()
            flash("Personal registrado. Aparece en Personal Registrado hasta que se asigne locker o dotación.", "success")
            return redirect(url_for("main.modulo", modulo_id="registro-personal"))
        if modulo_id == "ingreso-lockers":
            codigo = (request.form.get("codigo") or "").strip()
            area = (request.form.get("area") or "").strip() or current_area
            area_lockers = (request.form.get("area_lockers") or "").strip()
            cantidad = max(1, request.form.get("cantidad", type=int) or 1)
            if not codigo:
                flash("El código es obligatorio.", "error")
                return render_template("registro_form.html", modulo_id=modulo_id, titulo="Ingreso de Lockers", form_fields=_FORM_INGRESO_LOCKERS, can_edit=can_edit, default_area=current_area)
            if _codigo_base_lockers_duplicado(codigo):
                flash("El código ya está registrado en Base de Lockers.", "error")
                return render_template("registro_form.html", modulo_id=modulo_id, titulo="Ingreso de Lockers", form_fields=_FORM_INGRESO_LOCKERS, can_edit=can_edit, default_area=current_area)
            if cantidad > 1:
                flash("Cada código debe ser único. Indique cantidad 1 o registre otro código en un envío aparte.", "error")
                return render_template("registro_form.html", modulo_id=modulo_id, titulo="Ingreso de Lockers", form_fields=_FORM_INGRESO_LOCKERS, can_edit=can_edit, default_area=current_area)
            estado = _normalize_estado_base_lockers((request.form.get("estado") or "disponible").strip())
            for _ in range(cantidad):
                obj = BaseLockers(codigo=codigo, area=area, subarea="", area_lockers=area_lockers, estado=estado)
                db.session.add(obj)
            db.session.commit()
            flash("Locker(s) registrado(s) en Base de Lockers.", "success")
            return redirect(url_for("main.registro_form", modulo_id=modulo_id))
    if modulo_id == "ingreso-dotacion":
        return render_template("registro_form.html", modulo_id=modulo_id, titulo="Ingreso de Dotación", form_fields=_FORM_INGRESO_DOTACION, can_edit=can_edit)
    if modulo_id == "registro-personal":
        return render_template("registro_form.html", modulo_id=modulo_id, titulo="Registro de Personal", form_fields=_FORM_REGISTRO_PERSONAL, can_edit=can_edit, estado_activo=True, default_area=current_area)
    if modulo_id == "ingreso-lockers":
        return render_template("registro_form.html", modulo_id=modulo_id, titulo="Ingreso de Lockers", form_fields=_FORM_INGRESO_LOCKERS, can_edit=can_edit, default_area=current_area)
    return None


# Áreas operativas para el formulario de ingreso de dotación (encabezado / registro_form).
INGRESO_DOTACION_AREA_OPCIONES = frozenset(
    (
        "PROCESO",
        "VISITAS",
        "MTTO",
        "PLANTA EMERGENCIA",
        "EXTERNOS",
        "PIELES",
        "SUBPRODUCTOS",
    )
)
_INGRESO_DOTACION_AREA_OPCIONES_ORDER = (
    "PROCESO",
    "VISITAS",
    "MTTO",
    "PLANTA EMERGENCIA",
    "EXTERNOS",
    "PIELES",
    "SUBPRODUCTOS",
)

# Campos para los formularios de registro independientes (no almacenan en su tabla original)
_FORM_INGRESO_DOTACION = [
    {"name": "codigo", "label": "Código", "type": "text", "required": True},
    {"name": "cantidad", "label": "Cantidad", "type": "number"},
    {"name": "talla", "label": "Talla", "type": "select", "options": TALLAS_SELECT_OPCIONES, "required": True},
    {
        "name": "area",
        "label": "Área",
        "type": "select",
        "options": ["", *_INGRESO_DOTACION_AREA_OPCIONES_ORDER],
        "required": True,
    },
    {"name": "estado", "label": "Estado", "type": "text", "readonly": True, "default": "Disponible"},
]
_FORM_REGISTRO_PERSONAL = [
    {"name": "nombre", "label": "Nombre", "type": "text", "required": True},
    {"name": "documento", "label": "Documento", "type": "text", "required": True},
    {"name": "area", "label": "Área", "type": "text"},
    {"name": "talla", "label": "Talla", "type": "select", "options": TALLAS_SELECT_OPCIONES, "required": True},
    {"name": "area_lockers", "label": "Área Lockers", "type": "select", "options": ["", "VESTIER HOMBRES", "VESTIER MUJERES", "ADMINISTRATIVO"]},
]
_FORM_INGRESO_LOCKERS = [
    {"name": "codigo", "label": "Código", "type": "text", "required": True},
    {"name": "cantidad", "label": "Cantidad (lockers a agregar)", "type": "number"},
    {"name": "area", "label": "Área", "type": "text"},
    {"name": "area_lockers", "label": "Área Lockers", "type": "select", "options": ["VESTIDOR HOMBRES", "VESTIDOR MUJERES", "ADMINISTRATIVOS"]},
    {"name": "estado", "label": "Estado", "type": "select", "options": ["DISPONIBLE", "ASIGNADO", "VISITA"]},
]


@bp.route("/dashboard/registro/<modulo_id>", methods=["GET", "POST"])
@login_required
@_require_current_area
def registro_form(modulo_id):
    if modulo_id not in ("ingreso-dotacion", "registro-personal", "ingreso-lockers"):
        flash("Módulo no encontrado.", "error")
        return redirect(url_for("main.dashboard"))
    out = _registro_form_view(modulo_id)
    if out is not None:
        return out
    return redirect(url_for("main.dashboard"))


@bp.route("/dashboard/<modulo_id>", methods=["GET", "POST"])
@login_required
@_require_current_area
def modulo(modulo_id):
    if modulo_id not in MODULOS_CONFIG:
        flash("Módulo no encontrado.", "error")
        return redirect(url_for("main.dashboard"))
    # Redirigir solo ingreso-dotacion e ingreso-lockers al formulario; registro-personal es listado "Personal Registrado"
    if modulo_id in ("ingreso-dotacion", "ingreso-lockers"):
        return redirect(url_for("main.registro_form", modulo_id=modulo_id))
    config = MODULOS_CONFIG[modulo_id]
    Model = config["model"]
    current_area = (session.get("current_area") or "").strip()
    columnas = list(config["columnas"])
    form_fields = list(config["form_fields"])
    if modulo_id == "seca-botas-disponibles":
        areas = [a.nombre for a in AreaTrabajo.query.order_by(AreaTrabajo.nombre).all()]
        opciones_area = ["SIN ASIGNAR", *areas]
        for f in form_fields:
            if f.get("name") == "area":
                f["options"] = opciones_area
                break
    # Subárea: visible en DESPOSTE y en subáreas Desposte (LYD, CAL, …); oculta en BENEFICIO, PCC, etc.
    _ca_mod = (current_area or "").strip().upper()
    if (
        modulo_id in ("base-lockers", "locker-disponibles")
        and _ca_mod != "DESPOSTE"
        and _ca_mod not in _DESPOSTE_CODES_UPPER
    ):
        columnas = [c for c in columnas if c.get("key") != "subarea"]
        form_fields = [f for f in form_fields if f.get("name") != "subarea"]
    date_fields = config.get("date_fields") or []
    titulo = config["titulo"]
    area_key = config.get("area_key")
    user_rol = (session.get("user_rol") or "usuario").strip().lower()
    user_area = (session.get("user_area") or "").strip()
    can_edit = _user_can_edit()

    if request.method == "GET" and config.get("no_crear") and request.args.get("crear"):
        return redirect(url_for("main.modulo", modulo_id=modulo_id))

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
                if user_rol == "coordinador" and area_key and user_area:  # superadmin/admin: sin restricción de área
                    if getattr(obj, area_key, None) != user_area:
                        flash("No puede eliminar registros de otra área.", "error")
                        return redirect(url_for("main.modulo", modulo_id=modulo_id, page=next_page))
                if Model == RegistroAsignaciones:
                    cod_dot = (getattr(obj, "codigo_dotacion", None) or "").strip()
                    cod_lock = (getattr(obj, "codigo_lockets", None) or "").strip()
                    hist = HistorialRetiros(
                        operario=getattr(obj, "operario", "") or "",
                        identificacion=getattr(obj, "identificacion", "") or "",
                        codigo_dotacion=cod_dot,
                        codigo_lockets=cod_lock,
                        area=getattr(obj, "area", "") or "",
                        talla_operarios=getattr(obj, "talla_operarios", "") or "",
                        talla_dotacion=getattr(obj, "talla_dotacion", "") or "",
                        area_lockers=getattr(obj, "area_lockers", "") or "",
                        fecha_retiro=datetime.utcnow(),
                        es_planta_desposte=bool(getattr(obj, "es_planta_desposte", False)),
                    )
                    db.session.add(hist)
                    reg_area = (getattr(obj, "area", None) or "").strip()
                    if cod_dot:
                        _liberar_dotacion(cod_dot, area=reg_area)
                    if cod_lock:
                        _liberar_locker(cod_lock, area=reg_area)
                db.session.delete(obj)
                db.session.commit()
                flash("Registro eliminado." + (" Pasa a Historial de Retiros y los códigos vuelven a estar disponibles." if Model == RegistroAsignaciones else ""), "success")
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
            old_cod_dot = (getattr(obj, "codigo_dotacion", None) or "").strip() if Model == RegistroAsignaciones else ""
            old_cod_lock = (getattr(obj, "codigo_lockets", None) or "").strip() if Model == RegistroAsignaciones else ""
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
            if Model == BaseLockers and hasattr(obj, "estado"):
                obj.estado = _normalize_estado_base_lockers(getattr(obj, "estado") or "")
            if Model == BaseDotaciones and hasattr(obj, "estado"):
                obj.estado = _normalize_estado_base_dotaciones(getattr(obj, "estado") or "")
            if Model == HistorialRetiros and hasattr(obj, "observaciones"):
                obj.observaciones = ((getattr(obj, "observaciones", None) or "").strip().upper())
            if Model == SecaBotasDisponibles and hasattr(obj, "area") and not (getattr(obj, "area") or "").strip():
                obj.area = "SIN ASIGNAR"
            if Model == SecaBotasDisponibles and hasattr(obj, "estado"):
                obj.estado = _normalize_estado_seca_botas(getattr(obj, "estado") or "")
            if Model == BaseDotaciones and hasattr(obj, "codigo") and _codigo_base_dotaciones_duplicado(getattr(obj, "codigo", None), exclude_id=obj.id):
                flash("El código ya está registrado.", "error")
                session["modulo_edit_form"] = {modulo_id: dict(request.form)}
                return redirect(url_for("main.modulo", modulo_id=modulo_id, edit_id=edit_id, page=next_page))
            if Model == BaseLockers and hasattr(obj, "codigo") and _codigo_base_lockers_duplicado(getattr(obj, "codigo", None), exclude_id=obj.id):
                flash("El código ya está registrado.", "error")
                session["modulo_edit_form"] = {modulo_id: dict(request.form)}
                return redirect(url_for("main.modulo", modulo_id=modulo_id, edit_id=edit_id, page=next_page))
            if Model == LockerDisponibles and hasattr(obj, "codigo") and _codigo_locker_disponibles_duplicado(getattr(obj, "codigo", None), exclude_id=obj.id):
                flash("El código ya está registrado.", "error")
                session["modulo_edit_form"] = {modulo_id: dict(request.form)}
                return redirect(url_for("main.modulo", modulo_id=modulo_id, edit_id=edit_id, page=next_page))
            # Validar Cod. Dotación y Cod. Lockers contra Dotaciones/Lockers Disponibles (Registro Asignaciones / Personal)
            if Model == RegistroAsignaciones:
                if not (getattr(obj, "identificacion", None) or "").strip():
                    flash("La identificación del operario es obligatoria.", "error")
                    session["modulo_edit_form"] = {modulo_id: dict(request.form)}
                    return redirect(url_for("main.modulo", modulo_id=modulo_id, edit_id=edit_id, page=next_page))
                cod_dot = (getattr(obj, "codigo_dotacion", None) or "").strip()
                cod_lock = (getattr(obj, "codigo_lockets", None) or "").strip()
                reg_area = (getattr(obj, "area", None) or "").strip() or current_area
                if cod_dot and not _codigo_dotacion_disponible(cod_dot, area=reg_area):
                    flash("El Código de dotación no está disponible (ya asignado o no existe en Dotaciones Disponibles). Por favor asigne otro.", "error")
                    session["modulo_edit_form"] = {modulo_id: dict(request.form)}
                    return redirect(url_for("main.modulo", modulo_id=modulo_id, edit_id=edit_id, page=next_page))
                if cod_lock and not _codigo_locker_disponible(cod_lock):
                    flash("El Código de locker no está disponible (ya asignado o no existe en Lockers Disponibles). Por favor asigne otro.", "error")
                    session["modulo_edit_form"] = {modulo_id: dict(request.form)}
                    return redirect(url_for("main.modulo", modulo_id=modulo_id, edit_id=edit_id, page=next_page))
                # Liberar códigos que ya no se usan y marcar los nuevos como asignados
                if old_cod_dot and old_cod_dot != cod_dot:
                    _liberar_dotacion(old_cod_dot, area=reg_area)
                if old_cod_lock and old_cod_lock != cod_lock:
                    _liberar_locker(old_cod_lock, area=reg_area)
                if cod_dot:
                    _marcar_dotacion_asignada(cod_dot, area=reg_area)
                if cod_lock:
                    _marcar_locker_asignado(cod_lock, area=reg_area)
            db.session.commit()
            flash("Registro actualizado.", "success")
            return redirect(url_for("main.modulo", modulo_id=modulo_id, page=next_page))

        if config.get("no_crear"):
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
        # Asignar área actual en módulos con area_key (Desposte: subáreas LYD/CAL/… → area=DESPOSTE + subarea)
        if area_key and current_area and hasattr(obj, area_key):
            if Model in (BaseLockers, LockerDisponibles):
                ca_u = (current_area or "").strip().upper()
                if ca_u in _DESPOSTE_SUBAREA_CODES:
                    obj.area = "DESPOSTE"
                    if hasattr(obj, "subarea"):
                        obj.subarea = ca_u
                else:
                    setattr(obj, area_key, current_area)
            else:
                setattr(obj, area_key, current_area)
        # Asegurar fechas obligatorias y ID ASG-XX
        if Model == RegistroAsignaciones:
            if getattr(obj, "fecha_asignacion", None) is None:
                obj.fecha_asignacion = datetime.utcnow()
            if not (getattr(obj, "estado", None) or "").strip():
                obj.estado = "Activo"
            if not (getattr(obj, "id_asignaciones", None) or "").strip():
                obj.id_asignaciones = _get_next_id_asignaciones()
            obj.es_planta_desposte = _registro_manual_es_planta_desposte(current_area)
        if Model == HistorialRetiros and getattr(obj, "fecha_retiro", None) is None:
            obj.fecha_retiro = datetime.utcnow()
        if Model == IngresoLockers and getattr(obj, "fecha_ingreso", None) is None:
            obj.fecha_ingreso = datetime.utcnow()
        if Model == IngresoDotacion and getattr(obj, "fecha_ingreso", None) is None:
            obj.fecha_ingreso = datetime.utcnow()
        if Model == BaseLockers and hasattr(obj, "estado"):
            obj.estado = _normalize_estado_base_lockers(getattr(obj, "estado") or "")
        if Model == BaseDotaciones and hasattr(obj, "estado"):
            obj.estado = _normalize_estado_base_dotaciones(getattr(obj, "estado") or "")
        if Model == HistorialRetiros and hasattr(obj, "observaciones"):
            obj.observaciones = ((getattr(obj, "observaciones", None) or "").strip().upper())
        if Model == SecaBotasDisponibles and hasattr(obj, "area") and not (getattr(obj, "area") or "").strip():
            obj.area = "SIN ASIGNAR"
        if Model == SecaBotasDisponibles and hasattr(obj, "estado"):
            obj.estado = _normalize_estado_seca_botas(getattr(obj, "estado") or "")
        if Model == BaseDotaciones and hasattr(obj, "codigo") and _codigo_base_dotaciones_duplicado(getattr(obj, "codigo", None)):
            flash("El código ya está registrado.", "error")
            session["modulo_crear_form"] = {modulo_id: dict(request.form)}
            return redirect(url_for("main.modulo", modulo_id=modulo_id, crear=1))
        if Model == BaseLockers and hasattr(obj, "codigo") and _codigo_base_lockers_duplicado(getattr(obj, "codigo", None)):
            flash("El código ya está registrado.", "error")
            session["modulo_crear_form"] = {modulo_id: dict(request.form)}
            return redirect(url_for("main.modulo", modulo_id=modulo_id, crear=1))
        if Model == LockerDisponibles and hasattr(obj, "codigo") and _codigo_locker_disponibles_duplicado(getattr(obj, "codigo", None)):
            flash("El código ya está registrado.", "error")
            session["modulo_crear_form"] = {modulo_id: dict(request.form)}
            return redirect(url_for("main.modulo", modulo_id=modulo_id, crear=1))
        # Validar Cod. Dotación y Cod. Lockers al crear RegistroAsignaciones
        if Model == RegistroAsignaciones:
            cod_dot = (getattr(obj, "codigo_dotacion", None) or "").strip()
            cod_lock = (getattr(obj, "codigo_lockets", None) or "").strip()
            if cod_dot and not _codigo_dotacion_disponible(cod_dot, area=current_area):
                flash("El Código de dotación no está disponible (ya asignado o no existe en Dotaciones Disponibles). Por favor asigne otro.", "error")
                session["modulo_crear_form"] = {modulo_id: dict(request.form)}
                return redirect(url_for("main.modulo", modulo_id=modulo_id, crear=1))
            if cod_lock and not _codigo_locker_disponible(cod_lock):
                flash("El Código de locker no está disponible (ya asignado o no existe en Lockers Disponibles). Por favor asigne otro.", "error")
                session["modulo_crear_form"] = {modulo_id: dict(request.form)}
                return redirect(url_for("main.modulo", modulo_id=modulo_id, crear=1))
            if cod_dot:
                _marcar_dotacion_asignada(cod_dot, area=current_area)
            if cod_lock:
                _marcar_locker_asignado(cod_lock, area=current_area)
        db.session.add(obj)
        db.session.commit()
        flash("Registro creado.", "success")
        return redirect(url_for("main.modulo", modulo_id=modulo_id))

    # GET: listar con paginación filtrada por área actual y búsqueda
    from sqlalchemy import or_, and_, false
    query = Model.query
    if area_key and current_area and hasattr(Model, area_key):
        if Model == BaseDotaciones and area_key == "area_uso":
            # Base dotaciones: DESPOSTE solo ve sus datos; las demás áreas ven todo excepto DESPOSTE
            if current_area.upper() == "DESPOSTE":
                query = query.filter(BaseDotaciones.area_uso == "DESPOSTE")
            else:
                query = query.filter(BaseDotaciones.area_uso != "DESPOSTE")
        elif Model == BaseLockers or Model == LockerDisponibles:
            lf = _lockers_por_sesion_filter(Model, current_area)
            if lf is not None:
                query = query.filter(lf)
            else:
                query = query.filter(false())
        elif Model == RegistroAsignaciones or Model == HistorialRetiros:
            if _is_desposte_context(current_area):
                attr = getattr(Model, area_key)
                query = query.filter(
                    getattr(Model, "es_planta_desposte").is_(True),
                    db.func.upper(attr).in_(DESPOSTE_AREAS),
                )
            else:
                scope = _registro_area_scope_filter(Model, current_area)
                if scope is not None:
                    query = query.filter(scope)
        else:
            query = query.filter(getattr(Model, area_key) == current_area)
    # Personal Registrado: solo RegistroAsignaciones sin locker ni dotación asignados
    if config.get("solo_sin_asignacion") and Model == RegistroAsignaciones:
        query = query.filter(
            or_(RegistroAsignaciones.codigo_lockets.is_(None), RegistroAsignaciones.codigo_lockets == ""),
            or_(RegistroAsignaciones.codigo_dotacion.is_(None), RegistroAsignaciones.codigo_dotacion == ""),
        )
    # Registro de asignaciones: solo registros que ya tienen locker o dotación asignada
    if config.get("solo_con_asignacion") and Model == RegistroAsignaciones:
        query = query.filter(
            or_(
                and_(RegistroAsignaciones.codigo_lockets.isnot(None), RegistroAsignaciones.codigo_lockets != ""),
                and_(RegistroAsignaciones.codigo_dotacion.isnot(None), RegistroAsignaciones.codigo_dotacion != ""),
            )
        )
    # Dotaciones Disponibles: solo registros con estado DISPONIBLE en Base de Dotaciones
    if config.get("solo_estado_disponible") and Model == BaseDotaciones:
        query = query.filter(BaseDotaciones.estado.ilike("%disponible%"))
        query = query.filter(~BaseDotaciones.estado.ilike("%asignada%"))
        # Alcance por área (DESPOSTE aparte; las demás áreas no ven DESPOSTE)
        if modulo_id == "dotaciones-disponibles":
            if _is_desposte_context(current_area):
                query = query.filter(BaseDotaciones.area_uso == "DESPOSTE")
            else:
                query = query.filter(BaseDotaciones.area_uso != "DESPOSTE")
                # Excluir códigos ya asignados en RegistroAsignaciones para el área (regla solicitada)
                scope_ra = _registro_area_scope_filter(RegistroAsignaciones, current_area)
                if scope_ra is not None:
                    assigned_codes_sq = (
                        RegistroAsignaciones.query.filter(scope_ra)
                        .filter(RegistroAsignaciones.codigo_dotacion.isnot(None), RegistroAsignaciones.codigo_dotacion != "")
                        .with_entities(RegistroAsignaciones.codigo_dotacion)
                        .distinct()
                        .subquery()
                    )
                    query = query.filter(~BaseDotaciones.codigo.in_(assigned_codes_sq))
    if config.get("solo_estado_disponible_locker") and Model == LockerDisponibles:
        query = query.filter(db.func.lower(LockerDisponibles.estado) == "disponible")
    if config.get("solo_estado_disponible_seca_botas") and Model == SecaBotasDisponibles:
        query = query.filter(db.func.lower(SecaBotasDisponibles.estado) == "disponible")
    search_q = (request.args.get("q") or "").strip()
    filter_col = (request.args.get("fcol") or "").strip()
    filter_val = (request.args.get("fval") or "").strip()

    if filter_col and filter_val and hasattr(Model, filter_col):
        from sqlalchemy import cast, String
        attr = getattr(Model, filter_col)
        try:
            query = query.filter(attr.ilike(f"%{filter_val}%"))
        except Exception:
            try:
                query = query.filter(cast(attr, String).ilike(f"%{filter_val}%"))
            except Exception:
                pass

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
    from sqlalchemy import text

    # Registro asignaciones / historial retiros: fecha más reciente primero (fecha entrega → fecha asignación/retiro → alta).
    order_asignaciones_reciente = None
    if Model == RegistroAsignaciones:
        od = db.func.coalesce(
            RegistroAsignaciones.fecha_entrega,
            RegistroAsignaciones.fecha_asignacion,
            RegistroAsignaciones.creado_en,
        )
        order_asignaciones_reciente = (od.desc(), RegistroAsignaciones.id.desc())
    elif Model == HistorialRetiros:
        od = db.func.coalesce(HistorialRetiros.fecha_retiro, HistorialRetiros.creado_en)
        order_asignaciones_reciente = (od.desc(), HistorialRetiros.id.desc())

    # Orden general de módulos por código (menor -> mayor) cuando exista un campo de código.
    # Si no hay código aplicable, mantiene orden por id descendente.
    code_order_fields = ("codigo", "identificacion", "id_asignaciones", "codigo_dotacion", "codigo_lockets")
    order_by_code = None
    for field_name in code_order_fields:
        if hasattr(Model, field_name):
            col = getattr(Model, field_name)
            order_by_code = [
                text(f"(CASE WHEN {field_name} IS NULL OR {field_name} = '' THEN 1 ELSE 0 END)"),
                text(f"({field_name} REGEXP '^[0-9]+$') DESC"),
                text(f"(CASE WHEN {field_name} REGEXP '^[0-9]+$' THEN CAST({field_name} AS UNSIGNED) ELSE 999999 END)"),
                col.asc(),
                Model.id.asc(),
            ]
            break

    if order_asignaciones_reciente is not None:
        rows = (
            query.order_by(*order_asignaciones_reciente)
            .limit(PER_PAGE)
            .offset((page - 1) * PER_PAGE)
            .all()
        )
    elif order_by_code:
        rows = (
            query.order_by(*order_by_code)
            .limit(PER_PAGE)
            .offset((page - 1) * PER_PAGE)
            .all()
        )
    else:
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
            if col["key"] == "subarea" and (Model == BaseLockers or Model == LockerDisponibles):
                area_val = (getattr(row, "area", None) or "") or ""
                sub_val = (val or "") or ""
                val = "{} (ubic. Desposte)".format(sub_val) if (area_val == "DESPOSTE" and sub_val) else sub_val
            if col["key"] == "area" and (Model == RegistroAsignaciones or Model == HistorialRetiros) and _is_desposte_context(current_area):
                area_val = (val or "").strip().upper()
                if area_val and area_val not in ("DES", "DESPOSTE"):
                    val = "{} (ubic. Desposte)".format(area_val)
                elif area_val == "DESPOSTE":
                    val = "DES"
            if col["key"] == "estado" and Model == BaseDotaciones and val:
                val = _normalize_estado_base_dotaciones(val)
            if col["key"] == "estado" and Model == RegistroAsignaciones:
                codigo_l = (getattr(row, "codigo_lockets", None) or "").strip()
                codigo_d = (getattr(row, "codigo_dotacion", None) or "").strip()
                if not codigo_l and not codigo_d:
                    val = "Pendiente"
                    d["_estado_pendiente"] = True
                elif (val or "").lower() == "activa":
                    val = "Activo"
            if val is not None and hasattr(val, "strftime"):
                d[col["key"]] = val.strftime("%Y-%m-%d")
            else:
                d[col["key"]] = val
        items.append(d)
    pendientes_sin_asignar = []
    pendientes_count = 0
    if modulo_id == "registro-asignaciones" and current_area:
        q_pend = RegistroAsignaciones.query
        if _is_desposte_context(current_area):
            q_pend = q_pend.filter(
                RegistroAsignaciones.es_planta_desposte.is_(True),
                db.func.upper(RegistroAsignaciones.area).in_(DESPOSTE_AREAS),
            )
        else:
            sc = _registro_area_scope_filter(RegistroAsignaciones, current_area)
            if sc is not None:
                q_pend = q_pend.filter(sc)
        pendientes_sin_asignar = (
            q_pend.filter(
                or_(
                    RegistroAsignaciones.codigo_lockets.is_(None),
                    RegistroAsignaciones.codigo_lockets == "",
                ),
                or_(
                    RegistroAsignaciones.codigo_dotacion.is_(None),
                    RegistroAsignaciones.codigo_dotacion == "",
                ),
            )
            .order_by(
                db.func.coalesce(
                    RegistroAsignaciones.fecha_entrega,
                    RegistroAsignaciones.fecha_asignacion,
                    RegistroAsignaciones.creado_en,
                ).desc(),
                RegistroAsignaciones.id.desc(),
            )
            .limit(100)
            .all()
        )
        pendientes_count = len(pendientes_sin_asignar)

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
                    if name == "estado" and Model == BaseDotaciones and val:
                        val = _normalize_estado_base_dotaciones(val)
                    if name == "estado" and Model == RegistroAsignaciones and val:
                        val = "ACTIVO" if (val or "").strip().lower() == "activa" else (val or "ACTIVO").strip().upper()
                    if name == "estado" and Model == BaseLockers and val is not None:
                        val = (val or "disponible").strip().upper()
                    if name == "estado" and Model == LockerDisponibles and val is not None:
                        val = (val or "disponible").strip().upper()
                    if val is not None and name in date_fields and hasattr(val, "strftime"):
                        edit_data[name] = val.strftime("%Y-%m-%d")
                    else:
                        edit_data[name] = val
        # Si hubo error de validación, usar datos del formulario guardados en sesión
        saved_form = session.pop("modulo_edit_form", {}).get(modulo_id)
        if saved_form:
            edit_data = {k: saved_form.get(k, "") for k in (f["name"] for f in form_fields)}
    # Al crear, si hubo error de validación, prellenar con datos guardados en sesión
    if request.args.get("crear") and not edit_data:
        saved_crear = session.pop("modulo_crear_form", {}).get(modulo_id)
        if saved_crear:
            edit_data = {k: saved_crear.get(k, "") for k in (f["name"] for f in form_fields)}
        elif modulo_id == "seca-botas-disponibles":
            edit_data = {"area": "SIN ASIGNAR", "estado": "DISPONIBLE"}
    # Listas de códigos para selects: disponibles (asignación) o todos (historial retiros)
    form_field_names = [f["name"] for f in form_fields]
    opciones_dotacion = []
    opciones_locker = []
    opciones_seca_botas = []
    if "codigo_dotacion" in form_field_names:
        q_dot = BaseDotaciones.query
        if current_area == "DESPOSTE":
            q_dot = q_dot.filter(BaseDotaciones.area_uso == "DESPOSTE")
        elif current_area:
            q_dot = q_dot.filter(BaseDotaciones.area_uso != "DESPOSTE")
        if modulo_id == "historial-retiros":
            opciones_dotacion = [r[0] for r in q_dot.with_entities(BaseDotaciones.codigo).distinct().order_by(BaseDotaciones.codigo).all() if r[0]]
        else:
            opciones_dotacion = [
                r[0] for r in
                q_dot.filter(BaseDotaciones.estado.ilike("%disponible%"))
                .filter(~BaseDotaciones.estado.ilike("%asignada%"))
                .with_entities(BaseDotaciones.codigo)
                .distinct()
                .order_by(BaseDotaciones.codigo)
                .all()
            ]
            opciones_dotacion = [c for c in opciones_dotacion if c]
    if "codigo_lockets" in form_field_names:
        q = LockerDisponibles.query
        if modulo_id != "historial-retiros":
            q = q.filter(db.func.lower(LockerDisponibles.estado) == "disponible")
        if current_area:
            lf = _lockers_por_sesion_filter(LockerDisponibles, current_area)
            if lf is not None:
                q = q.filter(lf)
        opciones_locker = [r[0] for r in q.with_entities(LockerDisponibles.codigo).order_by(LockerDisponibles.codigo).all()]
    if "codigo_seca_botas" in form_field_names:
        q_sb = SecaBotasDisponibles.query.filter(db.func.lower(SecaBotasDisponibles.estado) != "disponible")
        # Regla solicitada: para áreas distintas de DESPOSTE, aplicar el filtro por área del código (no por Desposte)
        if current_area and current_area.strip().upper() != "DESPOSTE":
            q_sb = q_sb.filter(db.func.upper(db.func.trim(SecaBotasDisponibles.area)) == current_area.strip().upper())
        opciones_seca_botas = [
            r[0]
            for r in q_sb.with_entities(SecaBotasDisponibles.codigo)
            .distinct()
            .order_by(SecaBotasDisponibles.codigo)
            .all()
            if r[0]
        ]
    return render_template(
        "modulo.html",
        modulo_id=modulo_id,
        titulo=titulo,
        columnas=columnas,
        form_fields=form_fields,
        items=items,
        item_edit=item_edit,
        edit_data=edit_data,
        opciones_dotacion=opciones_dotacion,
        opciones_locker=opciones_locker,
        opciones_seca_botas=opciones_seca_botas,
        modulos_config=MODULOS_CONFIG,
        can_edit=can_edit and not config.get("solo_lectura", False),
        can_crear=not config.get("no_crear", False),
        page=page,
        total_pages=total_pages,
        total=total,
        per_page=PER_PAGE,
        search_q=search_q,
        filter_col=filter_col,
        filter_val=filter_val,
        pendientes_sin_asignar=pendientes_sin_asignar if modulo_id == "registro-asignaciones" else [],
        pendientes_count=pendientes_count if modulo_id == "registro-asignaciones" else 0,
    )
