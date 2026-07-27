# Documentación de código — LockerBeef (`gestor_lockers`)

**Producto:** LockerBeef · Colbeef S.A.S.  
**Repositorio:** https://github.com/brayang466/gestion-lockers  
**Autor de referencia:** equipo de Tecnología Colbeef  
**Versión del documento:** 1.0  
**Audiencia:** desarrolladores, mantenedores y revisores técnicos (nivel senior)

---

## Tabla de contenido

1. [Propósito de este documento](#1-propósito-de-este-documento)
2. [Lenguajes y stack tecnológico](#2-lenguajes-y-stack-tecnológico)
3. [Arquitectura y patrones](#3-arquitectura-y-patrones)
4. [Estructura del repositorio](#4-estructura-del-repositorio)
5. [Punto de entrada y ciclo de vida de la app](#5-punto-de-entrada-y-ciclo-de-vida-de-la-app)
6. [Configuración](#6-configuración)
7. [Capa de datos (ORM)](#7-capa-de-datos-orm)
8. [Capa de rutas y lógica de negocio](#8-capa-de-rutas-y-lógica-de-negocio)
9. [Autenticación, sesión y seguridad](#9-autenticación-sesión-y-seguridad)
10. [Multi-área y filtrado por sesión](#10-multi-área-y-filtrado-por-sesión)
11. [Sistema de módulos (`MODULOS_CONFIG`)](#11-sistema-de-módulos-modulos_config)
12. [Usabilidad (auditoría de navegación)](#12-usabilidad-auditoría-de-navegación)
13. [DESPOSTE en mantenimiento](#13-desposte-en-mantenimiento)
14. [Capa de presentación](#14-capa-de-presentación)
15. [Frontend React (Vite)](#15-frontend-react-vite)
16. [Correo electrónico](#16-correo-electrónico)
17. [Scripts y base de datos](#17-scripts-y-base-de-datos)
18. [Convenciones senior y guía de extensión](#18-convenciones-senior-y-guía-de-extensión)

---

## 1. Propósito de este documento

Este documento describe **cómo está construido el código** de LockerBeef: lenguajes, estructura, contratos entre capas, lógica de dominio y convenciones para mantener el sistema sin degradar la arquitectura.

Complementa:

- `docs/DOCUMENTACION_TECNICA.md` — documento institucional (entrega / arquitectura de producto).
- Guías operativas en `docs/` (roles, BD, correo, Desposte, formularios).

---

## 2. Lenguajes y stack tecnológico

### 2.1 Resumen por capa

| Capa | Lenguaje / tecnología | Rol en el código |
|------|------------------------|------------------|
| Backend | **Python 3.x** | Lógica de negocio, rutas HTTP, ORM, scripts |
| Framework | **Flask ≥ 3.0** | Application Factory, blueprints, sesiones, SSR |
| ORM | **Flask-SQLAlchemy ≥ 3.1** | Modelos, consultas, `db.create_all()` |
| Driver BD | **PyMySQL ≥ 1.1** | Conexión a MySQL vía SQLAlchemy |
| Plantillas | **Jinja2** (incluido en Flask) | HTML del lado del servidor |
| Estilos (UI principal) | **CSS3** | `app/static/css/app.css`, `login.css` |
| Cliente (UI principal) | **JavaScript (ES5/ES6 vanilla)** | Temas, timer de sesión, validaciones login, recordatorios |
| Dashboard opcional | **React 18 + Vite 5 + Tailwind 3** | Build estático bajo `/static/dashboard/` |
| Persistencia | **MySQL 8+** (utf8mb4) | Base `gestor_lockers` |
| Config | **python-dotenv** | Variables desde `.env` |
| Seguridad passwords | **Werkzeug** | `generate_password_hash` / `check_password_hash` |
| Tokens reset | **itsdangerous** | `URLSafeTimedSerializer` |
| Correo | **smtplib** + **email** (stdlib) | Recuperación de contraseña |
| Excel / import | **openpyxl** | Scripts de importación |
| Cripto / TLS | **cryptography** | Soporte de conexiones seguras |

### 2.2 Dependencias Python (`requirements.txt`)

```
Flask>=3.0.0
Flask-SQLAlchemy>=3.1.0
PyMySQL>=1.1.0
cryptography>=42.0.0
python-dotenv>=1.0.0
openpyxl>=3.1.0
```

### 2.3 Dependencias Node (`frontend/package.json`)

Usadas solo para construir el dashboard React:

- `react`, `react-dom`, `react-router-dom`
- `vite`, `@vitejs/plugin-react`
- `tailwindcss`, `postcss`, `autoprefixer`

**Principio:** la UI operativa en producción es **Flask + Jinja2**. React es un artefacto de build opcional servido como estáticos.

---

## 3. Arquitectura y patrones

### 3.1 Estilo arquitectónico

**Monolito modular Flask** con:

- Un único blueprint `main` (`app/routes/main.py`) que concentra rutas y reglas de negocio.
- Modelos en paquete `app/models/` (un archivo por entidad).
- Presentación SSR (Jinja) + assets estáticos.
- Multi-tenancy lógico por **área de trabajo en sesión** (`session["current_area"]`), no por esquemas BD separados.

```
Navegador
   │  HTML / form / fetch JSON
   ▼
Flask (create_app)
   │  before_request: idle timeout · DESPOSTE · usabilidad
   │  Blueprint main
   ▼
SQLAlchemy ──► MySQL (gestor_lockers)
   │
   └─► SMTP (reset password)
```

### 3.2 Patrones de diseño usados

| Patrón | Dónde | Para qué |
|--------|-------|----------|
| **Application Factory** | `app/__init__.py` → `create_app()` | Crear app testable y configurable |
| **Blueprint** | `app/routes/main.py` | Agrupar rutas |
| **Configuración por entorno** | `app/config.py` + `.env` | Secretos y conexión BD fuera del código |
| **CRUD dirigido por configuración** | `MODULOS_CONFIG` | Un motor genérico para N módulos |
| **Decoradores de acceso** | `login_required`, `_require_current_area`, `_superadmin_required` | Cross-cutting authz |
| **Hooks de request** | `_idle_timeout_guard` | Timeout, mantenimiento, auditoría |
| **Context processor** | `inject_current_year` | Datos globales a plantillas |

### 3.3 Ciclo de vida de una petición autenticada

1. Flask recibe el request.
2. `_idle_timeout_guard` (antes de la vista):
   - Omite `/static/`, login, logout, favicon.
   - Si hay sesión y pasó el idle (25 min) → limpia sesión y redirige a login.
   - Si `current_area == DESPOSTE` y el usuario no es superadmin (mantenimiento) → expulsa a `/areas`.
   - Registra usabilidad (con debounce).
3. Decoradores de la ruta validan login / área / rol.
4. La vista consulta ORM, aplica filtros de área y renderiza o responde JSON.
5. Jinja genera HTML; el navegador carga CSS/JS estáticos.

---

## 4. Estructura del repositorio

```
gestor_lockers/
├── run.py                          # Arranque desarrollo
├── build_dashboard.bat             # Build React → app/static/dashboard
├── requirements.txt
├── README.md
├── .env                            # Secretos (NO versionar)
├── .gitignore
│
├── app/
│   ├── __init__.py                 # create_app, db, register blueprint
│   ├── config.py                   # Clase Config
│   ├── models/                     # Entidades ORM
│   │   ├── __init__.py             # Exports públicos
│   │   ├── usuario.py
│   │   ├── area_trabajo.py
│   │   ├── base_lockers.py
│   │   ├── locker_disponibles.py
│   │   ├── base_dotaciones.py
│   │   ├── dotaciones_disponibles.py
│   │   ├── registro_personal.py
│   │   ├── registro_asignaciones.py
│   │   ├── historial_retiros.py
│   │   ├── personal_presupuestado.py
│   │   ├── ingreso_lockers.py
│   │   ├── ingreso_dotacion.py
│   │   ├── seca_botas_disponibles.py
│   │   └── usabilidad_log.py
│   ├── routes/
│   │   └── main.py                 # Rutas + reglas de dominio (núcleo)
│   ├── utils/
│   │   └── email.py                # SMTP reset password
│   ├── templates/                  # Vistas Jinja2
│   │   ├── base.html
│   │   ├── login.html
│   │   ├── areas.html
│   │   ├── dashboard.html
│   │   ├── modulo.html
│   │   ├── usuarios.html
│   │   ├── usabilidad.html
│   │   └── includes/               # favicon, iconos de módulos
│   └── static/
│       ├── css/
│       ├── js/
│       ├── favicon.svg
│       └── dashboard/              # Output Vite
│
├── frontend/                       # Código fuente React
│   ├── package.json
│   ├── vite.config.js
│   ├── public/favicon.svg
│   └── src/
│
├── database/                       # SQL, dumps, migraciones
├── scripts/                        # CLI: admin, import, export, sync
├── docs/                           # Documentación
└── datos_importar/                 # CSV de carga
```

---

## 5. Punto de entrada y ciclo de vida de la app

### 5.1 `run.py`

1. Carga `.env` con `override=True` (salvo `PORT` ya definido en el shell).
2. Importa `create_app` y instancia `app`.
3. Ejecuta `app.run(debug=True, host="0.0.0.0", port=PORT|5000)`.

### 5.2 `app/__init__.py` — `create_app()`

```python
def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    db.init_app(app)
    from app.routes import main
    app.register_blueprint(main.bp)

    @app.context_processor
    def inject_current_year():
        return {"current_year": datetime.utcnow().year}

    with app.app_context():
        db.create_all()   # Crea tablas faltantes; NO altera columnas existentes
    return app
```

**Implicación senior:** `create_all()` no sustituye migraciones. Columnas nuevas requieren SQL en `database/` + actualización del modelo.

---

## 6. Configuración

### 6.1 `app/config.py`

| Variable | Uso |
|----------|-----|
| `SECRET_KEY` | Firma de cookies de sesión |
| `MYSQL_*` | Host, puerto, user, password, database |
| `SQLALCHEMY_DATABASE_URI` | `mysql+pymysql://…` |
| `MAIL_*` | SMTP para reset de contraseña |
| `PASSWORD_RESET_EXPIRE_MINUTES` | Vigencia del token (default 15) |
| `APP_URL` | Base URL para enlaces en correos |
| `PERMANENT_SESSION_LIFETIME` | 30 días si “Recordarme” |

### 6.2 Reglas

- `.env` **nunca** con secretos reales en git.
- `SECRET_KEY` débil solo en desarrollo local.
- Preferir `APP_URL` explícita en LAN/producción para correos correctos.

---

## 7. Capa de datos (ORM)

### 7.1 Convenciones de modelo

Cada modelo:

- Hereda de `db.Model`.
- Declara `__tablename__`.
- Usa `datetime.utcnow` en `creado_en` cuando aplica.
- Exporta la clase en `app/models/__init__.py`.

### 7.2 Catálogo de entidades

| Clase | Tabla | Dominio |
|-------|-------|---------|
| `Usuario` | `usuarios` | Cuentas, roles, área asignada |
| `AreaTrabajo` | `area_trabajo` | Catálogo de áreas de sesión |
| `BaseLockers` | `base_lockers` | Inventario de lockers |
| `LockerDisponibles` | `locker_disponibles` | Lockers disponibles |
| `BaseDotaciones` | `base_dotaciones` | Inventario de dotaciones |
| `DotacionesDisponibles` | `dotaciones_disponibles` | Legacy / soporte |
| `RegistroPersonal` | `registro_personal` | Personal (modelo) |
| `RegistroAsignaciones` | `registro_asignaciones` | Asignaciones y “Personal Pendiente” |
| `HistorialRetiros` | `historial_retiros` | Retiros |
| `PersonalPresupuestado` | `personal_presupuestado` | Cupos por área |
| `IngresoLockers` | `ingreso_lockers` | Altas de lockers |
| `IngresoDotacion` | `ingreso_dotacion` | Altas de dotaciones |
| `SecaBotasDisponibles` | `seca_botas_disponibles` | Seca-botas |
| `UsabilidadLog` | `usabilidad_log` | Auditoría de navegación |

### 7.3 Relaciones

- Casi todo el filtrado es **por columnas de área** (`area`, `area_uso`, `subarea`, `es_planta_desposte`), no por FK entre tablas de negocio.
- **Única FK explícita relevante:** `UsabilidadLog.user_id → usuarios.id`.

### 7.4 Flag `es_planta_desposte`

En `RegistroAsignaciones` e `HistorialRetiros` separa registros de planta Desposte (CSV/import de planta) del resto, evitando mezclar códigos de subárea (LYD, CAL, …) con áreas generales homónimas.

---

## 8. Capa de rutas y lógica de negocio

### 8.1 Ubicación

Casi toda la lógica vive en `app/routes/main.py` (archivo grande). Agrupa:

- Constantes de dominio (`DESPOSTE_AREAS`, timeouts, flags).
- Helpers de filtrado por área.
- `MODULOS_CONFIG` / `MODULOS_ORDER`.
- Rutas HTTP y vistas.

### 8.2 Dominios de rutas

| Dominio | Prefijos / rutas |
|---------|------------------|
| Auth | `/login`, `/logout`, `/registro`, `/restablecer-contrasena*`, `/acceso-integrado` |
| Áreas | `/areas`, `/entrar-area/<path:nombre>` |
| Dashboard | `/`, `/dashboard` |
| APIs | `/dashboard/api/stats`, `/dashboard/api/verificar-codigos` |
| CRUD genérico | `/dashboard/<modulo_id>` |
| Formularios ingreso | `/dashboard/registro/<modulo_id>` |
| Superadmin | `/dashboard/usuarios`, `/dashboard/usabilidad` |
| Favicon | `/favicon.ico` |

**Orden de registro:** rutas específicas (`/dashboard/usuarios`, `/dashboard/usabilidad`) **antes** del catch-all `/dashboard/<modulo_id>`.

### 8.3 Helpers de filtrado (núcleo de negocio)

| Función | Responsabilidad |
|---------|-----------------|
| `_allowed_areas_for_user()` | Áreas visibles según rol |
| `_is_desposte_context()` | Sesión exactamente `DESPOSTE` |
| `_is_externos_area()` | Sesión EXTERNOS / OTRAS AREAS |
| `_lockers_por_sesion_filter()` | Scope de lockers por sesión |
| `_registro_area_scope_filter()` | Scope de asignaciones/retiros |
| `_base_dotaciones_scope_filter()` | Scope de dotaciones |
| `_dashboard_stats()` | KPIs del panel |
| `_user_can_edit()` | Permiso de mutación en módulos |

Estos filtros son la **fuente de verdad** del aislamiento multi-área. Cualquier nuevo listado debe reutilizarlos; no filtrar “a mano” en la plantilla.

---

## 9. Autenticación, sesión y seguridad

### 9.1 Login

1. Valida email + password con `check_password_hash`.
2. Rechaza cuentas `activo=False`.
3. Setea sesión:

```text
user_id, user_nombre, user_email, user_rol, user_area, session_started_ts_ms
```

4. Limpia `current_area` (obliga a elegir área).
5. Opcional: cookie `remember_email` + `session.permanent`.

### 9.2 Idle timeout

- Constante: `IDLE_TIMEOUT_SECONDS = 25 * 60`.
- Persistido en `session["last_activity_ts"]`.
- Al expirar: `session.clear()` → `/login?reason=idle`.

### 9.3 Reset de contraseña

- Token firmado (`itsdangerous`) con expiración configurable.
- Envío vía `app/utils/email.py`.
- Confirmación en `/restablecer-contrasena/confirmar`.

### 9.4 Roles (código)

| Rol | Código | Capacidades clave |
|-----|--------|-------------------|
| Super Administrador | `superadmin` | Todas las áreas; usuarios; usabilidad; edición |
| Administrador | `admin` | Todas las áreas; edición; sin usuarios/usabilidad |
| Coordinador | `coordinador` | Su área; edición |
| Usuario | `usuario` | Su área; solo lectura en módulos |

Funciones:

- `_is_superadmin()`
- `_user_can_edit()` → `superadmin | admin | coordinador`
- `_superadmin_required` → gate duro en usuarios y usabilidad

### 9.5 Controles actuales y deuda consciente

- Sesión firmada con `SECRET_KEY`.
- Passwords hasheados (Werkzeug).
- No hay Flask-WTF/CSRF global hoy: las mutaciones son formularios SSR clásicos; al añadir APIs JSON mutables, valorar CSRF o tokens.
- Uploads de evidencias no aplican en este producto (a diferencia de Mtto equipos).

---

## 10. Multi-área y filtrado por sesión

### 10.1 Flujo

```
Login → /areas → /entrar-area/<NOMBRE> → session[current_area] → /dashboard
```

### 10.2 DESPOSTE

Constantes:

```python
DESPOSTE_AREAS = ("DESPOSTE", "DES", "CAL", "LYD", "SST", "MTTO", "LOG", "EXT", "TIC")
```

- Sesión `DESPOSTE`: datos de planta (flag / filtros especiales).
- Sesión `LYD`/`CAL`/…: unión de área general + subárea en planta.
- Evitar cruzar Desposte con áreas generales que reutilizan códigos cortos.

### 10.3 EXTERNOS / OTRAS AREAS

- Excluye áreas internas de planta.
- Oculta módulo Personal Presupuestado en el sidebar.

---

## 11. Sistema de módulos (`MODULOS_CONFIG`)

### 11.1 Idea

Cada módulo es un **diccionario de configuración** que el motor genérico (`modulo()`) interpreta:

- `model` — clase SQLAlchemy
- `titulo`, `icon`
- `columnas` — listado
- `form_fields` — alta/edición
- Flags: `no_crear`, `solo_lectura`, `solo_estado_disponible`, `solo_sin_asignacion`, `solo_con_asignacion`, `area_key`, etc.

### 11.2 Orden de menú (`MODULOS_ORDER`)

1. Dotaciones Disponibles  
2. Locker Disponibles  
3. Seca Botas Disponibles  
4. Historial de Retiros  
5. Ingreso de Lockers *(fuera del sidebar; nav superior)*  
6. Ingreso de Dotación *(fuera del sidebar; nav superior)*  
7. Base de Lockers  
8. Base de Dotaciones  
9. Personal Pendiente (`registro-personal` → modelo `RegistroAsignaciones`)  
10. Personal Presupuestado  
11. Registro de Asignaciones  

### 11.3 Extender con un módulo nuevo (checklist)

1. Crear modelo en `app/models/<nombre>.py` y exportarlo.
2. Añadir entrada en `MODULOS_CONFIG` + ID en `MODULOS_ORDER`.
3. Icono en `templates/includes/module_icons.html` si hace falta.
4. Categoría en `MODULE_CATEGORIES` del dashboard (opcional).
5. Reiniciar app (`create_all`) o aplicar SQL si la tabla ya existía con otro esquema.
6. Verificar filtros de área (`area_key` / helpers).

**No** copiar-pegar una ruta CRUD completa salvo que el flujo sea especial (como usuarios o usabilidad).

---

## 12. Usabilidad (auditoría de navegación)

### 12.1 Objetivo

Registrar **qué pantallas visita cada usuario**, con hora/fecha, área y acción legible. Solo **superadmin** consulta el historial.

### 12.2 Persistencia

Modelo `UsabilidadLog` / tabla `usabilidad_log`:

| Campo | Tipo | Uso |
|-------|------|-----|
| `user_id` | FK nullable | Usuario |
| `user_nombre`, `user_email`, `user_rol` | string | Snapshot al momento del evento |
| `area` | string | `current_area` |
| `path`, `metodo` | string | Request |
| `accion` | string | Etiqueta humana (`_usabilidad_accion_label`) |
| `creado_en` | datetime | Índice temporal |

### 12.3 Captura

- Función: `_log_usabilidad_navegacion()` desde `_idle_timeout_guard`.
- Omite: `/static/`, favicon, login, APIs de polling.
- Debounce: `USABILIDAD_DEBOUNCE_SECONDS = 4` para el mismo path GET.
- Fallos de escritura se tragan con `rollback` para no tumbar la UI.

### 12.4 Vista

- Ruta: `GET /dashboard/usabilidad`
- Template: `usabilidad.html`
- Filtros: usuario, fecha, texto libre.
- Agrupación por día en Python (`grupos[].registros` — **no** usar clave `items` en dicts Jinja: colisiona con `dict.items`).

---

## 13. DESPOSTE en mantenimiento

### 13.1 Flag

```python
DESPOSTE_EN_MANTENIMIENTO = True
```

### 13.2 Comportamiento

| Actor | Efecto |
|-------|--------|
| No superadmin | Tarjeta DESPOSTE abre modal: *“Esta área se encuentra en mantenimiento. Estará disponible luego.”* |
| No superadmin vía URL | `entrar_area` rechaza con flash |
| Sesión previa en DESPOSTE | Hook limpia `current_area` y redirige a `/areas` |
| Superadmin | Acceso normal |

UI: `areas.html` + CSS de `.modal-mantenimiento-*` y `.area-card--mantenimiento`.

Para reabrir el área a todos: poner `DESPOSTE_EN_MANTENIMIENTO = False` y reiniciar.

---

## 14. Capa de presentación

### 14.1 Plantillas Jinja

| Template | Rol |
|----------|-----|
| `base.html` | Shell autenticado: nav, tema, área, timer |
| `login.html` / `login_integrado.html` | Auth |
| `areas.html` | Selector de área + modal mantenimiento |
| `dashboard.html` | KPIs + sidebar de módulos |
| `modulo.html` | Motor CRUD genérico |
| `usuarios.html` | Admin de usuarios |
| `usabilidad.html` | Historial de navegación |
| `registro_form.html` | Formularios de ingreso |

### 14.2 Assets

| Archivo | Función |
|---------|---------|
| `static/css/app.css` | Design system (variables, glass, tablas, modales) |
| `static/css/login.css` | Pantalla de login |
| `static/js/app.js` | Tema, progreso nav, utilidades |
| `static/js/login.js` | Validación / vistas login |
| `static/js/dashboard-reminders.js` | Recordatorios en dashboard |
| `static/favicon.svg` | Favicon corporativo |

### 14.3 Tema

- Preferencia en `localStorage` (`lockerbeef-login-theme`).
- Atributo `data-theme="dark|light"` en `<html>`.

---

## 15. Frontend React (Vite)

### 15.1 Propósito

Dashboard SPA alternativo/embebido. Build:

```bat
build_dashboard.bat
```

`vite.config.js`:

- `base: '/static/dashboard/'`
- `outDir: '../app/static/dashboard'`

### 15.2 Código fuente

`frontend/src/`:

- `App.jsx` — router basename `/dashboard`, fetch `/api/dashboard/stats`
- `pages/DashboardHome.jsx`, `components/ModuleCrudPage.jsx`, etc.
- `config/modulesConfig.js` — espejo parcial de módulos (puede desfasarse del backend)

**Nota senior:** la fuente de verdad de módulos y permisos es `MODULOS_CONFIG` en Python. Si React se usa en producción, sincronizar config o consumir endpoints dedicados.

---

## 16. Correo electrónico

`app/utils/email.py`:

- Construye mensaje multipart.
- Soporta TLS (587) y SSL (465).
- Respeta `MAIL_SSL_VERIFY`.
- Usado para reset de contraseña y notificación de cambio.

Sin `MAIL_USERNAME`/`MAIL_PASSWORD` válidos, el envío falla de forma controlada (ver docs de recuperación).

---

## 17. Scripts y base de datos

### 17.1 SQL

- `database/00_crear_base_vacia.sql` — crea schema vacío.
- Scripts de migración / import Desposte / dumps según necesidad.

### 17.2 Scripts Python útiles

| Script | Uso |
|--------|-----|
| `scripts/crear_admin.py` | Primer administrador |
| `scripts/asignar_superadmin.py` | Promover a superadmin |
| `scripts/importar_todo.py` | Carga masiva CSV |
| `scripts/exportar_bd.py` / `restaurar_bd.py` | Mover BD entre equipos |

Arranque típico:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
# Configurar .env + MySQL
python run.py
```

---

## 18. Convenciones senior y guía de extensión

1. **Filtros de área primero.** Toda consulta de negocio debe pasar por los helpers de scope; no confiar solo en el frontend.
2. **Configurar, no copiar.** Nuevos CRUDs → `MODULOS_CONFIG`. Flujos especiales (usuarios, usabilidad) → ruta dedicada + template.
3. **Roles en un solo lugar.** Comparar siempre contra strings normalizados (`.strip().lower()`).
4. **Hooks baratos.** El `before_request` no debe hacer queries pesadas; el log de usabilidad ya tiene debounce y omite APIs.
5. **Jinja y diccionarios.** Evitar claves `items`, `values`, `keys` en dicts pasados a plantillas.
6. **Esquema evolutivo.** Modelo + SQL explícito; no asumir que `create_all()` altera columnas.
7. **Secretos fuera del repo.** `.env` gitignored; documentar nombres de variables, no valores.
8. **DESPOSTE y EXTERNOS son casos especiales.** Antes de “simplificar” filtros, leer `docs/AREAS_TRABAJO_Y_DESPOSTE.md`.
9. **Documentación dual.** Mantener alineados este archivo y `DOCUMENTACION_TECNICA.md` cuando cambien módulos, roles o esquema.
10. **Commits claros.** Mensajes orientados al *por qué* (ej. “bloquea DESPOSTE en mantenimiento salvo superadmin”).

---

### Mapa rápido “dónde tocar qué”

| Necesidad | Archivo(s) |
|-----------|------------|
| Nueva ruta / regla | `app/routes/main.py` |
| Nueva tabla | `app/models/*.py` + `__init__.py` + SQL |
| Nueva pantalla | `app/templates/*.html` + CSS en `app.css` |
| Nuevo módulo CRUD | `MODULOS_CONFIG` |
| Permiso superadmin | `@_superadmin_required` + flag en dashboard |
| SMTP | `.env` + `app/utils/email.py` |
| Favicon | `app/static/favicon.svg` + `includes/favicon.html` |
| Build React | `frontend/` + `build_dashboard.bat` |

---

*Fin del documento — Documentación de código LockerBeef · Versión 1.0*
