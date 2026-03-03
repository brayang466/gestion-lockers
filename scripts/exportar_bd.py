"""
Exporta la base de datos MySQL a un archivo .sql (estructura + datos).
Usa las variables de .env (MYSQL_*). El archivo se guarda en database/gestor_lockers_dump.sql
Para usar en otro equipo: copiar ese archivo y ejecutar scripts/restaurar_bd.py
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

def buscar_mysqldump():
    exe = shutil.which("mysqldump")
    if exe:
        return exe
    # Rutas típicas en Windows (XAMPP, MySQL instalado)
    for ruta in [
        raiz / ".." / "xampp" / "mysql" / "bin" / "mysqldump.exe",
        Path("C:/xampp/mysql/bin/mysqldump.exe"),
        Path("C:/Program Files/MySQL/MySQL Server 8.0/bin/mysqldump.exe"),
        Path("C:/Program Files/MySQL/MySQL Server 5.7/bin/mysqldump.exe"),
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

    mysqldump = buscar_mysqldump()
    if not mysqldump:
        print("No se encontró mysqldump. Asegúrate de tener MySQL instalado (XAMPP o MySQL) y en el PATH.", file=sys.stderr)
        sys.exit(1)

    salida = raiz / "database" / "gestor_lockers_dump.sql"
    salida.parent.mkdir(parents=True, exist_ok=True)

    # mysqldump -u user -pPassword -h host -P port --single-transaction --routines dbname
    args = [
        mysqldump,
        "-u", user,
        f"-h{host}",
        f"-P{port}",
        "--single-transaction",
        "--routines",
        "--default-character-set=utf8mb4",
        database,
    ]
    env = os.environ.copy()
    if password:
        env["MYSQL_PWD"] = password  # evita pasar contraseña por línea de comandos

    print(f"Exportando {database} -> {salida}")
    try:
        with open(salida, "w", encoding="utf-8", newline="\n") as f:
            r = subprocess.run(args, env=env, stdout=f, stderr=subprocess.PIPE, text=True, encoding="utf-8")
        if r.returncode != 0:
            print(r.stderr, file=sys.stderr)
            sys.exit(1)
        print(f"Listo. Archivo: {salida}")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
