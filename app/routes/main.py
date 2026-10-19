import os
import re
from datetime import datetime, timedelta, timezone
from functools import wraps
from zoneinfo import ZoneInfo
from flask import Blueprint, render_template, redirect, url_for, request, session, flash, current_app, send_from_directory, send_file
from itsdangerous import URLSafeTimedSerializer, BadSignature
from app import db
from werkzeug.security import check_password_hash, generate_password_hash
from app.utils.email import send_password_reset_email, send_password_changed_notification
from app.models import (
    BaseLockers, BaseDotaciones, Usuario,
    RegistroPersonal, RegistroAsignaciones, DotacionesDisponibles,
    LockerDisponibles, HistorialRetiros, PersonalPresupuestado,
    IngresoLockers, IngresoDotacion, AreaTrabajo, SecaBotasDisponibles,
    UsabilidadLog, HistorialCambios,
)

bp = Blueprint("main", __name__)

# Hora local del equipo / Colombia (UTC-5, sin DST)
_TZ_COLOMBIA = ZoneInfo("America/Bogota")
_TZ_UTC = timezone.utc


@bp.route("/favicon.ico")
def favicon():
    return send_from_directory(
        os.path.join(current_app.root_path, "static"),
        "favicon.svg",
        mimetype="image/svg+xml",
    )


DESPOSTE_AREAS = ("DESPOSTE", "DES", "CAL", "LYD", "SST", "MTTO", "LOG", "EXT", "TIC")
_DESPOSTE_CODES_UPPER = frozenset((a or "").upper() for a in DESPOSTE_AREAS)
# Códigos de subárea en planta Desposte (DES, LYD, CAL, …) — sin la palabra DESPOSTE como “subárea”
_DESPOSTE_SUBAREA_CODES = frozenset(x for x in _DESPOSTE_CODES_UPPER if x != "DESPOSTE")

# Sesión EXTERNOS / EXTERNOS/OTRAS AREAS: listados de registros externos (no planta principal).
_INTERNAS_PLANTA_UPPER = frozenset(
    {
        *_DESPOSTE_CODES_UPPER,
        "ASUR",
        "BENEFICIO",
        "LN",
        "CALIDAD",
        "CAL",
        "LOGISTICA",
        "LOG",
        "VIS",
        "VISITAS",
        "MTTO",
        "PCC",
        "PROCESO",
        "ADMINISTRATIVA",
        "SST",
        "TIC",
        "ADM",
        "PYP",
        "GG",
        "SEG",
    }
)

# Área nueva: agrupa SST, TIC, ADM, EXT, PYP, GG, SEG, ASUR, MTTO.
# Sin historial retiros/cambios ni personal presupuestado.
_ADMINISTRATIVA_UPPER = "ADMINISTRATIVA"
_MODULOS_OCULTOS_ADMINISTRATIVA = frozenset(
    {"historial-retiros", "historial-cambios", "personal-presupuestado"}
)

# Personal presupuestado en Excel/BD suele usar códigos cortos (LN, LOG, CAL).
_AREA_PP_ALIASES = {
    "BENEFICIO": ("BENEFICIO", "LN"),
    "LOGISTICA": ("LOGISTICA", "LOG"),
    "CALIDAD": ("CALIDAD", "CAL"),
    "PCC": ("PCC",),
    "LYD": ("LYD",),
}
# Etiquetas que solo deben verse en esta sesión (no en ASUR/BENEFICIO/… ni en vista general dotaciones ≠ DESPOSTE).
_OTRAS_ETIQUETAS_SOLO_SESION_EXTERNOS = frozenset(
    (
        "PIELES",
        "SUBPRODUCTOS",
        "PLANTA EMERGENCIA",
    )
)
_DOTACION_AREA_USO_RESTO_INTERNA = frozenset(_INTERNAS_PLANTA_UPPER)

# Nombre de área de trabajo en sesión y en UI (mantener también "EXTERNOS" por compatibilidad con filas viejas).
_LABEL_AREA_EXTERNAS_OTRAS = "EXTERNOS/OTRAS AREAS"
_EXTERNOS_SESSION_UPPER = frozenset(
    {
        "EXTERNOS",
        (_LABEL_AREA_EXTERNAS_OTRAS or "").strip().upper(),
    }
)


def _is_externos_area(area):
    return (area or "").strip().upper() in _EXTERNOS_SESSION_UPPER


def _area_uso_solo_en_sesion_externas(area_uso_val):
    """Área de uso de dotación que no debe darse de alta ni verse en áreas principales (solo EXTERNOS/OTRAS AREAS)."""
    u = (area_uso_val or "").strip().upper()
    return u in _OTRAS_ETIQUETAS_SOLO_SESION_EXTERNOS or u in _EXTERNOS_SESSION_UPPER


def _filtro_sin_etiquetas_solo_otras_areas(t_norm):
    """Excluye PIELES, SUBPRODUCTOS, PLANTA EMERGENCIA (columna ya trim+upper en SQL)."""
    return ~t_norm.in_(_OTRAS_ETIQUETAS_SOLO_SESION_EXTERNOS)


def _base_dotaciones_scope_filter(current_area):
    """Filtro sobre BaseDotaciones según sesión: DESPOSTE / EXTERNOS·otras / resto (sin DESPOSTE ni sólo‑otras)."""
    from sqlalchemy import and_

    au = db.func.upper(db.func.trim(db.func.coalesce(BaseDotaciones.area_uso, "")))
    ca_u = (current_area or "").strip().upper()
    if ca_u == "DESPOSTE":
        return BaseDotaciones.area_uso == "DESPOSTE"
    if _is_externos_area(current_area):
        # Incluye PIELES, SUBPRODUCTOS, PLANTA EMERGENCIA; excluye solo áreas internas de planta.
        return and_(au != "", ~au.in_(_DOTACION_AREA_USO_RESTO_INTERNA))
    return and_(BaseDotaciones.area_uso != "DESPOSTE", _filtro_sin_etiquetas_solo_otras_areas(au))


# Cierre por inactividad (segundos). Valor prudente: 25 min.
IDLE_TIMEOUT_SECONDS = 25 * 60
# Área DESPOSTE en mantenimiento: no se entra; solo se muestra el aviso.
DESPOSTE_EN_MANTENIMIENTO = True
USABILIDAD_DEBOUNCE_SECONDS = 4


def _is_superadmin():
    return (session.get("user_rol") or "").strip().lower() == "superadmin"


def _desposte_bloqueado_para_usuario():
    """True si DESPOSTE está en mantenimiento (bloqueada para todos)."""
    return bool(DESPOSTE_EN_MANTENIMIENTO)


def _usabilidad_skip_path(path):
    path_l = (path or "").lower()
    if path_l.startswith("/static/") or path_l.startswith("/favicon"):
        return True
    if "/api/" in path_l or path_l.endswith("/api/stats"):
        return True
    if path_l in ("/login", "/acceso-integrado", "/favicon.ico"):
        return True
    return False


def _now_colombia():
    """Hora actual en zona America/Bogota (naive, para guardar/mostrar alineado al equipo)."""
    return datetime.now(_TZ_COLOMBIA).replace(tzinfo=None)


