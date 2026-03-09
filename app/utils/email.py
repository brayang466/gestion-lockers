"""Envío de correo vía SMTP (recuperación de contraseña, etc.)."""
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr


def send_email(to_email, subject, body_plain, body_html=None, from_email=None, from_name=None, config=None):
    """
    Envía un correo usando la configuración de la app.
    """
    if config is None:
        from flask import current_app
        config = current_app.config

    server = (config.get("MAIL_SERVER") or "").strip()
    port = config.get("MAIL_PORT", 587)
    use_tls = config.get("MAIL_USE_TLS", True)
    use_ssl = config.get("MAIL_USE_SSL", False)
    username = (config.get("MAIL_USERNAME") or "").strip()
    password = config.get("MAIL_PASSWORD") or ""
    from_email = from_email or (config.get("MAIL_DEFAULT_SENDER") or "").strip() or username
    from_name = from_name or config.get("MAIL_FROM_NAME", "LockerBeef")
    timeout = config.get("MAIL_TIMEOUT", 25)
    ssl_verify = config.get("MAIL_SSL_VERIFY", True)

    if not server or not username or not password:
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = formataddr((from_name, from_email))
    msg["To"] = to_email
    msg.attach(MIMEText(body_plain, "plain", "utf-8"))
    if body_html:
        msg.attach(MIMEText(body_html, "html", "utf-8"))

    try:
        if use_ssl or port == 465:
            context = ssl.create_default_context() if ssl_verify else ssl._create_unverified_context()
            with smtplib.SMTP_SSL(server, port, timeout=timeout, context=context) as smtp:
                smtp.login(username, password)
                smtp.sendmail(from_email, [to_email], msg.as_string())
        else:
            with smtplib.SMTP(server, port, timeout=timeout) as smtp:
                if use_tls:
                    smtp.starttls()
                smtp.login(username, password)
                smtp.sendmail(from_email, [to_email], msg.as_string())
        return True
    except Exception as e:
        try:
            from flask import current_app
            current_app.logger.warning("Error al enviar correo: %s", e)
        except Exception:
            pass
        return False


def send_password_reset_email(to_email, reset_url, config=None):
    """Envía el correo con el enlace para restablecer la contraseña."""
    from flask import current_app
    mins = current_app.config.get("PASSWORD_RESET_EXPIRE_MINUTES", 15)
    mins_text = "1 minuto" if mins == 1 else f"{mins} minutos"
    subject = "Restablecer contraseña — LockerBeef"
    body_plain = f"""Hola,

Has solicitado restablecer tu contraseña en LockerBeef.

Haz clic en el siguiente enlace para elegir una nueva contraseña (válido por {mins_text}):

{reset_url}

Si no solicitaste este cambio, ignora este correo. Tu contraseña no se modificará.

—
LockerBeef
"""
    # HTML adaptable y llamativo (compatible con clientes de correo y móviles)
    body_html = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="X-UA-Compatible" content="IE=edge">
  <title>Restablecer contraseña</title>
  <!--[if mso]>
  <noscript><xml><o:OfficeDocumentSettings><o:PixelsPerInch>96</o:PixelsPerInch></o:OfficeDocumentSettings></xml></noscript>
  <![endif]-->
</head>
<body style="margin:0; padding:0; background-color:#f1f5f9; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; -webkit-font-smoothing: antialiased;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color:#f1f5f9;">
    <tr>
      <td align="center" style="padding: 32px 16px;">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="max-width: 480px; background-color:#ffffff; border-radius: 16px; box-shadow: 0 4px 24px rgba(0,0,0,0.08); overflow: hidden;">
          <!-- Cabecera -->
          <tr>
            <td style="background-color: #059669; background: linear-gradient(135deg, #059669 0%, #047857 100%); padding: 28px 32px; text-align: center;">
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                <tr>
                  <td align="center">
                    <span style="font-size: 26px; font-weight: 700; color: #ffffff; letter-spacing: -0.02em;">LockerBeef</span>
                    <p style="margin: 6px 0 0 0; font-size: 14px; color: rgba(255,255,255,0.9); font-weight: 500;">Recuperación de contraseña</p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <!-- Contenido -->
          <tr>
            <td style="padding: 32px 28px;">
              <p style="margin: 0 0 16px 0; font-size: 18px; font-weight: 600; color: #0f172a;">Hola,</p>
              <p style="margin: 0 0 20px 0; font-size: 15px; line-height: 1.6; color: #475569;">Has solicitado restablecer tu contraseña. Haz clic en el botón de abajo para elegir una nueva. El enlace es válido por <strong>{mins_text}</strong>.</p>
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                <tr>
                  <td align="center" style="padding: 8px 0 24px 0;">
                    <a href="{reset_url}" target="_blank" style="display: inline-block; padding: 14px 32px; background-color: #059669; background: linear-gradient(135deg, #059669 0%, #047857 100%); color: #ffffff; font-size: 16px; font-weight: 600; text-decoration: none; border-radius: 10px; box-shadow: 0 4px 14px rgba(5, 150, 105, 0.4);">Restablecer contraseña</a>
                  </td>
                </tr>
              </table>
              <p style="margin: 0; font-size: 13px; line-height: 1.5; color: #64748b;">Si el botón no funciona, copia y pega este enlace en tu navegador:</p>
              <p style="margin: 8px 0 0 0; font-size: 12px; line-height: 1.5; color: #059669; word-break: break-all;">{reset_url}</p>
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-top: 24px; padding-top: 20px; border-top: 1px solid #e2e8f0;">
                <tr>
                  <td>
                    <p style="margin: 0; font-size: 13px; color: #94a3b8;">Si no solicitaste este cambio, ignora este correo. Tu contraseña no se modificará.</p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <!-- Pie -->
          <tr>
            <td style="padding: 20px 28px; background-color: #f8fafc; text-align: center;">
              <p style="margin: 0; font-size: 12px; color: #94a3b8;">LockerBeef — Control de lockers y dotaciones</p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""
    return send_email(to_email, subject, body_plain, body_html, config=config)


def send_password_changed_notification(to_email, nombre=None, config=None):
    """Notifica al usuario que su contraseña fue cambiada correctamente."""
    nombre = (nombre or "").strip() or "Usuario"
    subject = "Contraseña actualizada — LockerBeef"
    body_plain = f"""Hola {nombre},

Te confirmamos que tu contraseña en LockerBeef ha sido cambiada correctamente.

Si no realizaste este cambio, contacta de inmediato al administrador del sistema.

—
LockerBeef
"""
    body_html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: sans-serif; line-height: 1.5; color: #334155;">
  <p>Hola {nombre},</p>
  <p>Te confirmamos que <strong>tu contraseña en LockerBeef ha sido cambiada correctamente</strong>.</p>
  <p>Si no realizaste este cambio, contacta de inmediato al administrador del sistema.</p>
  <p style="margin-top: 2rem; font-size: 0.85rem; color: #94a3b8;">— LockerBeef</p>
</body>
</html>
"""
    return send_email(to_email, subject, body_plain, body_html, config=config)
