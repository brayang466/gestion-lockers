from datetime import datetime
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from app.config import Config

db = SQLAlchemy()


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
        db.create_all()
    return app
