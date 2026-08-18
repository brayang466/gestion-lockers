"""
Lectura de empleados/retirados desde gestio_humana (autollenado y sync).
"""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime
from typing import Any

import pymysql
from flask import current_app

# Área en LockerBeef (session current_area) → valor en gestio_humana.*.area
AREA_LOCKERBEEF_A_GH: dict[str, str] = {
    "BENEFICIO": "LINEA DE SACRIFICIO",
    "LOGISTICA": "LOGISTICA",
    "PCC": "SUBPRODUCTOS COMESTIBLES",
    "CALIDAD": "DIRECCION DPTO CALIDAD",
    "LYD": "LIMPIEZA Y DESINFECCION",
}

GH_ID_RE = re.compile(r"^\[GH:([^\]]+)\]")


def area_gh_para_lockers(current_area: str | None) -> str | None:
    """Devuelve el nombre de área en Gestión Humana o None si no hay mapeo."""
    key = (current_area or "").strip().upper()
    if not key:
        return None
    return AREA_LOCKERBEEF_A_GH.get(key)


def _gh_enabled() -> bool:
    return bool(current_app.config.get("GH_ENABLED", True))


def _connect():
    return pymysql.connect(
        host=current_app.config["GH_MYSQL_HOST"],
        port=int(current_app.config.get("GH_MYSQL_PORT") or 3306),
        user=current_app.config["GH_MYSQL_USER"],
        password=current_app.config.get("GH_MYSQL_PASSWORD") or "",
        database=current_app.config["GH_MYSQL_DATABASE"],
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=8,
        read_timeout=30,
    )


def _norm_celular(val: Any) -> str:
    if val is None:
        return ""
    s = str(val).strip()
    if s.endswith(".0") and s.replace(".", "", 1).isdigit():
        s = s[:-2]
    return s


def _norm_doc(val: Any) -> str:
    return re.sub(r"\D+", "", str(val or "").strip())


def _parse_fecha_gh(val: Any) -> datetime | None:
    s = str(val or "").strip()
    if not s:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _row_to_empleado(row: dict) -> dict:
    return {
        "documento": str(row.get("id_cedula") or "").strip(),
        "nombre": str(row.get("apellidos_nombre") or "").strip(),
        "email": str(row.get("direccion_email") or "").strip(),
        "telefono": _norm_celular(row.get("celular") or row.get("telefono")),
        "cargo": str(row.get("id_perfil_ocupacional") or "").strip(),
        "area_gh": str(row.get("area") or "").strip(),
        "fecha_ingreso": str(row.get("fecha_ingreso") or "").strip(),
        "estado": str(row.get("estado") or "").strip(),
    }


def _row_to_retirado(row: dict) -> dict:
    return {
        "id_retiro": str(row.get("id_retiro") or "").strip(),
        "documento": str(row.get("id_cedula") or "").strip(),
        "nombre": str(row.get("apellidos_nombre") or "").strip(),
        "area_gh": str(row.get("area") or "").strip(),
        "fecha_ingreso": str(row.get("fecha_ingreso") or "").strip(),
        "fecha_retiro": str(row.get("fecha_retiro") or "").strip(),
        "tipo_retiro": str(row.get("tipo_retiro") or "").strip(),
        "motivo": str(row.get("motivo") or "").strip(),
        "dias_laborados": row.get("dias_laborados"),
    }


def _observaciones_desde_gh(tipo: str, motivo: str) -> str:
    """Observaciones desde GH: prioriza motivo; si hay ambos, tipo | motivo."""
    motivo = (motivo or "").strip()
    tipo = (tipo or "").strip()
    if motivo and tipo and tipo.upper() != motivo.upper():
        return f"{tipo} | {motivo}"[:500]
    if motivo:
        return motivo[:500]
    return tipo[:500]