def _as_hora_colombia(dt):
    """Convierte un datetime (UTC naive o aware) a hora local Colombia naive."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        # Los logs de usabilidad se guardan en UTC naive
        dt = dt.replace(tzinfo=_TZ_UTC)
    return dt.astimezone(_TZ_COLOMBIA).replace(tzinfo=None)


def _usabilidad_accion_label(path, method="GET"):
    """Etiqueta legible de la navegación para el módulo de usabilidad."""
    path = (path or "").rstrip("/") or "/"
    method = (method or "GET").upper()
    if path == "/areas":
        return "Selector de áreas"
    if path.startswith("/entrar-area/"):
        from urllib.parse import unquote
        area = unquote(path[len("/entrar-area/"):]).upper()
        return f"Entró al área {area}"
    if path == "/dashboard":
        return "Dashboard"
    if path == "/dashboard/usuarios":
        return "Gestión de usuarios"
    if path == "/dashboard/usabilidad":
        return "Usabilidad por usuario"
    if path == "/logout":
        return "Cierre de sesión"
    if path.startswith("/dashboard/registro/"):
        mid = path.rsplit("/", 1)[-1]
        titulo = MODULOS_CONFIG.get(mid, {}).get("titulo", mid)
        return f"Formulario: {titulo}"
    if path.startswith("/dashboard/"):
        parts = [p for p in path.split("/") if p]
        if len(parts) >= 2:
            mid = parts[1]
            if mid in MODULOS_CONFIG:
                titulo = MODULOS_CONFIG[mid].get("titulo", mid)
                return f"{'Consultó' if method == 'GET' else 'Acción en'} {titulo}"
    return f"{method} {path}"


def _registrar_usabilidad_evento(
    *,
    user_id=None,
    user_nombre="",
    user_email="",
    user_rol="",
    area="",
    path="",
    metodo="GET",
    accion="",
):
    """Inserta un evento de usabilidad (no bloquea la app si falla).
    No registra actividad del superadmin."""
    try:
        rol = (user_rol or "").strip().lower()
        if rol == "superadmin":
            return
        # Si viene de sesión actual y es superadmin, tampoco.
        if (session.get("user_rol") or "").strip().lower() == "superadmin":
            return
        db.session.add(
            UsabilidadLog(
                user_id=user_id,
                user_nombre=(user_nombre or "")[:120],
                user_email=(user_email or "")[:120],
                user_rol=(user_rol or "")[:30],
                area=(area or "")[:100],
                path=(path or "/")[:255],
                metodo=(metodo or "GET")[:10],
                accion=(accion or _usabilidad_accion_label(path, metodo))[:255],
            )
        )
        db.session.commit()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass


def _log_usabilidad_navegacion():
    """Persiste un registro de navegación (no bloquea la app si falla)."""
    try:
        if session.get("user_id") is None:
            return
        if (session.get("user_rol") or "").strip().lower() == "superadmin":
            return
        path = request.path or ""
        method = (request.method or "GET").upper()
        if _usabilidad_skip_path(path):
            return
        now = int(datetime.utcnow().timestamp())
        last_path = session.get("_usa_last_path")
        last_ts = session.get("_usa_last_ts")
        try:
            last_ts_i = int(last_ts) if last_ts is not None else None
        except Exception:
            last_ts_i = None
        if (
            method == "GET"
            and last_path == path
            and last_ts_i is not None
            and (now - last_ts_i) < USABILIDAD_DEBOUNCE_SECONDS
        ):
            return
        session["_usa_last_path"] = path
        session["_usa_last_ts"] = now
        _registrar_usabilidad_evento(
            user_id=session.get("user_id"),
            user_nombre=session.get("user_nombre") or "",
            user_email=session.get("user_email") or "",
            user_rol=session.get("user_rol") or "",
            area=session.get("current_area") or "",
            path=path,
            metodo=method,
            accion=_usabilidad_accion_label(path, method),
        )
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass


@bp.before_app_request
def _idle_timeout_guard():
    """Cierra sesión si no hay actividad; registra usabilidad; bloquea DESPOSTE en mantenimiento."""
    path = (request.path or "").lower()
    if path.startswith("/static/"):
        return None
    if path in ("/login", "/acceso-integrado", "/logout", "/favicon.ico"):
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
        _registrar_usabilidad_evento(
            user_id=session.get("user_id"),
            user_nombre=session.get("user_nombre") or "",
            user_email=session.get("user_email") or "",
            user_rol=session.get("user_rol") or "",
            area=session.get("current_area") or "",
            path="/logout",
            metodo="GET",
            accion="Desconexión por inactividad",
        )
        session.clear()
        return redirect(url_for("main.login", reason="idle"))
    session["last_activity_ts"] = now

    # Sesiones viejas en DESPOSTE mientras está en mantenimiento
    if (
        _desposte_bloqueado_para_usuario()
        and (session.get("current_area") or "").strip().upper() == "DESPOSTE"
        and not path.startswith("/areas")
        and not path.startswith("/entrar-area")
    ):
        session.pop("current_area", None)
        flash(
            "El área DESPOSTE se encuentra en mantenimiento. Estará disponible luego.",
            "error",
        )
        return redirect(url_for("main.areas"))

    _log_usabilidad_navegacion()
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
    if _is_externos_area(current_area):
        tu = db.func.upper(db.func.trim(db.func.coalesce(a, "")))
        return and_(tu != "", ~tu.in_(_INTERNAS_PLANTA_UPPER))
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
    if _is_externos_area(current_area):
        tu = db.func.upper(db.func.trim(db.func.coalesce(ac, "")))
        return and_(tu != "", ~tu.in_(_INTERNAS_PLANTA_UPPER))
    if _is_desposte_context(current_area):
        flag = getattr(Model, "es_planta_desposte", None)
        zone = db.func.upper(db.func.trim(ac)).in_(DESPOSTE_AREAS)
        tu = db.func.upper(db.func.trim(ac))
        if flag is not None:
            return and_(flag.is_(True), zone, _filtro_sin_etiquetas_solo_otras_areas(tu))
        return and_(zone, _filtro_sin_etiquetas_solo_otras_areas(tu))

    tu = db.func.upper(db.func.trim(ac))
    flag = getattr(Model, "es_planta_desposte", None)

    def _no_es_planta_desposte():
        if flag is None:
            return sql_true()
        return or_(flag.is_(False), flag.is_(None))

    # Área en sesión = nombre largo (area_trabajo); CSV histórico = código corto.
    if ca == "CALIDAD":
        return and_(
            or_(tu == "CALIDAD", and_(tu == "CAL", _no_es_planta_desposte())),
            _filtro_sin_etiquetas_solo_otras_areas(tu),
        )
    if ca == "LOGISTICA":
        return and_(
            or_(tu == "LOGISTICA", and_(tu == "LOG", _no_es_planta_desposte())),
            _filtro_sin_etiquetas_solo_otras_areas(tu),
        )
    if ca == "BENEFICIO":
        return and_(
            or_(tu == "BENEFICIO", tu == "LN"),
            _filtro_sin_etiquetas_solo_otras_areas(tu),
        )

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
        return and_(cond, _filtro_sin_etiquetas_solo_otras_areas(tu))

    return and_(tu == ca, _filtro_sin_etiquetas_solo_otras_areas(tu))


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


def _codigo_dotacion_disponible(codigo, area=None, permitir_codigo=None):
    """True si el código existe en Base de Dotaciones con estado DISPONIBLE.
    Si area='DESPOSTE' solo busca en dotaciones DESPOSTE; si area es otra, excluye DESPOSTE.
    permitir_codigo: al editar, acepta el código ya asignado al mismo registro.
    """
    if not (codigo or "").strip():
        return True
    cod = (codigo or "").strip()
    if permitir_codigo and cod == (permitir_codigo or "").strip():
        return True
    q = BaseDotaciones.query.filter(
        BaseDotaciones.codigo == cod,
        BaseDotaciones.estado.ilike("%disponible%"),
    ).filter(~BaseDotaciones.estado.ilike("%asignada%"))
    ca = (area or "").strip().upper()
    if ca == "DESPOSTE":
        q = q.filter(BaseDotaciones.area_uso == "DESPOSTE")
    elif area:
        q = q.filter(_base_dotaciones_scope_filter(area))
    return q.first() is not None


def _codigo_locker_disponible(codigo, permitir_codigo=None):
    """True si el código existe en Lockers Disponibles con estado DISPONIBLE.
    permitir_codigo: al editar, acepta el código ya asignado al mismo registro.
    """
    if not (codigo or "").strip():
        return True
    cod = (codigo or "").strip()
    if permitir_codigo and cod == (permitir_codigo or "").strip():
        return True
    return (
        LockerDisponibles.query.filter_by(codigo=cod)
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
    ca = (area or "").strip().upper()
    if ca == "DESPOSTE":
        q = q.filter(BaseDotaciones.area_uso == "DESPOSTE")
    elif area:
        q = q.filter(_base_dotaciones_scope_filter(area))
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
    ca = (area or "").strip().upper()
    if ca == "DESPOSTE":
        q = q.filter(BaseDotaciones.area_uso == "DESPOSTE")
    elif area:
        q = q.filter(_base_dotaciones_scope_filter(area))
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


def _liberar_seca_botas(codigo):
    """Vuelve a DISPONIBLE la seca botas con ese código."""
    if not (codigo or "").strip():
        return
    cod = (codigo or "").strip()
    for reg in SecaBotasDisponibles.query.filter_by(codigo=cod).all():
        reg.estado = "DISPONIBLE"


def _snapshot_registro(obj, max_len=800):
    """Resumen corto de un registro para auditoría."""
    if obj is None:
        return ""
    partes = []
    for attr in (
        "identificacion",
        "operario",
        "codigo",
        "codigo_dotacion",
        "codigo_lockets",
        "codigo_seca_botas",
        "area",
        "estado",
        "nombre",
    ):
        if hasattr(obj, attr):
            val = getattr(obj, attr, None)
            if val is not None and str(val).strip():
                partes.append(f"{attr}={str(val).strip()}")
    if not partes:
        partes.append(f"id={getattr(obj, 'id', '')}")
    return "; ".join(partes)[:max_len]


def _registrar_cambio(modulo_id, accion, obj=None, detalle="", registro_id=None):
    """Guarda una entrada en historial_cambios (no falla la operación principal)."""
    try:
        rid = registro_id
        if rid is None and obj is not None:
            rid = getattr(obj, "id", None)
        resumen = f"{accion} en {modulo_id}"
        if obj is not None:
            snap = _snapshot_registro(obj)
            if snap:
                resumen = f"{accion}: {snap}"
        db.session.add(
            HistorialCambios(
                modulo=(modulo_id or "")[:80],
                accion=(accion or "")[:20],
                registro_id=rid,
                resumen=(resumen or "")[:255],
                detalle=(detalle or _snapshot_registro(obj, 4000) or "")[:4000],
                usuario_id=session.get("user_id"),
                usuario_nombre=(session.get("user_nombre") or session.get("user_email") or "")[:120],
                area=(session.get("current_area") or "")[:100],
            )
        )
    except Exception:
        pass


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


def _digits_only_field_error(form_fields, form):
    """Valida campos con numeric_only: solo dígitos (texto) o entero con signo opcional (type number)."""
    for f in form_fields:
        if not f.get("numeric_only"):
            continue
        name = f.get("name")
        if not name or f.get("type") == "hidden":
            continue
        val = (form.get(name) or "").strip()
        if not val:
            continue
        if f.get("type") == "number":
            if not val.isdigit():
                label = (f.get("label") or name).replace('"', "'")
                return f"El campo «{label}» solo admite números (sin letras ni símbolos)."
        else:
            if not val.isdigit():
                label = (f.get("label") or name).replace('"', "'")
                return f"El campo «{label}» solo admite números (sin letras ni símbolos)."
    return None


# Opciones estándar para campos de talla (formularios de encabezado y módulos)
TALLAS_SELECT_OPCIONES = ["", "M", "L", "S", "XXL", "XL", "XXXL", "XS", "S-M-L-XL"]

MODULOS_CONFIG = {
    "base-lockers": {
        "model": BaseLockers,
        "titulo": "Base de Lockers",
        "icon": "locker",
        "area_key": "area",
        "no_crear": True,
        "columnas": [
            {"key": "codigo", "label": "Código"},
            {"key": "area", "label": "Área"},
            {"key": "subarea", "label": "Subárea (ubic. Desposte)"},
            {"key": "area_lockers", "label": "Área Lockers"},
            {"key": "estado", "label": "Estado"},
            {"key": "unidad", "label": "Unidad"},
        ],
        "form_fields": [
            {"name": "codigo", "label": "Código", "type": "text", "required": True, "numeric_only": True},
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
            {"name": "codigo", "label": "Código", "type": "text", "required": True, "numeric_only": True},
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
            {"key": "area_locker", "label": "UBICACIÓN"},
        ],
        "form_fields": [
            {"name": "codigo", "label": "CODIGO", "type": "text", "required": True, "numeric_only": True},
            {"name": "area", "label": "AREA", "type": "select", "options": []},
            {"name": "area_locker", "label": "UBICACIÓN", "type": "text"},
        ],
        "date_fields": [],
    },
    "base-dotaciones": {
        "model": BaseDotaciones,
        "titulo": "Base de Dotaciones",
        "icon": "package",
        "area_key": "area_uso",
        "no_crear": True,
        "columnas": [
            {"key": "codigo", "label": "Código"},
            {"key": "area_uso", "label": "Área uso"},
            {"key": "cantidad", "label": "Cantidad"},
            {"key": "talla", "label": "Talla"},
            {"key": "estado", "label": "Estado"},
        ],
        "form_fields": [
            {"name": "codigo", "label": "Código", "type": "text", "numeric_only": True},
            {"name": "cantidad", "label": "Cantidad", "type": "number", "numeric_only": True},
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
            {"key": "codigo_lockets", "label": "Cód. Lockers"},
            {"key": "codigo_dotacion", "label": "Cód. Dotación"},
            {"key": "codigo_seca_botas", "label": "Cód. Seca Botas"},
            {"key": "fecha_asignacion", "label": "Fecha asignación"},
            {"key": "fecha_entrega", "label": "Fecha entrega"},
            {"key": "estado", "label": "Estado"},
        ],
        "form_fields": [
            {"name": "fecha_asignacion", "label": "Fecha de asignación", "type": "date", "required": True},
            {"name": "fecha_entrega", "label": "Fecha de entrega", "type": "date", "required": True},
            {"name": "codigo_seca_botas", "label": "Código Seca Botas", "type": "text", "required": True, "numeric_only": True},
            {"name": "operario", "label": "Nombre", "type": "text", "required": True},
            {"name": "identificacion", "label": "Documento", "type": "text", "required": True, "numeric_only": True},
            {"name": "area", "label": "Área", "type": "hidden"},
            {"name": "talla_operarios", "label": "Talla", "type": "select", "options": TALLAS_SELECT_OPCIONES},
            {"name": "area_lockers", "label": "Área Lockers", "type": "text"},
            {"name": "codigo_lockets", "label": "Código lockers", "type": "text", "required": True},
            {"name": "codigo_dotacion", "label": "Código dotación", "type": "text", "required": True},
            {"name": "estado", "label": "Estado", "type": "select", "options": ["ACTIVO", "INACTIVO", "PENDIENTE"]},
            {"name": "observaciones", "label": "Observaciones", "type": "textarea"},
        ],
        "date_fields": ["fecha_asignacion", "fecha_entrega"],
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
            {"name": "aprobados", "label": "Aprobados", "type": "number", "numeric_only": True},
            {"name": "contratados", "label": "Contratados", "type": "number", "numeric_only": True},
            {"name": "por_contratar", "label": "Por contratar", "type": "number", "numeric_only": True},
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
            {"name": "identificacion", "label": "Identificación", "type": "text", "required": True, "numeric_only": True},
            {"name": "codigo_lockets", "label": "Código lockers", "type": "text"},
            {"name": "codigo_seca_botas", "label": "Cód. Seca Botas", "type": "text", "numeric_only": True},
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
            {"name": "identificacion", "label": "Identificación", "type": "text", "numeric_only": True},
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
    "historial-cambios": {
        "model": HistorialCambios,
        "titulo": "Historial de Cambios",
        "icon": "clock",
        "area_key": None,
        "no_crear": True,
        "solo_lectura": True,
        "columnas": [
            {"key": "creado_en", "label": "Fecha"},
            {"key": "accion", "label": "Acción"},
            {"key": "modulo", "label": "Módulo"},
            {"key": "resumen", "label": "Resumen"},
            {"key": "usuario_nombre", "label": "Usuario"},
            {"key": "area", "label": "Área"},
            {"key": "registro_id", "label": "ID registro"},
        ],
        "form_fields": [],
        "date_fields": ["creado_en"],
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
            {"name": "codigo", "label": "Código", "type": "text", "numeric_only": True},
            {"name": "cantidad", "label": "Cantidad", "type": "number", "numeric_only": True},
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
            {"name": "codigo", "label": "Código", "type": "text", "numeric_only": True},
            {"name": "descripcion", "label": "Descripción", "type": "text"},
            {"name": "cantidad", "label": "Cantidad", "type": "number", "numeric_only": True},
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
    "historial-cambios",
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
        session["user_email"] = (user.email or "").strip()
        session["user_rol"] = (user.rol or "usuario").strip().lower()
        session["user_area"] = (user.area or "").strip()
        session["session_started_ts_ms"] = int(datetime.utcnow().timestamp() * 1000)
        session.pop("current_area", None)
        session.pop("logout_to_integrado", None)
        _registrar_usabilidad_evento(
            user_id=user.id,
            user_nombre=session.get("user_nombre") or "",
            user_email=session.get("user_email") or "",
            user_rol=session.get("user_rol") or "",
            area="",
            path="/login",
            metodo="POST",
            accion="Inicio de sesión",
        )
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
        session["user_email"] = (user.email or "").strip()
        session["user_rol"] = (user.rol or "usuario").strip().lower()
        session["user_area"] = (user.area or "").strip()
        session["session_started_ts_ms"] = int(datetime.utcnow().timestamp() * 1000)
        session.pop("current_area", None)
        session["logout_to_integrado"] = True
        _registrar_usabilidad_evento(
            user_id=user.id,
            user_nombre=session.get("user_nombre") or "",
            user_email=session.get("user_email") or "",
            user_rol=session.get("user_rol") or "",
            area="",
            path="/acceso-integrado",
            metodo="POST",
            accion="Inicio de sesión (integrado)",
        )
        return redirect(url_for("main.areas"))

    usuarios = _usuarios_activos()
    return render_template("login_integrado.html", usuarios=usuarios)


@bp.route("/logout")
def logout():
    to_integrado = bool(session.get("logout_to_integrado"))
    if session.get("user_id") is not None:
        _registrar_usabilidad_evento(
            user_id=session.get("user_id"),
            user_nombre=session.get("user_nombre") or "",
            user_email=session.get("user_email") or "",
            user_rol=session.get("user_rol") or "",
            area=session.get("current_area") or "",
            path="/logout",
            metodo="GET",
            accion="Cierre de sesión",
        )
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
    return render_template(
        "areas.html",
        areas_para_elegir=areas_para_elegir,
        sin_area=sin_area,
        desposte_en_mantenimiento=DESPOSTE_EN_MANTENIMIENTO,
    )


@bp.route("/entrar-area/<path:nombre>")
@login_required
def entrar_area(nombre):
    """Fija el área actual y redirige al dashboard. <path:nombre> permite nombres con «/» (p. ej. EXTERNOS/OTRAS AREAS)."""
    nombre = (nombre or "").strip().upper()
    if nombre == "DESPOSTE" and DESPOSTE_EN_MANTENIMIENTO:
        flash(
            "El área DESPOSTE se encuentra en mantenimiento. Estará disponible luego.",
            "error",
        )
        return redirect(url_for("main.areas"))
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


@bp.route("/dashboard/api/empleados-gh")
@login_required
@_require_current_area
def api_empleados_gh():
    """Autollenado GH por área:
    - Solo ACTIVO
    - Solo ingresos del año en curso (personal nuevo)
    - Si ya está en registro_asignaciones → nunca aparece (sin duplicados)
    No aplica en DESPOSTE.
    """
    from flask import jsonify
    import re as _re
    from app.utils.gestion_humana import area_gh_para_lockers, buscar_empleados, _parse_fecha_gh

    current_area = (session.get("current_area") or "").strip()
    if (current_area or "").strip().upper() == "DESPOSTE":
        return jsonify(
            {
                "ok": False,
                "error": "Gestión Humana no aplica mientras DESPOSTE esté en mantenimiento.",
                "area_lockers": current_area,
                "area_gh": None,
                "items": [],
                "meta": {
                    "total_gh_activos": 0,
                    "ya_registrados_en_app": 0,
                    "disponibles_mostrados": 0,
                    "omitidos_anio_anterior": 0,
                    "anio": datetime.now().year,
                    "nota": "DESPOSTE en mantenimiento.",
                },
            }
        )

    q = (request.args.get("q") or "").strip()
    try:
        limit = int(request.args.get("limit") or 40)
    except (TypeError, ValueError):
        limit = 40
    limit = max(1, min(limit, 100))
    anio_actual = datetime.now().year

    items, err = buscar_empleados(current_area, q=q, limit=500, solo_activos=True)
    total_gh = len(items or [])
    ya_reg_n = 0
    omitidos_anio = 0

    ya_reg = set()
    for (ident,) in RegistroAsignaciones.query.with_entities(
        RegistroAsignaciones.identificacion
    ).all():
        d = _re.sub(r"\D+", "", (ident or "").strip())
        if d:
            ya_reg.add(d)
            # Variante sin ceros a la izquierda (evita falsos "libres")
            d2 = d.lstrip("0") or d
            ya_reg.add(d2)

    filtrados = []
    if items:
        for it in items:
            raw_doc = str(
                it.get("documento")
                or it.get("identificacion")
                or it.get("id_cedula")
                or ""
            ).strip()
            doc = _re.sub(r"\D+", "", raw_doc)
            if not doc:
                continue
            doc_alt = doc.lstrip("0") or doc
            # Sin duplicados: si ya está en registro_asignaciones, no aparece.
            if doc in ya_reg or doc_alt in ya_reg:
                ya_reg_n += 1
                continue

            # Solo personal nuevo del año en curso.
            fecha_ing = (it.get("fecha_ingreso") or "").strip()
            dt_ing = _parse_fecha_gh(fecha_ing) if fecha_ing else None
            if dt_ing is None or dt_ing.year != anio_actual:
                omitidos_anio += 1
                continue

            filtrados.append(it)
            if len(filtrados) >= limit:
                break
    items = filtrados
    return jsonify(
        {
            "ok": err is None,
            "error": err,
            "area_lockers": current_area,
            "area_gh": area_gh_para_lockers(current_area),
            "items": items,
            "meta": {
                "total_gh_activos": total_gh,
                "ya_registrados_en_app": ya_reg_n,
                "disponibles_mostrados": len(items or []),
                "omitidos_anio_anterior": omitidos_anio,
                "anio": anio_actual,
                "nota": (
                    f"Solo ACTIVO de GH con ingreso {anio_actual} que aún no están "
                    "en registro_asignaciones. Sin duplicados."
                ),
            },
        }
    )


@bp.route("/dashboard/api/empleados-gh/<documento>")
@login_required
@_require_current_area
def api_empleado_gh_detalle(documento):
    """Detalle GH por cédula: solo ACTIVO del año en curso y no registrado en asignaciones."""
    from flask import jsonify
    import re as _re
    from app.utils.gestion_humana import obtener_empleado_por_cedula, _parse_fecha_gh

    current_area = (session.get("current_area") or "").strip()
    if (current_area or "").strip().upper() == "DESPOSTE":
        return jsonify({"ok": False, "error": "DESPOSTE en mantenimiento.", "item": None})

    item, err = obtener_empleado_por_cedula(documento, current_area=current_area)
    if item is None:
        return jsonify({"ok": False, "error": err, "item": None})

    estado = (item.get("estado") or "").strip().upper()
    if estado and estado != "ACTIVO":
        return jsonify(
            {
                "ok": False,
                "error": f"El empleado figura como {estado} en Gestión Humana; no aplica para registro nuevo.",
                "item": None,
            }
        )

    anio_actual = datetime.now().year
    dt_ing = _parse_fecha_gh((item.get("fecha_ingreso") or "").strip())
    if dt_ing is None or dt_ing.year != anio_actual:
        return jsonify(
            {
                "ok": False,
                "error": f"Solo se admiten ingresos del año {anio_actual} (personal nuevo).",
                "item": None,
            }
        )

    doc = _re.sub(r"\D+", "", str(item.get("documento") or documento or "").strip())
    doc_alt = (doc.lstrip("0") or doc) if doc else ""
    if doc:
        for (ident,) in RegistroAsignaciones.query.with_entities(
            RegistroAsignaciones.identificacion
        ).all():
            d = _re.sub(r"\D+", "", (ident or "").strip())
            d2 = d.lstrip("0") or d
            if d == doc or d2 == doc or d == doc_alt or d2 == doc_alt:
                return jsonify(
                    {
                        "ok": False,
                        "error": "Esta cédula ya está en registro de asignaciones.",
                        "item": None,
                    }
                )

    return jsonify({"ok": True, "error": None, "item": item})


@bp.route("/dashboard/api/retirados-gh")
@login_required
@_require_current_area
def api_retirados_gh():
    """Retirados de gestio_humana por área mapeada, más recientes primero."""
    from flask import jsonify
    from app.utils.gestion_humana import area_gh_para_lockers, buscar_retirados

    current_area = (session.get("current_area") or "").strip()
    q = (request.args.get("q") or "").strip()
    try:
        limit = int(request.args.get("limit") or 25)
    except (TypeError, ValueError):
        limit = 25
    items, err = buscar_retirados(current_area, q=q, limit=limit)
    return jsonify(
        {
            "ok": err is None,
            "error": err,
            "area_lockers": current_area,
            "area_gh": area_gh_para_lockers(current_area),
            "items": items,
        }
    )


@bp.route("/dashboard/api/sync-retirados-gh", methods=["POST", "GET"])
@login_required
@_require_current_area
def api_sync_retirados_gh():
    """Sincroniza retirados de GH → historial_retiros (solo inserta nuevos; no sobrescribe)."""
    from flask import jsonify
    from app.utils.gestion_humana import sincronizar_retirados_area

    if not _user_can_edit():
        return jsonify({"ok": False, "error": "Sin permiso para sincronizar.", "inserted": 0}), 403
    current_area = (session.get("current_area") or "").strip()
    result = sincronizar_retirados_area(current_area)
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


@bp.route("/dashboard/api/verificar-documento-personal")
@login_required
@_require_current_area
def api_verificar_documento_personal():
    """Indica si el documento ya está en Registro de personal / asignaciones."""
    from flask import jsonify
    from sqlalchemy import or_
    import re as _re

    documento = _re.sub(r"\D+", "", (request.args.get("documento") or "").strip())
    if not documento:
        return jsonify({"ok": True, "exists": False, "documento": ""})

    exists = False
    operario = None
    area_reg = None
    candidates = (
        RegistroAsignaciones.query.filter(
            or_(
                RegistroAsignaciones.identificacion == documento,
                RegistroAsignaciones.identificacion.like(f"%{documento}%"),
            )
        )
        .with_entities(
            RegistroAsignaciones.identificacion,
            RegistroAsignaciones.operario,
            RegistroAsignaciones.area,
        )
        .limit(50)
        .all()
    )
    for row in candidates:
        if _re.sub(r"\D+", "", (row[0] or "").strip()) == documento:
            exists = True
            operario = row[1]
            area_reg = row[2]
            break
    return jsonify(
        {
            "ok": True,
            "exists": exists,
            "documento": documento,
            "operario": operario,
            "area": area_reg,
            "message": (
                f"Ya está registrado: {operario or documento}"
                + (f" (área {area_reg})" if area_reg else "")
                if exists
                else None
            ),
        }
    )


def _dashboard_stats(current_area):
    """Calcula estadísticas del dashboard para un área. Usado por dashboard() y por api_dashboard_stats()."""
    from sqlalchemy import func, or_, and_, false
    # Total lockers: siempre desde BaseLockers (fuente de verdad).
    lf_base = _lockers_por_sesion_filter(BaseLockers, current_area)
    q_base = BaseLockers.query.filter(lf_base) if lf_base is not None else BaseLockers.query.filter(false())
    total_lockers = q_base.count()

    # Lockers disponibles: por regla de negocio = BaseLockers estado DISPONIBLE (áreas generales; DESPOSTE por filtro de sesión).
    disponibles = q_base.filter(db.func.lower(BaseLockers.estado) == "disponible").count()
    q_dot = BaseDotaciones.query.filter(_base_dotaciones_scope_filter(current_area))
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

    # Personal presupuestado: solo del área de sesión (códigos cortos LN/LOG/CAL ↔ nombre largo).
    personal_presupuestado = {"aprobados": 0, "contratados": 0, "por_contratar": 0}
    ca_u = (current_area or "").strip().upper()
    show_pp = bool(
        ca_u
        and ca_u != _ADMINISTRATIVA_UPPER
        and not _is_desposte_context(current_area)
        and not _is_externos_area(current_area)
    )
    if show_pp:
        aliases = _AREA_PP_ALIASES.get(ca_u, (ca_u,))
        pp = (
            PersonalPresupuestado.query.filter(
                db.func.upper(db.func.trim(PersonalPresupuestado.area)).in_(
                    [a.upper() for a in aliases]
                )
            )
            .order_by(PersonalPresupuestado.id.asc())
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
        "show_personal_presupuestado": show_pp,
        "show_dashboard_charts": ca_u != _ADMINISTRATIVA_UPPER,
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
        "historial-cambios": "Operaciones",
        "seca-botas-disponibles": "Lockers",
    }
    unique_categories = sorted(set(MODULE_CATEGORIES.values()))
    # Listado del sidebar: sin Ingreso de Lockers ni Ingreso de Dotación (acceso por botones del encabezado)
    modulos_sidebar = {k: v for k, v in MODULOS_CONFIG.items() if k not in ("ingreso-lockers", "ingreso-dotacion")}
    if _is_externos_area(current_area):
        modulos_sidebar = {k: v for k, v in modulos_sidebar.items() if k != "personal-presupuestado"}
    if (current_area or "").strip().upper() == _ADMINISTRATIVA_UPPER:
        modulos_sidebar = {
            k: v for k, v in modulos_sidebar.items() if k not in _MODULOS_OCULTOS_ADMINISTRATIVA
        }
    show_pp = bool(stats.get("show_personal_presupuestado"))
    show_charts = bool(stats.get("show_dashboard_charts", True))
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
        show_usabilidad_module=es_superadmin,
        chart_labels=chart_labels,
        chart_data=chart_data,
        module_categories=MODULE_CATEGORIES,
        unique_categories=unique_categories,
        current_area=current_area,
        show_personal_presupuestado=show_pp,
        show_dashboard_charts=show_charts,
    )


def _user_can_edit():
    """Usuario: solo consulta. Admin, coordinador y superadmin: pueden agregar, editar y eliminar en módulos."""
    return (session.get("user_rol") or "usuario").strip().lower() in ("superadmin", "admin", "coordinador")


def _superadmin_required(f):
    """Decorator: solo superadmin (acceso a Gestión de usuarios / usabilidad)."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect(url_for("main.login"))
        if (session.get("user_rol") or "").strip().lower() != "superadmin":
            flash("Solo el Super Administrador puede acceder a esta sección.", "error")
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


