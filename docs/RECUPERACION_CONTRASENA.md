# Recuperación de contraseña por correo

El usuario puede solicitar restablecer su contraseña desde «¿Olvidaste tu contraseña?» en la pantalla de login. Se le envía un correo con un enlace válido por **15 minutos** (configurable vía PASSWORD_RESET_EXPIRE_MINUTES) para elegir una nueva contraseña.

## ¿Quién envía y quién recibe?

- **Remitente (De:):** La cuenta que configuras en `.env` con `MAIL_USERNAME` / `MAIL_DEFAULT_SENDER`. Es la cuenta desde la que la aplicación envía el correo (ej. `no-responder@tuempresa.com`).
- **Destinatario (Para:):** Siempre es el correo que el usuario escribe en el formulario «Restablecer contraseña», es decir, su propio correo (el que tiene registrado en la app). No se configura en `.env`; la app lo toma del formulario y de la base de datos.

No hace falta ningún campo tipo «correo donde se envía el código»: el código/enlace se envía al mismo usuario que pidió restablecer la contraseña.

## Configuración en `.env`

Añade las variables de correo. Puedes usar `MAIL_SERVER` o `MAIL_HOST`, y `MAIL_DEFAULT_SENDER` o `MAIL_FROM`:

```env
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=tu-correo@gmail.com
MAIL_PASSWORD=tu-contraseña-de-aplicacion
MAIL_DEFAULT_SENDER=tu-correo@gmail.com
MAIL_FROM_NAME=LockerBeef
PASSWORD_RESET_EXPIRE_HOURS=1
```

### Gmail

1. Activa la **verificación en dos pasos** en tu cuenta de Google.
2. Ve a **Cuenta de Google → Seguridad → Contraseñas de aplicaciones**.
3. Genera una contraseña de aplicación para «Correo» y usa ese valor en `MAIL_PASSWORD` (no tu contraseña normal de Gmail).

### Outlook / Office 365

- `MAIL_SERVER=smtp.office365.com`, `MAIL_PORT=587`, `MAIL_USE_TLS=true`.
- Usa tu correo y contraseña (o contraseña de aplicación si está habilitada).

### Otros proveedores

Cualquier SMTP con TLS (puerto 587) suele funcionar. Ajusta `MAIL_SERVER`, `MAIL_PORT` y `MAIL_USE_TLS` según la documentación del proveedor.

## Si no configuras correo

Si no defines `MAIL_USERNAME` y `MAIL_PASSWORD`, al solicitar restablecer contraseña se mostrará un mensaje indicando que el envío no está configurado. En entornos de desarrollo, la app puede mostrar el enlace de restablecimiento en pantalla para probar sin enviar el correo.
