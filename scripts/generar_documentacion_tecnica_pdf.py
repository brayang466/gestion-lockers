# -*- coding: utf-8 -*-
"""Genera docs/DOCUMENTACION_TECNICA_LOCKERBEEF.pdf (estilo institucional Colbeef)."""
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    KeepTogether,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

OUT = Path(__file__).resolve().parent.parent / "docs" / "DOCUMENTACION_TECNICA_LOCKERBEEF.pdf"

GREEN = colors.HexColor("#1a7a3a")
RED = colors.HexColor("#c62828")
DARK = colors.HexColor("#1a1a1a")
MUTED = colors.HexColor("#444444")
HEADER_BG = colors.HexColor("#f3f4f6")
LINE = colors.HexColor("#d1d5db")
ACCENT = colors.HexColor("#0f766e")


def make_styles():
    base = getSampleStyleSheet()
    styles = {
        "cover_kicker": ParagraphStyle(
            "cover_kicker",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=11,
            textColor=GREEN,
            alignment=TA_CENTER,
            spaceAfter=6,
        ),
        "cover_title": ParagraphStyle(
            "cover_title",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=20,
            textColor=DARK,
            alignment=TA_CENTER,
            spaceAfter=8,
            leading=24,
        ),
        "cover_sub": ParagraphStyle(
            "cover_sub",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=10,
            textColor=MUTED,
            alignment=TA_CENTER,
            leading=14,
            spaceAfter=6,
        ),
        "meta": ParagraphStyle(
            "meta",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            textColor=MUTED,
            alignment=TA_CENTER,
            leading=12,
            spaceAfter=4,
        ),
        "h1": ParagraphStyle(
            "h1",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=13,
            textColor=ACCENT,
            spaceBefore=14,
            spaceAfter=8,
            leading=16,
        ),
        "h2": ParagraphStyle(
            "h2",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=11,
            textColor=DARK,
            spaceBefore=10,
            spaceAfter=6,
            leading=14,
        ),
        "body": ParagraphStyle(
            "body",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9.5,
            textColor=DARK,
            alignment=TA_JUSTIFY,
            leading=13,
            spaceAfter=6,
        ),
        "bullet": ParagraphStyle(
            "bullet",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9.5,
            textColor=DARK,
            leading=12.5,
            leftIndent=4,
        ),
        "code": ParagraphStyle(
            "code",
            parent=base["Code"],
            fontName="Courier",
            fontSize=7.5,
            textColor=DARK,
            leading=10,
            backColor=HEADER_BG,
            leftIndent=4,
            rightIndent=4,
            spaceBefore=4,
            spaceAfter=8,
        ),
        "toc": ParagraphStyle(
            "toc",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=10,
            textColor=DARK,
            leading=15,
            leftIndent=8,
        ),
        "footer": ParagraphStyle(
            "footer",
            parent=base["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=8,
            textColor=MUTED,
            alignment=TA_CENTER,
        ),
        "cell": ParagraphStyle(
            "cell",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8,
            textColor=DARK,
            leading=10,
        ),
        "cell_h": ParagraphStyle(
            "cell_h",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            textColor=colors.white,
            leading=10,
        ),
    }
    return styles


def header_footer(canvas, doc):
    canvas.saveState()
    page = canvas.getPageNumber()
    header = f"LockerBeef · Colbeef S.A.S. · Documentación técnica   Página {page}"
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(1.8 * cm, A4[1] - 1.2 * cm, header)
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.4)
    canvas.line(1.8 * cm, A4[1] - 1.35 * cm, A4[0] - 1.8 * cm, A4[1] - 1.35 * cm)
    canvas.line(1.8 * cm, 1.3 * cm, A4[0] - 1.8 * cm, 1.3 * cm)
    canvas.drawCentredString(
        A4[0] / 2,
        0.85 * cm,
        "Documentación Técnica Sistema LockerBeef Colbeef · Versión 1.0",
    )
    canvas.restoreState()