def _fmt_duracion_minutos(minutos):
    """Formato legible de duración (minutos → 1h 23m)."""
    try:
        m = max(0, int(round(float(minutos or 0))))
    except (TypeError, ValueError):
        m = 0
    if m < 60:
        return f"{m} min"
    h, r = divmod(m, 60)
    if r == 0:
        return f"{h} h"
    return f"{h} h {r} min"


def _usabilidad_modulo_de_path(path, accion=""):
    """Clasifica un path en módulo amigable para gráficos de uso."""
    path = (path or "").rstrip("/") or "/"
    accion_l = (accion or "").lower()
    if path in ("/login", "/acceso-integrado") or "inicio de sesión" in accion_l:
        return "Inicio de sesión"
    if path == "/logout" or "cierre de sesión" in accion_l or "inactividad" in accion_l:
        return "Cierre / desconexión"
    if path == "/areas" or path.startswith("/entrar-area/"):
        return "Selector de áreas"
    if path == "/dashboard":
        return "Dashboard"
    if path == "/dashboard/usuarios":
        return "Gestión de usuarios"
    if path == "/dashboard/usabilidad":
        return "Usabilidad"
    if path.startswith("/dashboard/registro/"):
        mid = path.rsplit("/", 1)[-1]
        return MODULOS_CONFIG.get(mid, {}).get("titulo", mid)
    if path.startswith("/dashboard/"):
        parts = [p for p in path.split("/") if p]
        if len(parts) >= 2 and parts[1] in MODULOS_CONFIG:
            return MODULOS_CONFIG[parts[1]].get("titulo", parts[1])
    return "Otros"