def _score_historial(r) -> tuple:
    lock = 1 if (getattr(r, "codigo_lockets", None) or "").strip() else 0
    dot = 1 if (getattr(r, "codigo_dotacion", None) or "").strip() else 0
    al = 1 if (getattr(r, "area_lockers", None) or "").strip() else 0
    tallas = 1 if (
        (getattr(r, "talla_operarios", None) or "").strip()
        or (getattr(r, "talla_dotacion", None) or "").strip()
    ) else 0
    obs = 1 if (getattr(r, "observaciones", None) or "").strip() else 0
    fr = 1 if getattr(r, "fecha_retiro", None) else 0
    return (lock + dot, lock, dot, al, tallas, obs, fr, getattr(r, "id", 0) or 0)


def buscar_empleados(
    current_area: str,
    q: str = "",
    limit: int = 25,
    solo_activos: bool = True,
) -> tuple[list[dict], str | None]:
    if not _gh_enabled():
        return [], "Integración con Gestión Humana deshabilitada."

    area_gh = area_gh_para_lockers(current_area)
    if not area_gh:
        return [], (
            f"El área «{(current_area or '').strip() or '?'}» no tiene mapeo "
            "a Gestión Humana (aún)."
        )

    limit = max(1, min(int(limit or 25), 50))
    q = (q or "").strip()
    q_digits = re.sub(r"\D+", "", q)

    sql = """
        SELECT id_cedula, apellidos_nombre, area, fecha_ingreso, estado,
               direccion_email, celular, telefono, id_perfil_ocupacional
        FROM empleado
        WHERE area = %s
    """
    params: list[Any] = [area_gh]
    if solo_activos:
        sql += " AND UPPER(TRIM(COALESCE(estado, ''))) = 'ACTIVO'"
    if q_digits and q_digits == q.replace(" ", ""):
        sql += " AND id_cedula LIKE %s"
        params.append(f"%{q_digits}%")
    elif q:
        sql += " AND (id_cedula LIKE %s OR apellidos_nombre LIKE %s)"
        like = f"%{q}%"
        params.extend([like, like])

    sql += """
        ORDER BY STR_TO_DATE(NULLIF(TRIM(fecha_ingreso), ''), '%%d/%%m/%%Y') DESC,
                 id_cedula DESC
        LIMIT %s
    """
    params.append(limit)

    try:
        conn = _connect()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall() or []
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001
        return [], f"No se pudo consultar Gestión Humana: {exc}"

    return [_row_to_empleado(r) for r in rows], None


def obtener_empleado_por_cedula(documento: str, current_area: str | None = None) -> tuple[dict | None, str | None]:
    if not _gh_enabled():
        return None, "Integración con Gestión Humana deshabilitada."

    documento = _norm_doc(documento)
    if not documento:
        return None, "Documento vacío."

    area_gh = area_gh_para_lockers(current_area) if current_area else None

    sql = """
        SELECT id_cedula, apellidos_nombre, area, fecha_ingreso, estado,
               direccion_email, celular, telefono, id_perfil_ocupacional
        FROM empleado
        WHERE id_cedula = %s
    """
    params: list[Any] = [documento]
    if area_gh:
        sql += " AND area = %s"
        params.append(area_gh)
    sql += " LIMIT 1"

    try:
        conn = _connect()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                row = cur.fetchone()
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001
        return None, f"No se pudo consultar Gestión Humana: {exc}"

    if not row:
        if area_gh:
            return None, "No hay empleado coincidente en esa área de Gestión Humana."
        return None, "Empleado no encontrado en Gestión Humana."
    return _row_to_empleado(row), None


