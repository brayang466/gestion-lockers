"""
Prueba el envío del correo "Has cambiado tu contraseña".
Uso: python scripts/probar_correo.py [correo@destino.com]
Si no pasas correo, se usa el MAIL_USERNAME del .env como destinatario.
"""
import sys
from pathlib import Path

raiz = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(raiz))

from dotenv import load_dotenv
load_dotenv(raiz / ".env", override=True, encoding="utf-8")

from app.config import Config
from app.utils.email import send_password_changed_notification

def main():
    to_email = (sys.argv[1] if len(sys.argv) > 1 else "").strip() or (Config.MAIL_USERNAME or "").strip()
    if not to_email:
        print("Uso: python scripts/probar_correo.py correo@destino.com")
        print("O define MAIL_USERNAME en .env y ejecuta: python scripts/probar_correo.py")
        sys.exit(1)

    # Pasar la config como dict (las claves que usa send_email)
    config = {
        "MAIL_SERVER": Config.MAIL_SERVER,
        "MAIL_PORT": Config.MAIL_PORT,
        "MAIL_USE_TLS": Config.MAIL_USE_TLS,
        "MAIL_USE_SSL": Config.MAIL_USE_SSL,
        "MAIL_USERNAME": Config.MAIL_USERNAME,
        "MAIL_PASSWORD": Config.MAIL_PASSWORD,
        "MAIL_DEFAULT_SENDER": Config.MAIL_DEFAULT_SENDER,
        "MAIL_FROM_NAME": Config.MAIL_FROM_NAME,
        "MAIL_TIMEOUT": getattr(Config, "MAIL_TIMEOUT", 25),
        "MAIL_SSL_VERIFY": getattr(Config, "MAIL_SSL_VERIFY", True),
    }

    print(f"Enviando correo de prueba 'Contraseña actualizada' a: {to_email}")
    ok = send_password_changed_notification(to_email, nombre="Usuario de prueba", config=config)
    if ok:
        print("OK. Revisa la bandeja de entrada (y spam) de", to_email)
    else:
        print("Error al enviar. Revisa la configuración MAIL_* en .env y que el servidor SMTP acepte la conexión.")
        sys.exit(1)

if __name__ == "__main__":
    main()