def _analizar_usabilidad(logs, *, ranking_limit=15, sesiones_limit=40, modulos_limit=12):
    """
    Deriva sesiones, tiempo en línea, desconexiones y uso por módulo
    a partir de eventos de navegación (sin schema nuevo).
    """
    gap_sec = max(int(IDLE_TIMEOUT_SECONDS or 1500), 300)
    # Orden cronológico para armar sesiones
    eventos = []
    for log in logs:
        local = _as_hora_colombia(log.creado_en) or _now_colombia()
        eventos.append(
            {
                "log": log,
                "local": local,
                "user_key": log.user_id or (log.user_email or log.user_nombre or "anon"),
                "nombre": (log.user_nombre or log.user_email or f"Usuario {log.user_id}" or "—").strip(),
                "email": (log.user_email or "").strip(),
                "rol": (log.user_rol or "").strip(),
                "path": log.path or "",
                "accion": log.accion or "",
                "area": (log.area or "").strip(),
                "modulo": _usabilidad_modulo_de_path(log.path, log.accion),
            }
        )
    eventos.sort(key=lambda e: (str(e["user_key"]), e["local"]))

    por_usuario = {}
    for ev in eventos:
        por_usuario.setdefault(ev["user_key"], []).append(ev)

    sesiones = []
    tiempo_por_usuario = {}
    modulos_count = {}
    horas_count = [0] * 24
    areas_count = {}
    cierres_explicitos = 0
    cierres_inactividad = 0

    for uid, evs in por_usuario.items():
        ses_actual = None
        for ev in evs:
            modulos_count[ev["modulo"]] = modulos_count.get(ev["modulo"], 0) + 1
            horas_count[ev["local"].hour] += 1
            if ev["area"]:
                areas_count[ev["area"]] = areas_count.get(ev["area"], 0) + 1

            accion_l = (ev["accion"] or "").lower()
            es_login = "inicio de sesión" in accion_l
            es_logout = (
                "cierre de sesión" in accion_l
                or "inactividad" in accion_l
                or (ev["path"] or "").rstrip("/") == "/logout"
            )

            if ses_actual is None or es_login:
                if ses_actual is not None and not ses_actual.get("fin"):
                    ses_actual["fin"] = ses_actual["eventos"][-1]["local"]
                    ses_actual["cierre"] = "sin cierre registrado"
                    sesiones.append(ses_actual)
                ses_actual = {
                    "user_key": uid,
                    "nombre": ev["nombre"],
                    "email": ev["email"],
                    "rol": ev["rol"],
                    "inicio": ev["local"],
                    "fin": None,
                    "cierre": "en curso / sin cierre",
                    "eventos": [ev],
                    "modulos": {},
                    "areas": set(),
                }
            else:
                prev = ses_actual["eventos"][-1]["local"]
                gap = (ev["local"] - prev).total_seconds()
                if gap > gap_sec:
                    ses_actual["fin"] = prev
                    ses_actual["cierre"] = "posible inactividad (sin actividad)"
                    sesiones.append(ses_actual)
                    cierres_inactividad += 1
                    ses_actual = {
                        "user_key": uid,
                        "nombre": ev["nombre"],
                        "email": ev["email"],
                        "rol": ev["rol"],
                        "inicio": ev["local"],
                        "fin": None,
                        "cierre": "en curso / sin cierre",
                        "eventos": [ev],
                        "modulos": {},
                        "areas": set(),
                    }
                else:
                    ses_actual["eventos"].append(ev)

            if ses_actual is not None:
                ses_actual["modulos"][ev["modulo"]] = ses_actual["modulos"].get(ev["modulo"], 0) + 1
                if ev["area"]:
                    ses_actual["areas"].add(ev["area"])
                if es_logout:
                    ses_actual["fin"] = ev["local"]
                    if "inactividad" in accion_l:
                        ses_actual["cierre"] = "Desconexión por inactividad"
                        cierres_inactividad += 1
                    else:
                        ses_actual["cierre"] = "Cierre de sesión"
                        cierres_explicitos += 1
                    sesiones.append(ses_actual)
                    ses_actual = None

        if ses_actual is not None:
            ses_actual["fin"] = ses_actual["eventos"][-1]["local"]
            sesiones.append(ses_actual)

    # Duraciones y ranking de usuarios
    for s in sesiones:
        ini = s["inicio"]
        fin = s["fin"] or s["eventos"][-1]["local"]
        # Tiempo online ≈ suma de gaps internos (máx. gap_sec) + mínimo 1 min si hay actividad
        total_sec = 0
        evs = s["eventos"]
        for i in range(1, len(evs)):
            gap = (evs[i]["local"] - evs[i - 1]["local"]).total_seconds()
            if 0 < gap <= gap_sec:
                total_sec += gap
        if total_sec <= 0:
            total_sec = max(60, (fin - ini).total_seconds()) if fin and ini else 60
        mins = max(1, int(round(total_sec / 60.0)))
        s["minutos"] = mins
        s["duracion"] = _fmt_duracion_minutos(mins)
        s["inicio_txt"] = ini.strftime("%H:%M") if ini else "—"
        s["fin_txt"] = fin.strftime("%H:%M") if fin else "—"
        s["fecha_txt"] = ini.strftime("%d/%m/%Y") if ini else "—"
        s["n_eventos"] = len(evs)
        s["areas_txt"] = ", ".join(sorted(s["areas"])) if s["areas"] else "—"
        top_mod = sorted(s["modulos"].items(), key=lambda x: -x[1])[:3]
        s["modulos_txt"] = ", ".join(f"{m} ({n})" for m, n in top_mod) if top_mod else "—"
        uk = s["user_key"]
        if uk not in tiempo_por_usuario:
            tiempo_por_usuario[uk] = {
                "nombre": s["nombre"],
                "email": s["email"],
                "minutos": 0,
                "sesiones": 0,
                "eventos": 0,
            }
        tiempo_por_usuario[uk]["minutos"] += mins
        tiempo_por_usuario[uk]["sesiones"] += 1
        tiempo_por_usuario[uk]["eventos"] += s["n_eventos"]

    ranking = sorted(tiempo_por_usuario.values(), key=lambda x: -x["minutos"])
    for r in ranking:
        r["duracion"] = _fmt_duracion_minutos(r["minutos"])

    modulos_sorted = sorted(modulos_count.items(), key=lambda x: -x[1])[: max(1, int(modulos_limit or 12))]
    areas_sorted = sorted(areas_count.items(), key=lambda x: -x[1])[:10]
    sesiones_ord = sorted(sesiones, key=lambda s: s["inicio"] or datetime.min, reverse=True)
    rk_lim = ranking_limit if ranking_limit is not None else 15
    ses_lim = sesiones_limit if sesiones_limit is not None else 40
    ranking_out = ranking if rk_lim is None else ranking[:rk_lim]
    sesiones_out = sesiones_ord if ses_lim is None else sesiones_ord[:ses_lim]

    total_min = sum(r["minutos"] for r in ranking)
    return {
        "kpis": {
            "usuarios": len(ranking),
            "sesiones": len(sesiones),
            "eventos": len(eventos),
            "minutos_online": total_min,
            "tiempo_online": _fmt_duracion_minutos(total_min),
            "cierres": cierres_explicitos,
            "inactividad": cierres_inactividad,
        },
        "ranking": ranking_out,
        "sesiones": sesiones_out,
        "chart_usuarios_labels": [r["nombre"][:22] for r in ranking[:10]],
        "chart_usuarios_data": [r["minutos"] for r in ranking[:10]],
        "chart_modulos_labels": [m for m, _ in modulos_sorted],
        "chart_modulos_data": [n for _, n in modulos_sorted],
        "chart_horas_labels": [f"{h:02d}h" for h in range(24)],
        "chart_horas_data": horas_count,
        "chart_areas_labels": [a for a, _ in areas_sorted],
        "chart_areas_data": [n for _, n in areas_sorted],
    }