def buscar_retirados(
    current_area: str,
    q: str = "",
    limit: int = 25,
) -> tuple[list[dict], str | None]:
    if not _gh_enabled():
        return [], "Integración con Gestión Humana deshabilitada."

    area_gh = area_gh_para_lockers(current_area)
    if not area_gh:
        return [], (
            f"El área «{(current_area or '').strip() or '?'}» no tiene mapeo "
            "a Gestión Humana (aún)."
        )

    limit = max(1, min(int(limit or 25), 100))
    q = (q or "").strip()
    q_digits = re.sub(r"\D+", "", q)

    sql = """
        SELECT id_retiro, id_cedula, apellidos_nombre, area, fecha_ingreso,
               fecha_retiro, dias_laborados, tipo_retiro, motivo
        FROM retirado
        WHERE area = %s
          AND fecha_retiro IS NOT NULL
          AND TRIM(fecha_retiro) <> ''
    """
    params: list[Any] = [area_gh]
    if q_digits and q_digits == q.replace(" ", ""):
        sql += " AND id_cedula LIKE %s"
        params.append(f"%{q_digits}%")
    elif q:
        sql += " AND (id_cedula LIKE %s OR apellidos_nombre LIKE %s OR id_retiro LIKE %s)"
        like = f"%{q}%"
        params.extend([like, like, like])

    sql += """
        ORDER BY STR_TO_DATE(NULLIF(TRIM(fecha_retiro), ''), '%%d/%%m/%%Y') DESC,
                 id_retiro DESC
        LIMIT %s
    """
    params.append(limit)

    try:
        conn = _connect()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall() or []
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001
        return [], f"No se pudo consultar retirados en Gestión Humana: {exc}"

    items = []
    for r in rows:
        item = _row_to_retirado(r)
        if _parse_fecha_gh(item.get("fecha_retiro")):
            items.append(item)
    return items, None


def _existing_historial_docs(area_lockers: str) -> dict[str, Any]:
    """documento_norm -> mejor fila del área (prioriza lockers/dotación)."""
    from app.models import HistorialRetiros

    best: dict[str, Any] = {}
    q = HistorialRetiros.query
    if area_lockers:
        q = q.filter(HistorialRetiros.area == area_lockers)
    for r in q.order_by(HistorialRetiros.id.asc()).all():
        doc = _norm_doc(r.identificacion)
        if not doc:
            continue
        prev = best.get(doc)
        if prev is None or _score_historial(r) > _score_historial(prev):
            best[doc] = r
    return best


def deduplicar_historial_retiros(area_lockers: str | None = None) -> dict[str, Any]:
    """
    Elimina duplicados por documento. Conserva el que tenga más info de lockers/dotación.
    Hereda observaciones/fecha/operario del resto si al ganador le faltan.
    """
    from app import db
    from app.models import HistorialRetiros

    q = HistorialRetiros.query
    if area_lockers:
        q = q.filter(HistorialRetiros.area == area_lockers)

    groups: dict[str, list] = defaultdict(list)
    for r in q.order_by(HistorialRetiros.id.asc()).all():
        doc = _norm_doc(r.identificacion)
        if doc:
            groups[doc].append(r)

    deleted = 0
    kept = 0
    merged_obs = 0

    for _doc, rows in groups.items():
        if len(rows) < 2:
            continue
        rows_sorted = sorted(rows, key=_score_historial, reverse=True)
        winner = rows_sorted[0]
        kept += 1

        if not (winner.observaciones or "").strip():
            for other in rows_sorted[1:]:
                if (other.observaciones or "").strip():
                    winner.observaciones = (other.observaciones or "").strip()[:500]
                    merged_obs += 1
                    break
        if winner.fecha_retiro is None:
            for other in rows_sorted[1:]:
                if other.fecha_retiro is not None:
                    winner.fecha_retiro = other.fecha_retiro
                    break
        if not (winner.operario or "").strip():
            for other in rows_sorted[1:]:
                if (other.operario or "").strip():
                    winner.operario = other.operario
                    break
        # Completar códigos si el ganador no los tiene pero otro sí (poco probable por score)
        if not (winner.codigo_lockets or "").strip():
            for other in rows_sorted[1:]:
                if (other.codigo_lockets or "").strip():
                    winner.codigo_lockets = other.codigo_lockets
                    break
        if not (winner.codigo_dotacion or "").strip():
            for other in rows_sorted[1:]:
                if (other.codigo_dotacion or "").strip():
                    winner.codigo_dotacion = other.codigo_dotacion
                    break
        if not (winner.area_lockers or "").strip():
            for other in rows_sorted[1:]:
                if (other.area_lockers or "").strip():
                    winner.area_lockers = other.area_lockers
                    break

        for other in rows_sorted[1:]:
            db.session.delete(other)
            deleted += 1

    if deleted or merged_obs:
        db.session.commit()

    return {"deleted_duplicates": deleted, "groups_resolved": kept, "merged_obs": merged_obs}


