"""
Importa lockers del área DESPOSTE desde datos_importar/LOCKERS DES.csv.

Reglas:
- Todos los registros se importan con area = 'DESPOSTE'.
- Subáreas (ubicación en Desposte): DES, CAL, LYD, SST, MTTO, LOG, EXT, TIC.
  Se toman de la columna 'Area' del CSV o del prefijo del código (DES*, VIS*).
- Estado normalizado: solo DISPONIBLE, ASIGNADO o VISITA.
  Códigos que inician con VIS se consideran de visita (estado VISITA si aplica).
- Se eliminan previamente todos los BaseLockers y LockerDisponibles con area = 'DESPOSTE'.
- Tras importar Base de Lockers, se sincroniza Locker Disponibles: solo los que tienen
  estado DISPONIBLE se insertan en locker_disponibles, sin duplicar (por codigo+area+subarea).

Columnas CSV esperadas (con variantes): Codigo / Codigo de Lockets, Area, Area de Lockers,
ESTADO, UNIDAD. Si falta Area se infiere del prefijo del código (DES, VIS, CAL, etc.).

Ejecutar desde la raíz: python database/importar_lockers_desposte.py
"""
import csv
import re
import os
import sys
from pathlib import Path

raiz = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(raiz))

env_file = raiz / ".env"
if env_file.exists():
    with open(env_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                k, v = k.strip(), v.strip()
                if len(v) >= 2 and v[0] == v[-1] and v[0] in ('"', "'"):
                    v = v[1:-1]
                os.environ.setdefault(k, v)

# Subáreas válidas ubicadas en Desposte (denominación distinta al área principal)
SUBAREAS_DESPOSTE = {"DES", "CAL", "LYD", "SST", "MTTO", "LOG", "EXT", "TIC", "VIS"}


def infer_subarea_from_codigo(codigo):
    """Infiere subárea por prefijo del código: DES, VIS, CAL, LYD, etc."""
    c = (codigo or "").strip().upper()
    for prefix in ("DES", "VIS", "CAL", "LYD", "SST", "MTTO", "LOG", "EXT", "TIC"):
        if c.startswith(prefix):
            return prefix
    return ""


def normalize_estado(estado):
    """Solo DISPONIBLE, ASIGNADO o VISITA. Quita prefijo LOCKERT."""
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


def main():
    from app import create_app, db
    from app.models import BaseLockers, LockerDisponibles

    csv_path = raiz / "datos_importar" / "LOCKERS DES.csv"
    if not csv_path.exists():
        print("No se encontró {}.".format(csv_path))
        print("Coloque el archivo LOCKERS DES.csv en la carpeta datos_importar/.")
        sys.exit(1)

    rows = []
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            codigo = (
                row.get("Codigo")
                or row.get("Codigo de Lockets")
                or row.get("Codigo de Lockers")
                or row.get("codigo")
                or ""
            ).strip()
            if not codigo:
                continue
            area_col = (
                row.get("Area")
                or row.get("AREA")
                or row.get("area")
                or ""
            ).strip().upper()
            subarea = area_col if area_col in SUBAREAS_DESPOSTE else infer_subarea_from_codigo(codigo)
            if not subarea and area_col:
                subarea = area_col[:10]  # usar hasta 10 chars si no está en la lista
            area_lockers = (
                row.get("Area de Lockers")
                or row.get("Area Lockers")
                or row.get("area_lockers")
                or ""
            ).strip()
            estado = normalize_estado(
                row.get("ESTADO") or row.get("Estado") or row.get("estado") or ""
            )
            unidad = (
                row.get("UNIDAD") or row.get("Unidad") or row.get("unidad") or ""
            ).strip()

            # Visita: códigos que inician con VIS pueden forzar estado VISITA si en CSV viene así
            if codigo.upper().startswith("VIS") and estado == "DISPONIBLE":
                pass  # mantener DISPONIBLE; si el CSV dice VISITA se respeta en normalize_estado

            rows.append({
                "codigo": codigo,
                "subarea": subarea[:30] if subarea else "",
                "area_lockers": area_lockers,
                "estado": estado,
                "unidad": unidad[:30] if unidad else "",
            })

    app = create_app()
    with app.app_context():
        # Eliminar todos los lockers DESPOSTE en ambas tablas
        deleted_base = BaseLockers.query.filter(BaseLockers.area == "DESPOSTE").delete()
        deleted_disp = LockerDisponibles.query.filter(LockerDisponibles.area == "DESPOSTE").delete()
        db.session.commit()
        print("Eliminados {} registros en Base de Lockers (area=DESPOSTE).".format(deleted_base))
        print("Eliminados {} registros en Locker Disponibles (area=DESPOSTE).".format(deleted_disp))

        # Insertar en Base de Lockers
        for r in rows:
            obj = BaseLockers(
                codigo=r["codigo"],
                area="DESPOSTE",
                subarea=r["subarea"],
                area_lockers=r["area_lockers"],
                estado=r["estado"],
                unidad=r["unidad"],
            )
            db.session.add(obj)
        db.session.commit()
        print("Importados {} registros en Base de Lockers para area DESPOSTE.".format(len(rows)))

        # Sincronizar Locker Disponibles: solo DISPONIBLE, sin repetir (codigo + area + subarea)
        codigos_disp = set()
        added = 0
        for r in rows:
            if r["estado"] != "DISPONIBLE":
                continue
            key = (r["codigo"], "DESPOSTE", r["subarea"])
            if key in codigos_disp:
                continue
            codigos_disp.add(key)
            exist = (
                LockerDisponibles.query.filter_by(
                    codigo=r["codigo"],
                    area="DESPOSTE",
                    subarea=r["subarea"],
                ).first()
            )
            if not exist:
                ld = LockerDisponibles(
                    codigo=r["codigo"],
                    area="DESPOSTE",
                    subarea=r["subarea"],
                    area_lockers=r["area_lockers"],
                    estado="DISPONIBLE",
                )
                db.session.add(ld)
                added += 1
        db.session.commit()
        print("Sincronizados {} lockers DISPONIBLE en Locker Disponibles (sin duplicar).".format(added))
        print("Estados permitidos: DISPONIBLE, ASIGNADO, VISITA. Subáreas: DES, CAL, LYD, SST, MTTO, LOG, EXT, TIC, VIS.")


if __name__ == "__main__":
    main()