def _usabilidad_excluir_superadmin(query):
    """Solo actividad de usuarios que no son superadmin."""
    return query.filter(
        db.or_(
            UsabilidadLog.user_rol.is_(None),
            UsabilidadLog.user_rol == "",
            db.func.lower(db.func.trim(UsabilidadLog.user_rol)) != "superadmin",
        )
    )


def _usabilidad_rango_periodo(fecha_str, periodo="diario"):
    """
    Devuelve (inicio_utc, fin_utc, etiqueta, fecha_ref) según periodo.
    fecha_str = día de referencia (AAAA-MM-DD) en hora Colombia.
    periodo: diario | semanal | mensual
    """
    periodo = (periodo or "diario").strip().lower()
    if periodo not in ("diario", "semanal", "mensual"):
        periodo = "diario"
    try:
        dia = datetime.strptime(fecha_str, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        dia = _now_colombia().date()
        fecha_str = dia.strftime("%Y-%m-%d")

    if periodo == "semanal":
        # Semana lunes–domingo que contiene el día
        inicio_dia = dia - timedelta(days=dia.weekday())
        fin_dia = inicio_dia + timedelta(days=7)
        etiqueta = f"Semana {inicio_dia.strftime('%d/%m/%Y')} – {(fin_dia - timedelta(days=1)).strftime('%d/%m/%Y')}"
    elif periodo == "mensual":
        inicio_dia = dia.replace(day=1)
        if inicio_dia.month == 12:
            fin_dia = inicio_dia.replace(year=inicio_dia.year + 1, month=1)
        else:
            fin_dia = inicio_dia.replace(month=inicio_dia.month + 1)
        etiqueta = inicio_dia.strftime("%B %Y").capitalize()
        # Mes en español aproximado
        meses = {
            1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio",
            7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
        }
        etiqueta = f"{meses.get(inicio_dia.month, inicio_dia.strftime('%m'))} {inicio_dia.year}"
    else:
        inicio_dia = dia
        fin_dia = dia + timedelta(days=1)
        etiqueta = dia.strftime("%d/%m/%Y")
        periodo = "diario"

    inicio_local = datetime(inicio_dia.year, inicio_dia.month, inicio_dia.day, 0, 0, 0, tzinfo=_TZ_COLOMBIA)
    fin_local = datetime(fin_dia.year, fin_dia.month, fin_dia.day, 0, 0, 0, tzinfo=_TZ_COLOMBIA)
    inicio_utc = inicio_local.astimezone(_TZ_UTC).replace(tzinfo=None)
    fin_utc = fin_local.astimezone(_TZ_UTC).replace(tzinfo=None)
    return inicio_utc, fin_utc, etiqueta, fecha_str, periodo


def _usabilidad_logs_periodo(fecha_str, periodo="diario", limit=8000):
    inicio_utc, fin_utc, etiqueta, fecha_ok, periodo_ok = _usabilidad_rango_periodo(fecha_str, periodo)
    query = _usabilidad_excluir_superadmin(UsabilidadLog.query)
    query = query.filter(UsabilidadLog.creado_en >= inicio_utc, UsabilidadLog.creado_en < fin_utc)
    logs = query.order_by(UsabilidadLog.creado_en.desc()).limit(limit).all()
    return logs, etiqueta, fecha_ok, periodo_ok


def _usabilidad_grupos_detalle(logs):
    grupos = []
    grupo_actual = None
    for log in logs:
        creado_local = _as_hora_colombia(log.creado_en) or _now_colombia()
        log.hora_local = creado_local.strftime("%H:%M:%S")
        log.fecha_local = creado_local.strftime("%d/%m/%Y")
        log.modulo_label = _usabilidad_modulo_de_path(log.path, log.accion)
        uk = f"{log.user_id or ''}|{(log.user_email or '').lower()}"
        label = (log.user_nombre or log.user_email or f"Usuario {log.user_id}" or "—").strip()
        if grupo_actual is None or grupo_actual["key"] != uk:
            grupo_actual = {
                "key": uk,
                "label": label,
                "email": log.user_email or "",
                "rol": log.user_rol or "",
                "registros": [],
            }
            grupos.append(grupo_actual)
        grupo_actual["registros"].append(log)
    return grupos


def _generar_reporte_usabilidad_xlsx(logs, analytics, etiqueta, periodo):
    """Genera un Excel detallado de usabilidad (varios sheets)."""
    from io import BytesIO

    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    except ImportError as exc:
        raise RuntimeError("Falta openpyxl para generar el reporte.") from exc

    wb = Workbook()
    thin = Border(
        left=Side(style="thin", color="CBD5E1"),
        right=Side(style="thin", color="CBD5E1"),
        top=Side(style="thin", color="CBD5E1"),
        bottom=Side(style="thin", color="CBD5E1"),
    )
    header_fill = PatternFill("solid", fgColor="1E293B")
    header_font = Font(color="F8FAFC", bold=True)
    title_font = Font(bold=True, size=13)

    def _style_header(ws, row, cols):
        for c in range(1, cols + 1):
            cell = ws.cell(row=row, column=c)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = thin

    # --- Resumen ---
    ws = wb.active
    ws.title = "Resumen"
    ws["A1"] = "Reporte de usabilidad — LockerBeef"
    ws["A1"].font = title_font
    ws["A2"] = f"Periodo: {periodo}"
    ws["A3"] = f"Rango: {etiqueta}"
    ws["A4"] = f"Generado: {_now_colombia().strftime('%d/%m/%Y %H:%M')}"
    ws["A5"] = "Nota: no incluye actividad de superadmin."
    k = analytics.get("kpis") or {}
    rows_kpi = [
        ("Usuarios activos", k.get("usuarios", 0)),
        ("Tiempo en línea", k.get("tiempo_online", "0 min")),
        ("Sesiones", k.get("sesiones", 0)),
        ("Eventos", k.get("eventos", 0)),
        ("Cierres de sesión", k.get("cierres", 0)),
        ("Desconexiones por inactividad", k.get("inactividad", 0)),
    ]
    ws["A7"] = "Indicador"
    ws["B7"] = "Valor"
    _style_header(ws, 7, 2)
    for i, (lab, val) in enumerate(rows_kpi, start=8):
        ws.cell(row=i, column=1, value=lab).border = thin
        ws.cell(row=i, column=2, value=val).border = thin
    ws.column_dimensions["A"].width = 36
    ws.column_dimensions["B"].width = 22

    # --- Tiempo por usuario ---
    ws2 = wb.create_sheet("Tiempo por usuario")
    headers2 = ["Usuario", "Email", "Minutos online", "Duración", "Sesiones", "Eventos"]
    for i, h in enumerate(headers2, start=1):
        ws2.cell(row=1, column=i, value=h)
    _style_header(ws2, 1, len(headers2))
    for r_i, r in enumerate(analytics.get("ranking") or [], start=2):
        vals = [r.get("nombre"), r.get("email"), r.get("minutos"), r.get("duracion"), r.get("sesiones"), r.get("eventos")]
        for c_i, v in enumerate(vals, start=1):
            cell = ws2.cell(row=r_i, column=c_i, value=v)
            cell.border = thin
    for col, w in zip("ABCDEF", (28, 34, 16, 14, 12, 12)):
        ws2.column_dimensions[col].width = w

    # --- Sesiones ---
    ws3 = wb.create_sheet("Sesiones")
    headers3 = ["Fecha", "Usuario", "Email", "Inicio", "Fin", "Duración", "Cierre", "Eventos", "Áreas", "Módulos top"]
    for i, h in enumerate(headers3, start=1):
        ws3.cell(row=1, column=i, value=h)
    _style_header(ws3, 1, len(headers3))
    for r_i, s in enumerate(analytics.get("sesiones") or [], start=2):
        vals = [
            s.get("fecha_txt"), s.get("nombre"), s.get("email"), s.get("inicio_txt"),
            s.get("fin_txt"), s.get("duracion"), s.get("cierre"), s.get("n_eventos"),
            s.get("areas_txt"), s.get("modulos_txt"),
        ]
        for c_i, v in enumerate(vals, start=1):
            cell = ws3.cell(row=r_i, column=c_i, value=v)
            cell.border = thin
    for col, w in zip("ABCDEFGHIJ", (12, 24, 30, 10, 10, 12, 28, 10, 24, 40)):
        ws3.column_dimensions[col].width = w

    # --- Uso por módulo ---
    ws4 = wb.create_sheet("Uso por modulo")
    ws4.cell(row=1, column=1, value="Módulo")
    ws4.cell(row=1, column=2, value="Eventos")
    _style_header(ws4, 1, 2)
    for r_i, (lab, n) in enumerate(
        zip(analytics.get("chart_modulos_labels") or [], analytics.get("chart_modulos_data") or []),
        start=2,
    ):
        ws4.cell(row=r_i, column=1, value=lab).border = thin
        ws4.cell(row=r_i, column=2, value=n).border = thin
    ws4.column_dimensions["A"].width = 34
    ws4.column_dimensions["B"].width = 12

    # --- Eventos detalle ---
    ws5 = wb.create_sheet("Eventos detalle")
    headers5 = ["Fecha", "Hora", "Usuario", "Email", "Rol", "Área", "Módulo", "Acción", "Método", "Ruta"]
    for i, h in enumerate(headers5, start=1):
        ws5.cell(row=1, column=i, value=h)
    _style_header(ws5, 1, len(headers5))
    # Cronológico ascendente para lectura del reporte
    logs_asc = sorted(logs, key=lambda x: x.creado_en or datetime.min)
    for r_i, log in enumerate(logs_asc, start=2):
        local = _as_hora_colombia(log.creado_en) or _now_colombia()
        vals = [
            local.strftime("%d/%m/%Y"),
            local.strftime("%H:%M:%S"),
            log.user_nombre or "",
            log.user_email or "",
            log.user_rol or "",
            log.area or "",
            _usabilidad_modulo_de_path(log.path, log.accion),
            log.accion or "",
            log.metodo or "",
            log.path or "",
        ]
        for c_i, v in enumerate(vals, start=1):
            cell = ws5.cell(row=r_i, column=c_i, value=v)
            cell.border = thin
    for col, w in zip("ABCDEFGHIJ", (12, 10, 24, 30, 12, 16, 22, 36, 10, 40)):
        ws5.column_dimensions[col].width = w

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


@bp.route("/dashboard/usabilidad")
@login_required
@_superadmin_required
def usabilidad():
    """Analítica gráfica de usabilidad (sin superadmin). Solo filtro por fecha."""
    fecha = (request.args.get("fecha") or "").strip()
    if not fecha:
        fecha = _now_colombia().strftime("%Y-%m-%d")

    logs, etiqueta, fecha, _periodo = _usabilidad_logs_periodo(fecha, "diario", limit=3000)
    analytics = _analizar_usabilidad(logs)
    grupos = _usabilidad_grupos_detalle(logs)

    return render_template(
        "usabilidad.html",
        grupos=grupos,
        logs=logs,
        analytics=analytics,
        filtro_fecha=fecha,
        periodo_etiqueta=etiqueta,
        total=len(logs),
    )


@bp.route("/dashboard/usabilidad/reporte")
@login_required
@_superadmin_required
def usabilidad_reporte():
    """Descarga reporte Excel detallado: diario | semanal | mensual."""
    fecha = (request.args.get("fecha") or "").strip() or _now_colombia().strftime("%Y-%m-%d")
    periodo = (request.args.get("periodo") or "diario").strip().lower()
    if periodo not in ("diario", "semanal", "mensual"):
        periodo = "diario"

    logs, etiqueta, fecha_ok, periodo_ok = _usabilidad_logs_periodo(fecha, periodo, limit=20000)
    analytics = _analizar_usabilidad(
        logs,
        ranking_limit=None,
        sesiones_limit=None,
        modulos_limit=50,
    )
    try:
        buf = _generar_reporte_usabilidad_xlsx(logs, analytics, etiqueta, periodo_ok)
    except RuntimeError as exc:
        flash(str(exc), "error")
        return redirect(url_for("main.usabilidad", fecha=fecha_ok))

    safe_label = re.sub(r"[^\w\-]+", "_", etiqueta)[:60]
    filename = f"usabilidad_{periodo_ok}_{safe_label}.xlsx"
    return send_file(
        buf,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def _registro_form_view(modulo_id):
    """Vistas independientes de solo formulario: Ingreso dotación → BaseDotaciones; Registro personal → RegistroAsignaciones; Ingreso lockers → BaseLockers."""
    current_area = (session.get("current_area") or "").strip()
    if not current_area:
        flash("Selecciona un área de trabajo.", "error")
        return redirect(url_for("main.areas"))
    can_edit = _user_can_edit()
    ex_unlock = _is_externos_area(current_area)
    def_area_personal = "" if ex_unlock else current_area
    def_area_lockers = "" if ex_unlock else current_area

    def _ctx_registro_personal(**extra):
        from app.utils.gestion_humana import area_gh_para_lockers

        base = dict(
            modulo_id=modulo_id,
            titulo="Registro de Personal",
            form_fields=_FORM_REGISTRO_PERSONAL,
            can_edit=can_edit,
            default_area=def_area_personal,
            unlock_area_field=ex_unlock,
            gh_autofill=True,
            gh_area=area_gh_para_lockers(current_area),
            api_empleados_gh=url_for("main.api_empleados_gh"),
            api_verificar_documento=url_for("main.api_verificar_documento_personal"),
        )
        base.update(extra)
        return base
    if request.method == "POST" and can_edit:
        if modulo_id == "ingreso-dotacion":
            ne_err = _digits_only_field_error(_FORM_INGRESO_DOTACION, request.form)
            if ne_err:
                flash(ne_err, "error")
                return render_template(
                    "registro_form.html",
                    modulo_id=modulo_id,
                    titulo="Ingreso de Dotación",
                    form_fields=_FORM_INGRESO_DOTACION,
                    can_edit=can_edit,
                )
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
            if _area_uso_solo_en_sesion_externas(area_uso) and not _is_externos_area(current_area):
                flash(
                    f"PIELES, SUBPRODUCTOS, PLANTA EMERGENCIA y el uso «{_LABEL_AREA_EXTERNAS_OTRAS}» solo se registran con el área de trabajo «{_LABEL_AREA_EXTERNAS_OTRAS}».",
                    "error",
                )
                return render_template("registro_form.html", modulo_id=modulo_id, titulo="Ingreso de Dotación", form_fields=_FORM_INGRESO_DOTACION, can_edit=can_edit)
            if _codigo_base_dotaciones_duplicado(codigo):
                flash("El código ya está registrado en Base de Dotaciones.", "error")
                return render_template("registro_form.html", modulo_id=modulo_id, titulo="Ingreso de Dotación", form_fields=_FORM_INGRESO_DOTACION, can_edit=can_edit)
            estado = _normalize_estado_base_dotaciones("DISPONIBLE")
            obj = BaseDotaciones(codigo=codigo, cantidad=cantidad, talla=talla, estado=estado, area_uso=area_uso)
            db.session.add(obj)
            _registrar_cambio("ingreso-dotacion", "CREAR", obj=obj)
            db.session.commit()
            flash("Dotación registrada en Base de Dotaciones.", "success")
            return redirect(url_for("main.registro_form", modulo_id=modulo_id))
        if modulo_id == "registro-personal":
            ne_err = _digits_only_field_error(_FORM_REGISTRO_PERSONAL, request.form)
            if ne_err:
                flash(ne_err, "error")
                return render_template("registro_form.html", **_ctx_registro_personal())
            nombre = (request.form.get("nombre") or "").strip()
            documento = (request.form.get("documento") or "").strip()
            if not nombre or not documento:
                flash("Nombre y documento son obligatorios.", "error")
                return render_template("registro_form.html", **_ctx_registro_personal())
            # Duplicado: no permitir el mismo documento si ya está en asignaciones/personal
            doc_norm = re.sub(r"\D+", "", documento)
            if doc_norm:
                from sqlalchemy import or_ as _or

                _dup = False
                _op = _ar = None
                for _ident, _op0, _ar0 in (
                    RegistroAsignaciones.query.filter(
                        _or(
                            RegistroAsignaciones.identificacion == documento,
                            RegistroAsignaciones.identificacion == doc_norm,
                            RegistroAsignaciones.identificacion.like(f"%{doc_norm}%"),
                        )
                    )
                    .with_entities(
                        RegistroAsignaciones.identificacion,
                        RegistroAsignaciones.operario,
                        RegistroAsignaciones.area,
                    )
                    .limit(50)
                    .all()
                ):
                    if re.sub(r"\D+", "", (_ident or "").strip()) == doc_norm:
                        _dup = True
                        _op, _ar = _op0, _ar0
                        break
                if _dup:
                    flash(
                        f"Este documento ya está registrado"
                        + (f" como «{_op}»" if _op else "")
                        + (f" en el área {_ar}." if _ar else ".")
                        + " No se permiten duplicados.",
                        "error",
                    )
                    return render_template("registro_form.html", **_ctx_registro_personal())
            talla_val = (request.form.get("talla") or "").strip()
            if not talla_val:
                flash("Seleccione una talla.", "error")
                return render_template("registro_form.html", **_ctx_registro_personal())
            area_personal = (request.form.get("area") or "").strip()
            if ex_unlock:
                if not area_personal:
                    flash("Indique el área del personal (operación externa).", "error")
                    return render_template(
                        "registro_form.html",
                        **_ctx_registro_personal(unlock_area_field=True),
                    )
                if area_personal.strip().upper() in _INTERNAS_PLANTA_UPPER:
                    flash("Esa área corresponde a planta interna; use una etiqueta de operación externa.", "error")
                    return render_template(
                        "registro_form.html",
                        **_ctx_registro_personal(default_area=area_personal, unlock_area_field=True),
                    )
            obj = RegistroAsignaciones(
                id_asignaciones=_get_next_id_asignaciones(),
                operario=nombre,
                identificacion=documento,
                email=(request.form.get("email") or "").strip(),
                telefono=(request.form.get("telefono") or "").strip(),
                cargo=(request.form.get("cargo") or "").strip(),
                area=area_personal if ex_unlock else current_area,
                talla_operarios=talla_val,
                area_lockers=(request.form.get("area_lockers") or "").strip(),
                estado="Activo",
                fecha_asignacion=datetime.utcnow(),
                codigo_lockets="",
                codigo_dotacion="",
                es_planta_desposte=_registro_manual_es_planta_desposte(current_area),
            )
            db.session.add(obj)
            _registrar_cambio("registro-personal", "CREAR", obj=obj)
            db.session.commit()
            flash("Personal registrado. Aparece en Personal Registrado hasta que se asigne locker o dotación.", "success")
            return redirect(url_for("main.modulo", modulo_id="registro-personal"))
        if modulo_id == "ingreso-lockers":
            ne_err = _digits_only_field_error(_FORM_INGRESO_LOCKERS, request.form)
            if ne_err:
                flash(ne_err, "error")
                return render_template(
                    "registro_form.html",
                    modulo_id=modulo_id,
                    titulo="Ingreso de Lockers",
                    form_fields=_FORM_INGRESO_LOCKERS,
                    can_edit=can_edit,
                    default_area=def_area_lockers,
                    unlock_area_field=ex_unlock,
                )
            codigo = (request.form.get("codigo") or "").strip()
            area = (request.form.get("area") or "").strip()
            if ex_unlock:
                if not area:
                    flash("Indique el área del locker (operación externa).", "error")
                    return render_template(
                        "registro_form.html",
                        modulo_id=modulo_id,
                        titulo="Ingreso de Lockers",
                        form_fields=_FORM_INGRESO_LOCKERS,
                        can_edit=can_edit,
                        default_area=def_area_lockers,
                        unlock_area_field=True,
                    )
                if area.strip().upper() in _INTERNAS_PLANTA_UPPER:
                    flash(
                        f"No puede usar un código de área interna de planta en «{_LABEL_AREA_EXTERNAS_OTRAS}».",
                        "error",
                    )
                    return render_template(
                        "registro_form.html",
                        modulo_id=modulo_id,
                        titulo="Ingreso de Lockers",
                        form_fields=_FORM_INGRESO_LOCKERS,
                        can_edit=can_edit,
                        default_area=area,
                        unlock_area_field=True,
                    )
            else:
                area = area or current_area
            area_lockers = (request.form.get("area_lockers") or "").strip()
            cantidad_raw = (request.form.get("cantidad") or "").strip() or "1"
            cantidad = max(1, int(cantidad_raw))
            if not codigo:
                flash("El código es obligatorio.", "error")
                return render_template(
                    "registro_form.html",
                    modulo_id=modulo_id,
                    titulo="Ingreso de Lockers",
                    form_fields=_FORM_INGRESO_LOCKERS,
                    can_edit=can_edit,
                    default_area=def_area_lockers,
                    unlock_area_field=ex_unlock,
                )
            if _codigo_base_lockers_duplicado(codigo):
                flash("El código ya está registrado en Base de Lockers.", "error")
                return render_template(
                    "registro_form.html",
                    modulo_id=modulo_id,
                    titulo="Ingreso de Lockers",
                    form_fields=_FORM_INGRESO_LOCKERS,
                    can_edit=can_edit,
                    default_area=def_area_lockers,
                    unlock_area_field=ex_unlock,
                )
            if cantidad > 1:
                flash("Cada código debe ser único. Indique cantidad 1 o registre otro código en un envío aparte.", "error")
                return render_template(
                    "registro_form.html",
                    modulo_id=modulo_id,
                    titulo="Ingreso de Lockers",
                    form_fields=_FORM_INGRESO_LOCKERS,
                    can_edit=can_edit,
                    default_area=def_area_lockers,
                    unlock_area_field=ex_unlock,
                )
            estado = _normalize_estado_base_lockers("DISPONIBLE")
            for _ in range(cantidad):
                obj = BaseLockers(codigo=codigo, area=area, subarea="", area_lockers=area_lockers, estado=estado)
                db.session.add(obj)
                _registrar_cambio("ingreso-lockers", "CREAR", obj=obj)
            db.session.commit()
            flash("Locker(s) registrado(s) en Base de Lockers.", "success")
            return redirect(url_for("main.registro_form", modulo_id=modulo_id))
    if modulo_id == "ingreso-dotacion":
        return render_template("registro_form.html", modulo_id=modulo_id, titulo="Ingreso de Dotación", form_fields=_FORM_INGRESO_DOTACION, can_edit=can_edit)
    if modulo_id == "registro-personal":
        return render_template(
            "registro_form.html",
            **_ctx_registro_personal(estado_activo=True),
        )
    if modulo_id == "ingreso-lockers":
        return render_template(
            "registro_form.html",
            modulo_id=modulo_id,
            titulo="Ingreso de Lockers",
            form_fields=_FORM_INGRESO_LOCKERS,
            can_edit=can_edit,
            default_area=def_area_lockers,
            unlock_area_field=ex_unlock,
        )
    return None


# Áreas operativas para el formulario de ingreso de dotación (encabezado / registro_form).
INGRESO_DOTACION_AREA_OPCIONES = frozenset(
    (
        "PROCESO",
        "VISITAS",
        "MTTO",
        "PLANTA EMERGENCIA",
        _LABEL_AREA_EXTERNAS_OTRAS,
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
    "PIELES",
    "SUBPRODUCTOS",
    _LABEL_AREA_EXTERNAS_OTRAS,
    "EXTERNOS",
)

# Campos para los formularios de registro independientes (no almacenan en su tabla original)
_FORM_INGRESO_DOTACION = [
    {"name": "codigo", "label": "Código", "type": "text", "required": True, "numeric_only": True},
    {"name": "cantidad", "label": "Cantidad", "type": "number", "numeric_only": True},
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
    {"name": "documento", "label": "Documento", "type": "text", "required": True, "numeric_only": True},
    {"name": "nombre", "label": "Nombre", "type": "text", "required": True},
    {"name": "area", "label": "Área", "type": "text"},
    {"name": "talla", "label": "Talla", "type": "select", "options": TALLAS_SELECT_OPCIONES, "required": True},
    {"name": "area_lockers", "label": "Área Lockers", "type": "select", "options": ["", "VESTIER HOMBRES", "VESTIER MUJERES", "ADMINISTRATIVO"]},
]
_FORM_INGRESO_LOCKERS = [
    {"name": "codigo", "label": "Código de Locker", "type": "text", "required": True, "numeric_only": True},
    {"name": "area", "label": "Área", "type": "text"},
    {"name": "area_lockers", "label": "Área Lockers", "type": "select", "options": ["VESTIDOR HOMBRES", "VESTIDOR MUJERES", "ADMINISTRATIVOS"]},
    {"name": "cantidad", "label": "Cantidad (Lockers a agregar)", "type": "number", "numeric_only": True},
    {"name": "estado", "label": "Estado", "type": "text", "readonly": True, "default": "Disponible"},
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
    if modulo_id == "personal-presupuestado" and _is_externos_area(session.get("current_area")):
        flash(f"El módulo Personal presupuestado no está disponible en el área «{_LABEL_AREA_EXTERNAS_OTRAS}».", "error")
        return redirect(url_for("main.dashboard"))
    if (
        modulo_id in _MODULOS_OCULTOS_ADMINISTRATIVA
        and (session.get("current_area") or "").strip().upper() == _ADMINISTRATIVA_UPPER
    ):
        flash(
            "Ese módulo no está disponible en el área ADMINISTRATIVA.",
            "error",
        )
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
    if modulo_id == "registro-personal" and _is_externos_area(current_area):
        form_fields = [dict(f) for f in form_fields]
        for f in form_fields:
            if f.get("name") == "area":
                f["type"] = "text"
                f["label"] = "Área (operación externa)"
                f["required"] = True
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
        if modulo_id == "historial-cambios":
            flash("El Historial de Cambios es solo consulta; no se puede modificar.", "error")
            return redirect(url_for("main.modulo", modulo_id=modulo_id))

        eliminar_id = request.form.get("eliminar_id", type=int)
        edit_id = request.form.get("edit_id", type=int)
        next_page = max(1, request.form.get("page", 1, type=int))

        if eliminar_id:
            obj = Model.query.get(eliminar_id)
            if obj:
                if user_rol == "coordinador" and area_key and user_area and not _is_externos_area(current_area):
                    if getattr(obj, area_key, None) != user_area:
                        flash("No puede eliminar registros de otra área.", "error")
                        return redirect(url_for("main.modulo", modulo_id=modulo_id, page=next_page))
                # Eliminación manual / cancelación: NO va a historial de retiros.
                # Historial de retiros solo se llena desde Gestión Humana (INACTIVO/retirado).
                if Model == RegistroAsignaciones:
                    cod_dot = (getattr(obj, "codigo_dotacion", None) or "").strip()
                    cod_lock = (getattr(obj, "codigo_lockets", None) or "").strip()
                    cod_seca = (getattr(obj, "codigo_seca_botas", None) or "").strip()
                    reg_area = (getattr(obj, "area", None) or "").strip()
                    if cod_dot:
                        _liberar_dotacion(cod_dot, area=reg_area)
                    if cod_lock:
                        _liberar_locker(cod_lock, area=reg_area)
                    if cod_seca:
                        _liberar_seca_botas(cod_seca)
                _registrar_cambio(modulo_id, "ELIMINAR", obj=obj)
                db.session.delete(obj)
                db.session.commit()
                if Model == RegistroAsignaciones:
                    flash(
                        "Registro eliminado. Los códigos vuelven a estar disponibles. "
                        "No se envió a Historial de Retiros (solo aplica por baja en Gestión Humana).",
                        "success",
                    )
                else:
                    flash("Registro eliminado.", "success")
            return redirect(url_for("main.modulo", modulo_id=modulo_id, page=next_page))

        if edit_id:
            obj = Model.query.get(edit_id)
            if not obj:
                flash("Registro no encontrado.", "error")
                return redirect(url_for("main.modulo", modulo_id=modulo_id))
            if user_rol == "coordinador" and area_key and user_area and not _is_externos_area(current_area):
                if getattr(obj, area_key, None) != user_area:
                    flash("No puede editar registros de otra área.", "error")
                    return redirect(url_for("main.modulo", modulo_id=modulo_id))
            ne_err = _digits_only_field_error(form_fields, request.form)
            if ne_err:
                flash(ne_err, "error")
                session["modulo_edit_form"] = {modulo_id: dict(request.form)}
                return redirect(url_for("main.modulo", modulo_id=modulo_id, edit_id=edit_id, page=next_page))
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
            # Personal Pendiente: área fija (toma área actual; no editable) — excluye DESPOSTE
            if (
                modulo_id == "registro-personal"
                and Model == RegistroAsignaciones
                and current_area
                and current_area.strip().upper() != "DESPOSTE"
                and not _is_externos_area(current_area)
            ):
                obj.area = current_area
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
            if Model == BaseDotaciones and not _is_externos_area(current_area):
                au_ns = (getattr(obj, "area_uso", None) or "").strip()
                if _area_uso_solo_en_sesion_externas(au_ns):
                    flash(
                        f"Este «área de uso» solo puede editarse en «{_LABEL_AREA_EXTERNAS_OTRAS}» (p. ej. PIELES o SUBPRODUCTOS).",
                        "error",
                    )
                    session["modulo_edit_form"] = {modulo_id: dict(request.form)}
                    return redirect(url_for("main.modulo", modulo_id=modulo_id, edit_id=edit_id, page=next_page))
            if Model == HistorialRetiros and hasattr(obj, "observaciones"):
                _obs = ((getattr(obj, "observaciones", None) or "").strip())
                # No alterar marcas de sync [GH:id] (evita romper idempotencia)
                if _obs.upper().startswith("[GH:"):
                    obj.observaciones = _obs
                else:
                    obj.observaciones = _obs.upper()
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
            if Model == RegistroAsignaciones and not _is_externos_area(current_area):
                ara_u = (getattr(obj, "area", None) or "").strip().upper()
                if ara_u in _OTRAS_ETIQUETAS_SOLO_SESION_EXTERNOS:
                    flash(
                        f"El área «{getattr(obj, 'area')}» solo se gestiona con «{_LABEL_AREA_EXTERNAS_OTRAS}».",
                        "error",
                    )
                    session["modulo_edit_form"] = {modulo_id: dict(request.form)}
                    return redirect(url_for("main.modulo", modulo_id=modulo_id, edit_id=edit_id, page=next_page))
            if Model in (BaseLockers, LockerDisponibles) and _is_externos_area(current_area):
                la = (getattr(obj, "area", None) or "").strip()
                if not la:
                    flash("Indique el área del locker (operación externa).", "error")
                    session["modulo_edit_form"] = {modulo_id: dict(request.form)}
                    return redirect(url_for("main.modulo", modulo_id=modulo_id, edit_id=edit_id, page=next_page))
                if la.upper() in _INTERNAS_PLANTA_UPPER:
                    flash(
                        f"No puede usar un código de área interna de planta en «{_LABEL_AREA_EXTERNAS_OTRAS}».",
                        "error",
                    )
                    session["modulo_edit_form"] = {modulo_id: dict(request.form)}
                    return redirect(url_for("main.modulo", modulo_id=modulo_id, edit_id=edit_id, page=next_page))
            if Model == BaseDotaciones and _is_externos_area(current_area):
                au = (getattr(obj, "area_uso", None) or "").strip()
                if not au:
                    flash("Indique el área de uso de la dotación.", "error")
                    session["modulo_edit_form"] = {modulo_id: dict(request.form)}
                    return redirect(url_for("main.modulo", modulo_id=modulo_id, edit_id=edit_id, page=next_page))
                if au.upper() in _DOTACION_AREA_USO_RESTO_INTERNA:
                    flash(
                        f"Esa área de uso corresponde a planta interna y no está permitida en «{_LABEL_AREA_EXTERNAS_OTRAS}».",
                        "error",
                    )
                    session["modulo_edit_form"] = {modulo_id: dict(request.form)}
                    return redirect(url_for("main.modulo", modulo_id=modulo_id, edit_id=edit_id, page=next_page))
            # Validar Cod. Dotación y Cod. Lockers contra Dotaciones/Lockers Disponibles (Registro Asignaciones / Personal)
            if Model == RegistroAsignaciones:
                if (
                    modulo_id == "registro-personal"
                    and _is_externos_area(current_area)
                ):
                    ra = (getattr(obj, "area", None) or "").strip()
                    if not ra:
                        flash("Indique el área del personal (operación externa).", "error")
                        session["modulo_edit_form"] = {modulo_id: dict(request.form)}
                        return redirect(url_for("main.modulo", modulo_id=modulo_id, edit_id=edit_id, page=next_page))
                    if ra.upper() in _INTERNAS_PLANTA_UPPER:
                        flash("Esa área corresponde a planta interna; use una etiqueta externa.", "error")
                        session["modulo_edit_form"] = {modulo_id: dict(request.form)}
                        return redirect(url_for("main.modulo", modulo_id=modulo_id, edit_id=edit_id, page=next_page))
                if not (getattr(obj, "identificacion", None) or "").strip():
                    flash("La identificación del operario es obligatoria.", "error")
                    session["modulo_edit_form"] = {modulo_id: dict(request.form)}
                    return redirect(url_for("main.modulo", modulo_id=modulo_id, edit_id=edit_id, page=next_page))
                cod_dot = (getattr(obj, "codigo_dotacion", None) or "").strip()
                cod_lock = (getattr(obj, "codigo_lockets", None) or "").strip()
                # Edición en Registro de asignaciones: no vaciar códigos por accidente
                # (si el select no envía el valor actual, el registro no debe pasar a pendiente).
                if modulo_id == "registro-asignaciones":
                    if not cod_dot and old_cod_dot:
                        obj.codigo_dotacion = old_cod_dot
                        cod_dot = old_cod_dot
                    if not cod_lock and old_cod_lock:
                        obj.codigo_lockets = old_cod_lock
                        cod_lock = old_cod_lock
                reg_area = (getattr(obj, "area", None) or "").strip() or current_area
                if cod_dot and not _codigo_dotacion_disponible(cod_dot, area=reg_area, permitir_codigo=old_cod_dot):
                    flash("El Código de dotación no está disponible (ya asignado o no existe en Dotaciones Disponibles). Por favor asigne otro.", "error")
                    session["modulo_edit_form"] = {modulo_id: dict(request.form)}
                    return redirect(url_for("main.modulo", modulo_id=modulo_id, edit_id=edit_id, page=next_page))
                if cod_lock and not _codigo_locker_disponible(cod_lock, permitir_codigo=old_cod_lock):
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
            _registrar_cambio(modulo_id, "EDITAR", obj=obj)
            db.session.commit()
            flash("Registro actualizado.", "success")
            return redirect(url_for("main.modulo", modulo_id=modulo_id, page=next_page))

        if config.get("no_crear"):
            return redirect(url_for("main.modulo", modulo_id=modulo_id))

        ne_err = _digits_only_field_error(form_fields, request.form)
        if ne_err:
            flash(ne_err, "error")
            session["modulo_crear_form"] = {modulo_id: dict(request.form)}
            return redirect(url_for("main.modulo", modulo_id=modulo_id, crear=1))

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
        # Personal Pendiente: área fija (toma área actual; no editable) — excluye DESPOSTE y EXTERNOS
        if (
            modulo_id == "registro-personal"
            and Model == RegistroAsignaciones
            and current_area
            and current_area.strip().upper() != "DESPOSTE"
            and not _is_externos_area(current_area)
        ):
            obj.area = current_area
        # Asignar área actual en módulos con area_key (Desposte: subáreas LYD/CAL/… → area=DESPOSTE + subarea)
        if area_key and current_area and hasattr(obj, area_key):
            if _is_externos_area(current_area) and Model in (BaseLockers, LockerDisponibles, BaseDotaciones):
                pass
            elif Model in (BaseLockers, LockerDisponibles):
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
        if Model == BaseDotaciones and not _is_externos_area(current_area):
            au_ns = (getattr(obj, "area_uso", None) or "").strip()
            if _area_uso_solo_en_sesion_externas(au_ns):
                flash(
                    f"Este «área de uso» solo puede darse de alta en «{_LABEL_AREA_EXTERNAS_OTRAS}» (p. ej. PIELES o SUBPRODUCTOS).",
                    "error",
                )
                session["modulo_crear_form"] = {modulo_id: dict(request.form)}
                return redirect(url_for("main.modulo", modulo_id=modulo_id, crear=1))
        if Model == HistorialRetiros and hasattr(obj, "observaciones"):
            _obs = ((getattr(obj, "observaciones", None) or "").strip())
            if _obs.upper().startswith("[GH:"):
                obj.observaciones = _obs
            else:
                obj.observaciones = _obs.upper()
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
        if Model == RegistroAsignaciones and not _is_externos_area(current_area):
            ara_u = (getattr(obj, "area", None) or "").strip().upper()
            if ara_u in _OTRAS_ETIQUETAS_SOLO_SESION_EXTERNOS:
                flash(
                    f"El área «{getattr(obj, 'area')}» solo se gestiona con «{_LABEL_AREA_EXTERNAS_OTRAS}».",
                    "error",
                )
                session["modulo_crear_form"] = {modulo_id: dict(request.form)}
                return redirect(url_for("main.modulo", modulo_id=modulo_id, crear=1))
        if Model in (BaseLockers, LockerDisponibles) and _is_externos_area(current_area):
            la = (getattr(obj, "area", None) or "").strip()
            if not la:
                flash("Indique el área del locker (operación externa).", "error")
                session["modulo_crear_form"] = {modulo_id: dict(request.form)}
                return redirect(url_for("main.modulo", modulo_id=modulo_id, crear=1))
            if la.upper() in _INTERNAS_PLANTA_UPPER:
                flash(
                    f"No puede usar un código de área interna de planta en «{_LABEL_AREA_EXTERNAS_OTRAS}».",
                    "error",
                )
                session["modulo_crear_form"] = {modulo_id: dict(request.form)}
                return redirect(url_for("main.modulo", modulo_id=modulo_id, crear=1))
        if Model == BaseDotaciones and _is_externos_area(current_area):
            au = (getattr(obj, "area_uso", None) or "").strip()
            if not au:
                flash("Indique el área de uso de la dotación.", "error")
                session["modulo_crear_form"] = {modulo_id: dict(request.form)}
                return redirect(url_for("main.modulo", modulo_id=modulo_id, crear=1))
            if au.upper() in _DOTACION_AREA_USO_RESTO_INTERNA:
                flash(
                    f"Esa área de uso corresponde a planta interna y no está permitida en «{_LABEL_AREA_EXTERNAS_OTRAS}».",
                    "error",
                )
                session["modulo_crear_form"] = {modulo_id: dict(request.form)}
                return redirect(url_for("main.modulo", modulo_id=modulo_id, crear=1))
        if (
            Model == RegistroAsignaciones
            and modulo_id == "registro-personal"
            and _is_externos_area(current_area)
        ):
            ra = (getattr(obj, "area", None) or "").strip()
            if not ra:
                flash("Indique el área del personal (operación externa).", "error")
                session["modulo_crear_form"] = {modulo_id: dict(request.form)}
                return redirect(url_for("main.modulo", modulo_id=modulo_id, crear=1))
            if ra.upper() in _INTERNAS_PLANTA_UPPER:
                flash("Esa área corresponde a planta interna; use una etiqueta externa.", "error")
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
        _registrar_cambio(modulo_id, "CREAR", obj=obj)
        db.session.commit()
        flash("Registro creado.", "success")
        return redirect(url_for("main.modulo", modulo_id=modulo_id))

    # GET: listar con paginación filtrada por área actual y búsqueda
    from sqlalchemy import or_, and_, false

    # Sync GH → historial + sacar INACTIVOS de asignaciones (también al abrir
    # asignaciones / registro personal, no solo historial de retiros).
    if (
        modulo_id in ("historial-retiros", "registro-asignaciones", "registro-personal")
        and request.method == "GET"
        and can_edit
    ):
        from app.utils.gestion_humana import (
            area_gh_para_lockers,
            limpiar_historial_retiros_gh,
            sincronizar_retirados_area,
            deduplicar_historial_retiros,
        )

        try:
            limpiar_historial_retiros_gh()
        except Exception:
            pass

        # DESPOSTE queda fuera del sync GH mientras esté en mantenimiento.
        if (
            (current_area or "").strip().upper() != "DESPOSTE"
            and area_gh_para_lockers(current_area)
        ):
            try:
                sync = sincronizar_retirados_area(current_area)
                deduplicar_historial_retiros(None)
                if sync.get("ok") and (
                    sync.get("inserted", 0) > 0
                    or sync.get("updated", 0) > 0
                    or sync.get("deleted_duplicates", 0) > 0
                    or sync.get("asignaciones_cerradas", 0) > 0
                ):
                    flash(
                        f"Gestión Humana: nuevos {sync.get('inserted', 0)}, "
                        f"actualizados {sync.get('updated', 0)}, "
                        f"asignaciones cerradas {sync.get('asignaciones_cerradas', 0)}, "
                        f"códigos liberados {sync.get('codigos_liberados', 0)} "
                        f"(INACTIVOS → historial; ACTIVO/recontratados se conservan).",
                        "success",
                    )
                elif sync.get("ok") is False and sync.get("error"):
                    flash(f"No se pudo sincronizar retiros de Gestión Humana: {sync['error']}", "error")
            except Exception as exc:  # noqa: BLE001
                flash(f"Error al sincronizar retiros: {exc}", "error")

    query = Model.query
    if area_key and current_area and hasattr(Model, area_key):
        if Model == BaseDotaciones and area_key == "area_uso":
            query = query.filter(_base_dotaciones_scope_filter(current_area))
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
        elif Model == SecaBotasDisponibles:
            ca_u = (current_area or "").strip().upper()
            if ca_u == "DESPOSTE":
                query = query.filter(false())
            elif ca_u == "CALIDAD":
                # Calidad: se filtra por ubicación (MUJ/ADM) en vez de área directa.
                from sqlalchemy import or_
                query = query.filter(
                    or_(
                        db.func.upper(db.func.trim(SecaBotasDisponibles.area_locker)).like("%MUJ%"),
                        db.func.upper(db.func.trim(SecaBotasDisponibles.area_locker)).like("%ADM%"),
                    )
                )
            elif _is_externos_area(current_area):
                sa = db.func.upper(db.func.trim(db.func.coalesce(SecaBotasDisponibles.area, "")))
                query = query.filter(and_(sa != "", ~sa.in_(_INTERNAS_PLANTA_UPPER)))
            else:
                query = query.filter(db.func.upper(db.func.trim(SecaBotasDisponibles.area)) == ca_u)
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
            query = query.filter(_base_dotaciones_scope_filter(current_area))
            if not _is_desposte_context(current_area):
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
    elif Model == HistorialCambios:
        order_asignaciones_reciente = (HistorialCambios.creado_en.desc(), HistorialCambios.id.desc())

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
    edit_preview = None
    edit_id = request.args.get("edit_id", type=int)
    if edit_id:
        item_edit = Model.query.get(edit_id)
        if item_edit:
            if user_rol == "coordinador" and area_key and user_area and not _is_externos_area(current_area):
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
                # Personal Pendiente: fechas autollenadas con el día actual si vienen vacías (editable)
                if modulo_id == "registro-personal":
                    today = datetime.utcnow().date().isoformat()
                    if not (edit_data.get("fecha_asignacion") or "").strip():
                        edit_data["fecha_asignacion"] = today
                    if not (edit_data.get("fecha_entrega") or "").strip():
                        edit_data["fecha_entrega"] = today
                if modulo_id == "registro-asignaciones":
                    edit_preview = {
                        "Identificación": edit_data.get("identificacion", ""),
                        "Operario": edit_data.get("operario", ""),
                        "Área": edit_data.get("area", ""),
                        "Área lockers": edit_data.get("area_lockers", ""),
                        "Cód. Dotación": edit_data.get("codigo_dotacion", ""),
                        "Cód. Lockers": edit_data.get("codigo_lockets", ""),
                        "Cód. Seca Botas": edit_data.get("codigo_seca_botas", ""),
                        "Fecha asignación": edit_data.get("fecha_asignacion", ""),
                        "Fecha entrega": edit_data.get("fecha_entrega", ""),
                        "Estado": edit_data.get("estado", ""),
                    }
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
        if current_area:
            q_dot = q_dot.filter(_base_dotaciones_scope_filter(current_area))
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
        q_sb = SecaBotasDisponibles.query.filter(db.func.lower(SecaBotasDisponibles.estado) == "disponible")
        # Regla solicitada: para áreas distintas de DESPOSTE, aplicar el filtro por área del código (no por Desposte)
        if current_area and current_area.strip().upper() != "DESPOSTE":
            ca_u = current_area.strip().upper()
            if ca_u == "CALIDAD":
                # Calidad: el stock viene marcado en "Área locker" (p.ej. MUJ/ADM), no necesariamente como CAL en area.
                from sqlalchemy import or_
                q_sb = q_sb.filter(
                    or_(
                        db.func.upper(db.func.trim(SecaBotasDisponibles.area_locker)).like("%MUJ%"),
                        db.func.upper(db.func.trim(SecaBotasDisponibles.area_locker)).like("%ADM%"),
                    )
                )
            elif _is_externos_area(current_area):
                sa = db.func.upper(db.func.trim(db.func.coalesce(SecaBotasDisponibles.area, "")))
                q_sb = q_sb.filter(and_(sa != "", ~sa.in_(_INTERNAS_PLANTA_UPPER)))
            else:
                q_sb = q_sb.filter(db.func.upper(db.func.trim(SecaBotasDisponibles.area)) == ca_u)
        opciones_seca_botas = [
            r[0]
            for r in q_sb.with_entities(SecaBotasDisponibles.codigo)
            .distinct()
            .order_by(SecaBotasDisponibles.codigo)
            .all()
            if r[0]
        ]
    # Al editar: incluir códigos actuales aunque ya no estén "disponibles",
    # para no vaciar el select y mandar el registro a Personal pendiente.
    if edit_data and modulo_id in ("registro-asignaciones", "registro-personal"):
        cur_dot = (edit_data.get("codigo_dotacion") or "").strip()
        if cur_dot and cur_dot not in opciones_dotacion:
            opciones_dotacion = [cur_dot] + list(opciones_dotacion)
        cur_lock = (edit_data.get("codigo_lockets") or "").strip()
        if cur_lock and cur_lock not in opciones_locker:
            opciones_locker = [cur_lock] + list(opciones_locker)
        cur_sb = (edit_data.get("codigo_seca_botas") or "").strip()
        if cur_sb and cur_sb not in opciones_seca_botas:
            opciones_seca_botas = [cur_sb] + list(opciones_seca_botas)
    _mod_nav = dict(MODULOS_CONFIG)
    if _is_externos_area(current_area):
        _mod_nav.pop("personal-presupuestado", None)
    if (current_area or "").strip().upper() == _ADMINISTRATIVA_UPPER:
        for mid in _MODULOS_OCULTOS_ADMINISTRATIVA:
            _mod_nav.pop(mid, None)
    return render_template(
        "modulo.html",
        modulo_id=modulo_id,
        titulo=titulo,
        columnas=columnas,
        form_fields=form_fields,
        items=items,
        item_edit=item_edit,
        edit_data=edit_data,
        edit_preview=edit_preview,
        opciones_dotacion=opciones_dotacion,
        opciones_locker=opciones_locker,
        opciones_seca_botas=opciones_seca_botas,
        modulos_config=_mod_nav,
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
