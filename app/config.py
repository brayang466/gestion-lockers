import os
from datetime import timedelta
from pathlib import Path
from dotenv import load_dotenv

# Cargar .env desde la raíz del proyecto (gestor_lockers/)
_env_path = Path(__file__).resolve().parent.parent / ".env"
# override=False: variables ya definidas en el entorno (p. ej. PORT=5001) no las pisa el .env
load_dotenv(_env_path, override=False, encoding="utf-8")
# Por si se ejecuta desde otra carpeta, cargar también .env del cwd
load_dotenv(override=False, encoding="utf-8")


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or "cambiar-en-produccion"
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)
    MYSQL_USER = os.environ.get("MYSQL_USER", "root")
    MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "")
    MYSQL_HOST = os.environ.get("MYSQL_HOST", "127.0.0.1")
    MYSQL_PORT = os.environ.get("MYSQL_PORT", "3306")
    MYSQL_DATABASE = os.environ.get("MYSQL_DATABASE", "gestor_lockers")
    SQLALCHEMY_DATABASE_URI = (
        f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}"
        f"@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Correo: cuenta desde la que la app ENVÍA (el enlace se envía AL correo que el usuario escribe en el formulario)
    MAIL_SERVER = (
        (os.environ.get("MAIL_SERVER") or os.environ.get("MAIL_HOST") or "").strip()
        or "smtp.gmail.com"
    )
    MAIL_PORT = int(os.environ.get("MAIL_PORT", "587"))
    # Puerto 465 = SSL (SMTPS). Si no se indica, usamos SSL cuando el puerto es 465.
    _use_ssl = (os.environ.get("MAIL_USE_SSL") or "").strip().lower() in ("1", "true", "yes")
    MAIL_USE_SSL = _use_ssl or (os.environ.get("MAIL_PORT", "587").strip() == "465")
    MAIL_USE_TLS = (os.environ.get("MAIL_USE_TLS") or "true").strip().lower() in ("1", "true", "yes")
    MAIL_USERNAME = (os.environ.get("MAIL_USERNAME") or "").strip()
    _pw = os.environ.get("MAIL_PASSWORD") or ""
    # Quitar comillas que a veces deja el .env (ej. MAIL_PASSWORD="abc)" o MAIL_PASSWORD='abc')
    if isinstance(_pw, str) and len(_pw) >= 2 and _pw[0] == _pw[-1] and _pw[0] in ('"', "'"):
        _pw = _pw[1:-1].strip()
    MAIL_PASSWORD = _pw
    MAIL_DEFAULT_SENDER = (
        (os.environ.get("MAIL_DEFAULT_SENDER") or os.environ.get("MAIL_FROM") or "").strip()
        or MAIL_USERNAME
    )
    MAIL_FROM_NAME = (os.environ.get("MAIL_FROM_NAME") or "LockerBeef").strip()
    MAIL_TIMEOUT = int(os.environ.get("MAIL_TIMEOUT", "25"))
    # Si el servidor usa certificado autofirmado, pon MAIL_SSL_VERIFY=false
    MAIL_SSL_VERIFY = (os.environ.get("MAIL_SSL_VERIFY") or "true").strip().lower() not in ("0", "false", "no")
    # Validez del enlace de restablecimiento (minutos). Por defecto 15 min.
    PASSWORD_RESET_EXPIRE_MINUTES = int(os.environ.get("PASSWORD_RESET_EXPIRE_MINUTES", "15"))
    # URL pública de la app (para enlaces en correos). Ej: http://192.168.1.50:5000 o http://gestor.colbeef.com.co
    APP_URL = (os.environ.get("APP_URL") or "").strip()