def p(styles, text, style="body"):
    return Paragraph(text.replace("\n", "<br/>"), styles[style])


def bullets(styles, items):
    flow = []
    for it in items:
        flow.append(
            ListItem(Paragraph(it, styles["bullet"]), leftIndent=12, bulletColor=ACCENT)
        )
    return ListFlowable(flow, bulletType="bullet", start="•", leftIndent=10, spaceBefore=2, spaceAfter=6)


def table(styles, headers, rows, col_widths=None):
    data = [[Paragraph(h, styles["cell_h"]) for h in headers]]
    for row in rows:
        data.append([Paragraph(str(c), styles["cell"]) for c in row])
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, HEADER_BG]),
                ("GRID", (0, 0), (-1, -1), 0.4, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return t


def section(styles, title):
    return KeepTogether([Spacer(1, 4), p(styles, title, "h1")])


def build():
    styles = make_styles()
    doc = SimpleDocTemplate(
        str(OUT),
        pagesize=A4,
        leftMargin=1.8 * cm,
        rightMargin=1.8 * cm,
        topMargin=2.0 * cm,
        bottomMargin=1.8 * cm,
        title="Documentación Técnica — Sistema LockerBeef",
        author="Tecnología Colbeef",
    )
    story = []
    W = A4[0] - 3.6 * cm

    # Portada
    story.append(Spacer(1, 1.2 * cm))
    story.append(p(styles, "Colbeef", "cover_kicker"))
    story.append(p(styles, "Documentación Técnica — Sistema LockerBeef", "cover_title"))
    story.append(
        p(
            styles,
            "Documentación integral del código, la arquitectura, los lenguajes y la lógica "
            "de negocio del portal de control de lockers, dotaciones y personal "
            "(<b>LockerBeef</b> / gestor_lockers) de Colbeef.",
            "cover_sub",
        )
    )
    story.append(Spacer(1, 0.4 * cm))
    story.append(p(styles, "Autor de referencia técnica: equipo de Tecnología Colbeef", "meta"))
    story.append(p(styles, "Versión del documento: 1.0 · Producto: LockerBeef", "meta"))
    story.append(
        p(styles, "Repositorio: https://github.com/brayang466/gestion-lockers", "meta")
    )
    story.append(Spacer(1, 0.8 * cm))

    story.append(p(styles, "Tabla de contenido", "h1"))
    toc = [
        "1. Resumen ejecutivo",
        "2. Lenguajes y stack tecnológico",
        "3. Arquitectura general",
        "4. Estructura del proyecto",
        "5. Configuración y variables de entorno",
        "6. Modelo de datos (base de datos)",
        "7. Autenticación, sesión y seguridad",
        "8. Roles, módulos y control de acceso",
        "9. Módulos funcionales",
        "10. Flujos operativos",
        "11. Lógica de negocio destacada",
        "12. Sistema de correo",
        "13. Usabilidad (auditoría de navegación)",
        "14. Capa de presentación (frontend)",
        "15. Referencia de rutas (endpoints)",
        "16. Despliegue y ejecución",
        "17. Convenciones y notas de mantenimiento (nivel senior)",
    ]
    for line in toc:
        story.append(p(styles, f"• {line}", "toc"))

    story.append(PageBreak())

    # 1
    story.append(section(styles, "1. Resumen ejecutivo"))
    story.append(
        p(
            styles,
            "El <b>Sistema LockerBeef Colbeef</b> es una aplicación web monolítica construida "
            "sobre <b>Python + Flask</b> con persistencia en <b>MySQL</b> (ORM Flask-SQLAlchemy). "
            "Centraliza el control de lockers, dotaciones y personal por área de trabajo:",
        )
    )
    story.append(
        bullets(
            styles,
            [
                "<b>Inventario de lockers y dotaciones:</b> bases, disponibles, ingresos y seca-botas.",
                "<b>Asignaciones y personal:</b> personal pendiente, registro de asignaciones, personal presupuestado.",
                "<b>Operaciones:</b> historial de retiros y formularios de ingreso.",
                "<b>Multi-área:</b> selector de área de sesión (DESPOSTE, BENEFICIO, CALIDAD, LOGISTICA, EXTERNOS/OTRAS AREAS, etc.).",
                "<b>Administración:</b> gestión de usuarios y roles (solo superadmin).",
                "<b>Usabilidad:</b> registro automático de navegación por usuario (hora, fecha, área, acción).",
                "<b>Mantenimiento de área:</b> bloqueo de DESPOSTE para usuarios distintos de superadmin.",
            ],
        )
    )
    story.append(p(styles, "Características transversales:"))
    story.append(
        bullets(
            styles,
            [
                "Recuperación de contraseña por correo electrónico (SMTP).",
                "Cierre de sesión por inactividad (25 minutos).",
                "Favicon e identidad visual LockerBeef / Colbeef.",
                "Dashboard con estadísticas en tiempo real (polling HTTP).",
                "Dashboard React opcional (Vite) servido como estáticos.",
            ],
        )
    )

    # 2
    story.append(section(styles, "2. Lenguajes y stack tecnológico"))
    story.append(
        table(
            styles,
            ["Capa", "Tecnología", "Uso principal"],
            [
                ["Backend", "Python 3.x", "Lógica de negocio, rutas HTTP, scripts"],
                ["Framework web", "Flask ≥ 3.0", "Enrutamiento, sesiones, Application Factory"],
                ["ORM", "Flask-SQLAlchemy ≥ 3.1", "Persistencia relacional tipada"],
                ["Plantillas", "Jinja2", "HTML del lado del servidor (SSR)"],
                ["Base de datos", "MySQL 8+ (utf8mb4)", "Persistencia"],
                ["Driver BD", "PyMySQL", "Conexión MySQL vía SQLAlchemy"],
                ["Correo", "smtplib + email", "Envío SMTP (TLS / SSL)"],
                ["Config", "python-dotenv", "Variables desde .env"],
                ["Passwords", "Werkzeug", "Hash y verificación"],
                ["Tokens", "itsdangerous", "Restablecimiento de contraseña"],
                ["Frontend principal", "HTML5, CSS3, JS vanilla", "UI responsiva SSR"],
                ["Tipografías", "Plus Jakarta Sans", "Identidad visual"],
                ["Dashboard opcional", "React 18 + Vite 5 + Tailwind", "Build en /static/dashboard/"],
                ["Excel / import", "openpyxl", "Scripts de importación"],
                ["Entrada desarrollo", "run.py", "app.run con host/puerto"],
            ],
            col_widths=[W * 0.22, W * 0.32, W * 0.46],
        )
    )
    story.append(Spacer(1, 6))
    story.append(
        p(
            styles,
            "<b>Principio de diseño:</b> monolito modular con un blueprint (<b>main</b>) y "
            "configuración de módulos (<b>MODULOS_CONFIG</b>). La UI operativa es Jinja2 + CSS + JS vanilla. "
            "El tiempo real del dashboard usa polling HTTP hacia <b>/dashboard/api/stats</b>.",
        )
    )

    # 3
    story.append(section(styles, "3. Arquitectura general"))
    arch = """┌──────────────────────────────────────────────┐
│  Navegador (cliente)                         │
│  HTML + CSS + JS vanilla (+ React opcional)  │
└────────────────────┬─────────────────────────┘
                     │ HTML SSR / HTTP
                     ▼
┌──────────────────────────────────────────────┐
│  Flask — create_app                          │
│  before_request: idle · DESPOSTE · usabilidad│
│  Blueprint main · decoradores de acceso      │
└──────────┬───────────────────┬───────────────┘
           ▼                   ▼
     MySQL (gestor_lockers)   SMTP (reset password)"""
    story.append(Preformatted(arch, styles["code"]))
    story.append(
        p(
            styles,
            "<b>Patrón:</b> monolito modular. Las rutas orquestan validación, filtrado por área y "
            "renderizado. La configuración de cada módulo CRUD vive en <b>MODULOS_CONFIG</b>.",
        )
    )
    story.append(p(styles, "Ciclo de vida de una petición:", "h2"))
    story.append(
        bullets(
            styles,
            [
                "<b>_idle_timeout_guard</b> actualiza actividad, aplica mantenimiento DESPOSTE y registra usabilidad (omite /static/).",
                "La ruta valida acceso (login, área actual, gate superadmin si aplica).",
                "La vista aplica filtros de dominio y renderiza Jinja2 o responde JSON.",
                "El cliente consume CSS/JS y puede refrescar stats vía API.",
            ],
        )
    )

    # 4
    story.append(section(styles, "4. Estructura del proyecto"))
    tree = """gestor_lockers/
├── run.py                 # Arranque desarrollo
├── build_dashboard.bat    # Build React
├── requirements.txt
├── .env                   # Secretos (no versionar)
├── app/
│   ├── __init__.py        # create_app
│   ├── config.py
│   ├── models/            # ORM
│   ├── routes/main.py     # Núcleo de negocio
│   ├── utils/email.py
│   ├── templates/         # Jinja2
│   └── static/            # css, js, favicon, dashboard/
├── frontend/              # Fuente React + Vite
├── database/              # SQL / dumps
├── scripts/               # admin, import, export
├── docs/                  # Documentación
└── datos_importar/        # CSV"""
    story.append(Preformatted(tree, styles["code"]))

    # 5
    story.append(section(styles, "5. Configuración y variables de entorno"))
    story.append(
        p(
            styles,
            "<b>app/config.py</b> centraliza la configuración mediante la clase <b>Config</b>, "
            "poblada desde <b>.env</b> (python-dotenv).",
        )
    )
    story.append(
        table(
            styles,
            ["Variable", "Descripción", "Default / notas"],
            [
                ["SECRET_KEY", "Firma de sesión", "Obligatorio en producción"],
                ["PORT", "Puerto de run.py", "5000"],
                ["MYSQL_HOST / PORT", "Conexión MySQL", "127.0.0.1 / 3306"],
                ["MYSQL_USER / PASSWORD", "Credenciales BD", "root / vacío"],
                ["MYSQL_DATABASE", "Nombre de base", "gestor_lockers"],
                ["MAIL_SERVER / HOST", "Servidor SMTP", "smtp.gmail.com"],
                ["MAIL_PORT", "Puerto SMTP", "587 TLS / 465 SSL"],
                ["MAIL_USERNAME / PASSWORD", "Credenciales SMTP", "—"],
                ["MAIL_DEFAULT_SENDER / FROM", "Remitente", "Fallback a username"],
                ["MAIL_FROM_NAME", "Nombre visible", "LockerBeef"],
                ["PASSWORD_RESET_EXPIRE_MINUTES", "Vigencia del enlace", "15"],
                ["APP_URL", "URL pública (correos)", "http://192.168.x.x:5000"],
            ],
            col_widths=[W * 0.34, W * 0.33, W * 0.33],
        )
    )
    story.append(Spacer(1, 6))
    story.append(
        p(
            styles,
            "<b>Seguridad:</b> .env nunca debe versionarse con secretos reales. "
            "SECRET_KEY débil solo es aceptable en desarrollo local.",
        )
    )

    # 6
    story.append(section(styles, "6. Modelo de datos (base de datos)"))
    story.append(
        p(
            styles,
            "Motor MySQL, utf8mb4. Tablas con <b>db.create_all()</b> al arrancar; evolución con "
            "scripts en <b>database/</b> y modelos ORM.",
        )
    )
    story.append(p(styles, "6.1 Usuarios y áreas", "h2"))
    story.append(
        table(
            styles,
            ["Tabla", "Descripción"],
            [
                ["usuarios", "Cuentas; UK email; roles; área; activo"],
                ["area_trabajo", "Catálogo de áreas (nombre UNIQUE, UPPER)"],
                ["usabilidad_log", "Auditoría de navegación; FK opcional a usuarios"],
            ],
            col_widths=[W * 0.28, W * 0.72],
        )
    )
    story.append(p(styles, "6.2 Lockers y dotaciones", "h2"))
    story.append(
        table(
            styles,
            ["Tabla", "Descripción"],
            [
                ["base_lockers", "Inventario maestro de lockers"],
                ["locker_disponibles", "Lockers disponibles"],
                ["base_dotaciones", "Inventario maestro de dotaciones"],
                ["dotaciones_disponibles", "Soporte / legado"],
                ["seca_botas_disponibles", "Códigos de seca-botas"],
                ["ingreso_lockers / ingreso_dotacion", "Altas de ingreso"],
            ],
            col_widths=[W * 0.38, W * 0.62],
        )
    )
    story.append(p(styles, "6.3 Personal y operaciones", "h2"))
    story.append(
        table(
            styles,
            ["Tabla", "Descripción"],
            [
                ["registro_personal", "Registro de personal"],
                ["registro_asignaciones", "Asignaciones / pendiente; flag es_planta_desposte"],
                ["historial_retiros", "Retiros; flag es_planta_desposte"],
                ["personal_presupuestado", "Cupos por área"],
            ],
            col_widths=[W * 0.32, W * 0.68],
        )
    )
    story.append(p(styles, "6.4 Diagrama entidad-relación (resumen)", "h2"))
    er = """usuarios ──< usabilidad_log
area_trabajo   (catálogo de sesión)
base_lockers / locker_disponibles / seca_botas_disponibles
base_dotaciones / registro_asignaciones / historial_retiros
personal_presupuestado / ingreso_* / registro_personal

Aislamiento multi-área por columnas (area, area_uso, subarea, es_planta_desposte)."""
    story.append(Preformatted(er, styles["code"]))

    # 7
    story.append(section(styles, "7. Autenticación, sesión y seguridad"))
    story.append(p(styles, "7.1 Acceso a datos", "h2"))
    story.append(
        p(
            styles,
            "Acceso a MySQL mediante Flask-SQLAlchemy (<b>db.session</b>, modelos en <b>app/models/</b>).",
        )
    )
    story.append(p(styles, "7.2 Inicio de sesión", "h2"))
    story.append(
        p(
            styles,
            "<b>/login</b> valida email + activo + <b>check_password_hash</b>. Al autenticar setea "
            "user_id, user_nombre, user_email, user_rol, user_area; limpia current_area y redirige a "
            "<b>/areas</b>. Existe también <b>/acceso-integrado</b>.",
        )
    )
    story.append(p(styles, "7.3 Gestión de sesión", "h2"))
    story.append(
        bullets(
            styles,
            [
                "Idle timeout: <b>25 minutos</b>.",
                "Reloj en la barra de navegación.",
                "Logout: GET /logout limpia sesión.",
            ],
        )
    )
    story.append(p(styles, "7.4 Reset de contraseña", "h2"))
    story.append(
        p(
            styles,
            "Tokens firmados con <b>itsdangerous</b>, vigencia configurable. Requiere SMTP. "
            "Guía: docs/RECUPERACION_CONTRASENA.md.",
        )
    )
    story.append(p(styles, "7.5 Controles adicionales", "h2"))
    story.append(
        bullets(
            styles,
            [
                "Passwords hasheados (Werkzeug).",
                "Rutas admin con @_superadmin_required.",
                "DESPOSTE bloqueado en mantenimiento salvo superadmin.",
            ],
        )
    )

    # 8
    story.append(section(styles, "8. Roles, módulos y control de acceso"))
    story.append(p(styles, "8.1 Roles", "h2"))
    story.append(
        table(
            styles,
            ["Rol", "Código", "Capacidades"],
            [
                ["Super Administrador", "superadmin", "Todas las áreas; edición; usuarios; usabilidad; DESPOSTE"],
                ["Administrador", "admin", "Todas las áreas; edición; sin usuarios/usabilidad"],
                ["Coordinador", "coordinador", "Su área; edición"],
                ["Usuario", "usuario", "Su área; solo consulta"],
            ],
            col_widths=[W * 0.25, W * 0.18, W * 0.57],
        )
    )
    story.append(p(styles, "8.2 Control de acceso", "h2"))
    story.append(
        table(
            styles,
            ["Mecanismo", "Efecto"],
            [
                ["@login_required", "Exige sesión"],
                ["@_require_current_area", "Exige área elegida"],
                ["@_superadmin_required", "Solo superadmin"],
                ["_user_can_edit()", "Permite mutaciones en módulos"],
                ["_allowed_areas_for_user()", "Áreas del selector"],
            ],
            col_widths=[W * 0.38, W * 0.62],
        )
    )
    story.append(p(styles, "8.3 Matriz resumida", "h2"))
    story.append(
        table(
            styles,
            ["Capacidad", "Usuario", "Coord.", "Admin", "Superadmin"],
            [
                ["Selector de áreas", "✓", "✓", "✓ todas", "✓ todas"],
                ["Dashboard / consulta", "✓", "✓", "✓", "✓"],
                ["Editar módulos", "✗", "✓", "✓", "✓"],
                ["Gestión de usuarios", "✗", "✗", "✗", "✓"],
                ["Usabilidad", "✗", "✗", "✗", "✓"],
                ["DESPOSTE (mantenimiento)", "✗", "✗", "✗", "✓"],
            ],
            col_widths=[W * 0.32, W * 0.17, W * 0.17, W * 0.17, W * 0.17],
        )
    )

    # 9
    story.append(section(styles, "9. Módulos funcionales"))
    story.append(
        bullets(
            styles,
            [
                "<b>Selector de áreas</b> (/areas) con modal de mantenimiento para DESPOSTE.",
                "<b>Dashboard</b> (/dashboard) con KPIs y sidebar.",
                "<b>Inventario:</b> Base Lockers, Locker Disponibles, Seca Botas, Base Dotaciones, Dotaciones Disponibles.",
                "<b>Ingresos</b> (nav): Ingreso Lockers, Ingreso Dotación, Registro personal.",
                "<b>Personal/operaciones:</b> Personal Pendiente, Presupuestado, Asignaciones, Historial Retiros.",
                "<b>Superadmin:</b> Gestión de usuarios y Usabilidad por usuario.",
                "<b>Suite Principal:</b> enlace externo para admin/superadmin.",
            ],
        )
    )

    # 10
    story.append(section(styles, "10. Flujos operativos"))
    story.append(p(styles, "10.1 Acceso estándar", "h2"))
    flow_a = """Login → /areas → /entrar-area/<NOMBRE> → session[current_area]
→ /dashboard → /dashboard/<modulo> (CRUD según rol)"""
    story.append(Preformatted(flow_a, styles["code"]))
    story.append(p(styles, "10.2 DESPOSTE en mantenimiento", "h2"))
    story.append(
        p(
            styles,
            "Usuarios distintos de superadmin reciben el anuncio: "
            "<i>«Esta área se encuentra en mantenimiento. Estará disponible luego.»</i> "
            "También se bloquea en servidor (/entrar-area/DESPOSTE) y se expulsan sesiones previas.",
        )
    )
    story.append(p(styles, "10.3 Usabilidad", "h2"))
    story.append(
        p(
            styles,
            "Cada navegación autenticada (con omisiones y debounce) inserta un registro en "
            "<b>usabilidad_log</b>. Superadmin consulta <b>/dashboard/usabilidad</b>.",
        )
    )

    # 11
    story.append(section(styles, "11. Lógica de negocio destacada"))
    story.append(
        bullets(
            styles,
            [
                "<b>Scope por área:</b> helpers _lockers_por_sesion_filter, _registro_area_scope_filter, _base_dotaciones_scope_filter.",
                "<b>Flag es_planta_desposte:</b> separa planta Desposte de registros generales.",
                "<b>CRUD por configuración:</b> MODULOS_CONFIG + ruta /dashboard/&lt;modulo_id&gt;.",
                "<b>Hook unificado:</b> idle + usabilidad + mantenimiento DESPOSTE.",
                "<b>Verificación de códigos:</b> /dashboard/api/verificar-codigos.",
            ],
        )
    )

    # 12
    story.append(section(styles, "12. Sistema de correo"))
    story.append(
        table(
            styles,
            ["Evento", "Cuándo"],
            [
                ["Reset de contraseña", "Usuario solicita recuperación"],
                ["Notificación de cambio", "Tras restablecer (si aplica)"],
            ],
            col_widths=[W * 0.35, W * 0.65],
        )
    )
    story.append(Spacer(1, 6))
    story.append(
        p(
            styles,
            "Implementado en <b>app/utils/email.py</b>. Requiere MAIL_USERNAME, MAIL_PASSWORD y preferiblemente APP_URL.",
        )
    )

    # 13
    story.append(section(styles, "13. Usabilidad (auditoría de navegación)"))
    story.append(p(styles, "13.1 Captura automática", "h2"))
    story.append(
        bullets(
            styles,
            [
                "Hook en before_request.",
                "Omite estáticos, login y APIs de polling.",
                "Debounce ~4 s por mismo path GET.",
                "Guarda usuario, rol, área, path, método, acción y timestamp.",
            ],
        )
    )
    story.append(p(styles, "13.2 Panel (superadmin)", "h2"))
    story.append(
        p(
            styles,
            "<b>/dashboard/usabilidad</b>: filtros por usuario, fecha y texto; agrupación por día "
            "(máx. 500 registros); acciones legibles.",
        )
    )

    # 14
    story.append(section(styles, "14. Capa de presentación (frontend)"))
    story.append(
        bullets(
            styles,
            [
                "SSR con Jinja2; páginas extienden base.html.",
                "CSS: static/css/app.css y login.css.",
                "JS: app.js, login.js, dashboard-reminders.js.",
                "React opcional vía build_dashboard.bat.",
                "Favicon: static/favicon.svg.",
            ],
        )
    )
    story.append(
        table(
            styles,
            ["Archivo", "Función"],
            [
                ["app.js", "Tema, navegación, utilidades"],
                ["login.js", "Validación / vistas login"],
                ["dashboard-reminders.js", "Recordatorios dashboard"],
            ],
            col_widths=[W * 0.35, W * 0.65],
        )
    )

    # 15
    story.append(section(styles, "15. Referencia de rutas (endpoints)"))
    story.append(p(styles, "Autenticación", "h2"))
    story.append(
        table(
            styles,
            ["Ruta", "Métodos", "Función"],
            [
                ["/login", "GET, POST", "Inicio de sesión"],
                ["/acceso-integrado", "GET, POST", "Login integrado"],
                ["/logout", "GET", "Cerrar sesión"],
                ["/registro", "GET, POST", "Alta de usuario"],
                ["/restablecer-contrasena", "GET, POST", "Solicitar reset"],
                ["/restablecer-contrasena/confirmar", "GET, POST", "Nueva contraseña"],
            ],
            col_widths=[W * 0.42, W * 0.18, W * 0.40],
        )
    )
    story.append(p(styles, "Áreas, dashboard y administración", "h2"))
    story.append(
        table(
            styles,
            ["Ruta", "Métodos", "Función"],
            [
                ["/", "GET", "Redirect según sesión"],
                ["/areas", "GET", "Selector de área"],
                ["/entrar-area/&lt;path&gt;", "GET", "Fija área"],
                ["/dashboard", "GET", "Panel de control"],
                ["/dashboard/api/stats", "GET", "KPIs JSON"],
                ["/dashboard/api/verificar-codigos", "GET", "Disponibilidad códigos"],
                ["/dashboard/&lt;modulo_id&gt;", "GET, POST", "CRUD genérico"],
                ["/dashboard/registro/&lt;modulo_id&gt;", "GET, POST", "Formularios ingreso"],
                ["/dashboard/usuarios", "GET, POST", "Usuarios (superadmin)"],
                ["/dashboard/usabilidad", "GET", "Usabilidad (superadmin)"],
            ],
            col_widths=[W * 0.42, W * 0.18, W * 0.40],
        )
    )

    # 16
    story.append(section(styles, "16. Despliegue y ejecución"))
    story.append(p(styles, "16.1 Requisitos", "h2"))
    story.append(
        bullets(
            styles,
            [
                "Python 3.x y MySQL 8+.",
                "pip install -r requirements.txt (venv recomendado).",
                "Node.js opcional si se reconstruye el dashboard React.",
            ],
        )
    )
    story.append(p(styles, "16.2 Base de datos", "h2"))
    story.append(
        bullets(
            styles,
            [
                "Ejecutar database/00_crear_base_vacia.sql.",
                "Configurar .env (MYSQL_*).",
                "Arrancar app una vez (db.create_all).",
                "python scripts/crear_admin.py",
                "Opcional: asignar_superadmin.py e importar_todo.py.",
            ],
        )
    )
    story.append(p(styles, "16.3 Arranque", "h2"))
    story.append(Preformatted("# Desarrollo\npython run.py\n# http://127.0.0.1:5000  o  http://192.168.x.x:5000\n\n# Build opcional React\nbuild_dashboard.bat", styles["code"]))

    # 17
    story.append(section(styles, "17. Convenciones y notas de mantenimiento (nivel senior)"))
    story.append(
        bullets(
            styles,
            [
                "<b>Filtros de área como fuente de verdad.</b> No listar inventarios sin helpers de scope.",
                "<b>Configurar módulos, no duplicar CRUD.</b> Nuevas tablas → modelo + MODULOS_CONFIG.",
                "<b>Roles normalizados.</b> Comparar siempre .strip().lower().",
                "<b>Hook barato.</b> Respetar debounce de usabilidad y omisión de estáticos/APIs.",
                "<b>Esquema evolutivo.</b> create_all() no altera columnas; usar SQL + modelo.",
                "<b>Jinja y dicts.</b> Evitar claves items/keys/values en estructuras de plantilla.",
                "<b>Secretos fuera del repo.</b> Documentar nombres de variables, no valores.",
                "<b>Mantenimiento DESPOSTE.</b> Flag DESPOSTE_EN_MANTENIMIENTO en main.py.",
                "<b>Documentación dual.</b> Alinear DOCUMENTACION_CODIGO.md con este PDF al cambiar contratos.",
                "<b>Front React opcional.</b> Si se usa en producción, sincronizar con MODULOS_CONFIG.",
            ],
        )
    )

    story.append(Spacer(1, 1.2 * cm))
    story.append(
        p(
            styles,
            "<i>Fin del documento — Documentación Técnica Sistema LockerBeef Colbeef · Versión 1.0</i>",
            "footer",
        )
    )

    doc.build(story, onFirstPage=header_footer, onLaterPages=header_footer)
    print(f"PDF generado: {OUT}")


if __name__ == "__main__":
    build()
