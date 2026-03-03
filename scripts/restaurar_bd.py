"""
Restaura la base de datos desde database/gestor_lockers_dump.sql.
Usa las variables de .env (MYSQL_*). Ejecutar en el equipo donde quieres tener
la misma información (después de copiar el .sql y el .env).
"""
import os
import sys
import subprocess
import shutil
from pathlib import Path

# Cargar .env desde la raíz del proyecto
raiz = Path(__file__).resolve().parent.parent
os.chdir(raiz)
try:
    from dotenv import load_dotenv
    load_dotenv(raiz / ".env")
except ImportError:
    pass

def buscar_mysql():
    exe = shutil.which("mysql")
    if exe:
        return exe
    for ruta in [
        raiz / ".." / "xampp" / "mysql" / "bin" / "mysql.exe",
        Path("C:/xampp/mysql/bin/mysql.exe"),
        Path("C:/Program Files/MySQL/MySQL Server 8.0/bin/mysql.exe"),
        Path("C:/Program Files/MySQL/MySQL Server 5.7/bin/mysql.exe"),
    ]:
        p = Path(ruta).resolve()
        if p.exists():
            return str(p)
    return None

def main():
    user = os.environ.get("MYSQL_USER", "root")
    password = os.environ.get("MYSQL_PASSWORD", "")
    host = os.environ.get("MYSQL_HOST", "127.0.0.1")
    port = os.environ.get("MYSQL_PORT", "3306")
    database = os.environ.get("MYSQL_DATABASE", "gestor_lockers")

    dump = raiz / "database" / "gestor_lockers_dump.sql"
    if not dump.exists():
        print(f"No se encontró el archivo de respaldo: {dump}", file=sys.stderr)
        print("Primero exporta la BD en el otro equipo con: python scripts/exportar_bd.py", file=sys.stderr)
        sys.exit(1)

    mysql = buscar_mysql()
    if not mysql:
        print("No se encontró el cliente mysql. Instala MySQL o XAMPP y asegúrate de que esté en el PATH.", file=sys.stderr)
        sys.exit(1)

    env = os.environ.copy()
    if password:
        env["MYSQL_PWD"] = password

    # Crear la base de datos si no existe (el dump suele tener USE db; pero no CREATE DATABASE)
    args_create = [
        mysql, "-u", user, f"-h{host}", f"-P{port}",
        "-e", f"CREATE DATABASE IF NOT EXISTS `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
    ]
    print("Creando base de datos si no existe...")
    r = subprocess.run(args_create, env=env, capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0 and "already exists" not in (r.stderr or ""):
        print(r.stderr or r.stdout, file=sys.stderr)
        sys.exit(1)

    # Importar el dump
    args_import = [
        mysql, "-u", user, f"-h{host}", f"-P{port}", database,
    ]
    print(f"Restaurando desde {dump} ...")
    try:
        with open(dump, "r", encoding="utf-8", errors="replace") as f:
            r = subprocess.run(args_import, env=env, stdin=f, stderr=subprocess.PIPE, text=True, encoding="utf-8")
        if r.returncode != 0:
            print(r.stderr, file=sys.stderr)
            sys.exit(1)
        print("Restauración completada. La base de datos tiene la misma información que en el equipo de origen.")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