def enriquecer_observaciones_desde_gh(area_lockers: str) -> dict[str, Any]:
    """Completa observaciones vacías con motivo/tipo de retirado (GH)."""
    from app import db
    from app.models import HistorialRetiros

    area_gh = area_gh_para_lockers(area_lockers)
    if not area_gh or not _gh_enabled():
        return {"updated": 0}

    rows = (
        HistorialRetiros.query.filter(HistorialRetiros.area == area_lockers)
        .filter(
            (HistorialRetiros.observaciones.is_(None))
            | (HistorialRetiros.observaciones == "")
        )
        .all()
    )
    if not rows:
        return {"updated": 0}

    docs = {_norm_doc(r.identificacion) for r in rows if _norm_doc(r.identificacion)}
    if not docs:
        return {"updated": 0}

    sql = """
        SELECT id_cedula, fecha_retiro, tipo_retiro, motivo
        FROM retirado
        WHERE area = %s
          AND fecha_retiro IS NOT NULL AND TRIM(fecha_retiro) <> ''
        ORDER BY STR_TO_DATE(NULLIF(TRIM(fecha_retiro), ''), '%%d/%%m/%%Y') DESC
    """
    by_doc: dict[str, dict] = {}
    try:
        conn = _connect()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, (area_gh,))
                for r in cur.fetchall() or []:
                    d = _norm_doc(r.get("id_cedula"))
                    if not d or d in by_doc or d not in docs:
                        continue
                    obs = _observaciones_desde_gh(r.get("tipo_retiro") or "", r.get("motivo") or "")
                    if obs:
                        by_doc[d] = {"obs": obs, "fecha": _parse_fecha_gh(r.get("fecha_retiro"))}
        finally:
            conn.close()
    except Exception:
        return {"updated": 0, "error": "gh_query_failed"}

    updated = 0
    for r in rows:
        d = _norm_doc(r.identificacion)
        info = by_doc.get(d)
        if not info:
            continue
        r.observaciones = info["obs"][:500]
        if r.fecha_retiro is None and info.get("fecha"):
            r.fecha_retiro = info["fecha"]
        updated += 1
    if updated:
        db.session.commit()
    return {"updated": updated}


