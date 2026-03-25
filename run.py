# Cargar .env lo más pronto posible (también para el recargador de Flask)
import os
from pathlib import Path
from dotenv import load_dotenv

# Si defines PORT en la consola (PORT=5001 python run.py), no debe pisarlo el .env
_port_shell = os.environ.get("PORT")
load_dotenv(Path(__file__).resolve().parent / ".env", override=True, encoding="utf-8")
if _port_shell is not None:
    os.environ["PORT"] = _port_shell

from app import create_app
app = create_app()
if __name__ == "__main__":
    _port = int(os.environ.get("PORT", "5000"))
    app.run(debug=True, host="0.0.0.0", port=_port)
