# Siguiente: Login, Dashboard y Módulos

Orden sugerido para seguir con el funcionamiento de la app.

## 1. Login

- Ruta `/login`: formulario con **email** y **contraseña**.
- Verificar con el usuario en tabla `usuarios` (campo `password_hash` con `werkzeug.check_password_hash`).
- Si es correcto: guardar en sesión el `id` (o email) del usuario y redirigir a `/` o `/dashboard`.
- Proteger rutas: decorador o before_request que compruebe sesión; si no hay sesión, redirigir a `/login`.
- Ruta `/logout`: borrar sesión y redirigir a `/login`.

## 2. Dashboard

- Ruta `/` o `/dashboard`: página principal tras el login.
- Mostrar resumen útil:
  - Total lockers (base_lockers), cuántos disponibles.
  - Total dotaciones disponibles.
  - Personal (registro_personal o personal_presupuestado).
  - Últimas asignaciones o últimos retiros (opcional).
- En el layout: menú o navbar con enlaces a los módulos.

## 3. Módulos (menú)

En el menú se pueden agrupar así:

| Módulo | Contenido |
|--------|-----------|
| Base de lockers | Listar / buscar base_lockers. Opción de editar estado, área, etc. |
| Locker disponibles | Listar locker_disponibles (o vista de base_lockers con estado disponible). |
| Base de dotaciones | Listar base_dotaciones. |
| Dotaciones disponibles | Listar dotaciones_disponibles. |
| Registro de personal | Listar y alta/edición de registro_personal. |
| Personal presupuestado | Listar personal_presupuestado (por área, aprobados, contratados, por contratar). |
| Asignaciones | Listar y alta de registro_asignaciones (elegir operario, locker, dotación, fechas). |
| Historial de retiros | Listar historial_retiros. |
| Ingreso de lockers | Formulario para dar de alta nuevos lockers (ver FORMULARIOS_INGRESO.md). |
| Ingreso de dotación | Formulario para registrar nuevas dotaciones. |

## 4. Tecnología sugerida

- **Plantillas:** seguir con Jinja2 (ya en uso).
- **Sesión:** `session` de Flask (configurar `SECRET_KEY` en `.env`).
- **Formularios:** HTML con `<form>` y validación en el backend; opcional: Flask-WTF para validación y CSRF.
- **Estilos:** mantener o ampliar el CSS en `base.html`; opcional: Bootstrap o similar para el dashboard y tablas.

Cuando quieras, se puede implementar primero el **login** y después el **dashboard** con el menú a estos módulos.