def limpiar_historial_retiros_gh() -> dict[str, Any]:
    """Limpia tags [GH:], sin fecha, y deduplica."""
    from app import db
    from app.models import HistorialRetiros

    deleted_sin_fecha = (
        HistorialRetiros.query.filter(HistorialRetiros.fecha_retiro.is_(None)).delete(
            synchronize_session=False
        )
    )

    cleaned = 0
    deleted_sin_fecha_gh = 0
    sin_fecha_ids: set[str] = set()
    tagged = HistorialRetiros.query.filter(HistorialRetiros.observaciones.like("[GH:%")).all()

    if tagged:
        try:
            conn = _connect()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT id_retiro FROM retirado
                        WHERE fecha_retiro IS NULL OR TRIM(COALESCE(fecha_retiro, '')) = ''
                        """
                    )
                    sin_fecha_ids = {
                        str(r["id_retiro"]).strip()
                        for r in (cur.fetchall() or [])
                        if r.get("id_retiro")
                    }
            finally:
                conn.close()
        except Exception:
            sin_fecha_ids = set()

        for row in tagged:
            obs = (row.observaciones or "").strip()
            m = GH_ID_RE.match(obs)
            gid = m.group(1).strip() if m else ""
            if gid and gid in sin_fecha_ids:
                db.session.delete(row)
                deleted_sin_fecha_gh += 1
                continue
            new_obs = GH_ID_RE.sub("", obs)
            new_obs = re.sub(r"^\s*\|\s*", "", new_obs).strip()
            if new_obs != obs:
                row.observaciones = new_obs[:500]
                cleaned += 1

    db.session.commit()
    dedup = deduplicar_historial_retiros(None)
    return {
        "deleted_sin_fecha": int(deleted_sin_fecha or 0),
        "deleted_sin_fecha_gh": deleted_sin_fecha_gh,
        "cleaned_obs": cleaned,
        **dedup,
    }


def sincronizar_retirados_area(current_area: str) -> dict[str, Any]:
    """
    Sync retirados GH → historial_retiros.
    Solo con fecha. Sin duplicados por documento: conserva el de lockers
    y completa observaciones (motivo GH) si faltan.
    """
    from app import db
    from app.models import HistorialRetiros

    area_lb = (current_area or "").strip()
    area_gh = area_gh_para_lockers(area_lb)
    if not _gh_enabled():
        return {"ok": False, "error": "Integración deshabilitada.", "inserted": 0, "skipped": 0}
    if not area_gh:
        return {
            "ok": False,
            "error": f"El área «{area_lb or '?'}» no tiene mapeo a Gestión Humana.",
            "inserted": 0,
            "skipped": 0,
            "area_gh": None,
        }

    deduplicar_historial_retiros(area_lb)
    enriquecer_observaciones_desde_gh(area_lb)

    sql = """
        SELECT id_retiro, id_cedula, apellidos_nombre, area, fecha_ingreso,
               fecha_retiro, dias_laborados, tipo_retiro, motivo
        FROM retirado
        WHERE area = %s
          AND fecha_retiro IS NOT NULL
          AND TRIM(fecha_retiro) <> ''
        ORDER BY STR_TO_DATE(NULLIF(TRIM(fecha_retiro), ''), '%%d/%%m/%%Y') DESC,
                 id_retiro DESC
    """
    try:
        conn = _connect()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, (area_gh,))
                rows = cur.fetchall() or []
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc), "inserted": 0, "skipped": 0, "area_gh": area_gh}

    existing = _existing_historial_docs(area_lb)
    inserted = 0
    skipped = 0
    updated = 0
    skipped_sin_fecha = 0

    for row in rows:
        item = _row_to_retirado(row)
        doc = _norm_doc(item["documento"])
        fecha = _parse_fecha_gh(item["fecha_retiro"])
        if not fecha:
            skipped_sin_fecha += 1
            continue
        if not doc:
            skipped += 1
            continue

        observaciones = _observaciones_desde_gh(item["tipo_retiro"], item["motivo"])
        prev = existing.get(doc)

        if prev is not None:
            changed = False
            prev_obs = (prev.observaciones or "").strip()
            if not prev_obs and observaciones:
                prev.observaciones = observaciones
                changed = True
            elif observaciones and item.get("motivo"):
                # Si el guardado no trae el motivo de GH, enriquecer
                if item["motivo"].upper() not in prev_obs.upper():
                    if not prev_obs or prev_obs.upper() in (
                        "PENDIENTE POR ASIGNAR",
                        (item.get("tipo_retiro") or "").upper(),
                    ):
                        prev.observaciones = observaciones
                        changed = True
                    elif item["motivo"].strip() and "|" not in prev_obs:
                        # Añadir motivo sin borrar lo existente de lockers/historial
                        prev.observaciones = f"{prev_obs} | {item['motivo']}".strip(" |")[:500]
                        changed = True
            if prev.fecha_retiro is None:
                prev.fecha_retiro = fecha
                changed = True
            if not (prev.operario or "").strip() and item.get("nombre"):
                prev.operario = (item["nombre"] or "")[:120]
                changed = True
            if changed:
                updated += 1
            skipped += 1
            continue

        hist = HistorialRetiros(
            identificacion=(item["documento"] or "")[:40],
            operario=(item["nombre"] or "")[:120],
            codigo_dotacion="",
            codigo_lockets="",
            area=area_lb,
            talla_operarios="",
            talla_dotacion="",
            area_lockers="",
            fecha_retiro=fecha,
            observaciones=observaciones,
            es_planta_desposte=False,
        )
        db.session.add(hist)
        existing[doc] = hist
        inserted += 1

    if inserted or updated:
        db.session.commit()

    dedup = deduplicar_historial_retiros(area_lb)

    return {
        "ok": True,
        "error": None,
        "inserted": inserted,
        "updated": updated,
        "skipped": skipped,
        "skipped_sin_fecha": skipped_sin_fecha,
        "total_gh": len(rows),
        "area_gh": area_gh,
        "area_lockers": area_lb,
        "deleted_duplicates": dedup.get("deleted_duplicates", 0),
    }
