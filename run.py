# Cargar .env lo más pronto posible (también para el recargador de Flask)
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env", override=True, encoding="utf-8")

from app import create_app
app = create_app()
if __name__ == "__main__":
    _port = int(os.environ.get("PORT", "5000"))
    app.run(debug=True, host="0.0.0.0", port=_port)
