import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from config import Config

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "main.login"

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Ensure upload directory exists
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)

    from app import models  # noqa: F401 (registers tables)
    from app.routes import bp
    app.register_blueprint(bp)

    with app.app_context():
        db.create_all()
        seed_data()

    return app

def seed_data():
    from app.models import Location, Reward
    if Location.query.count() == 0:
        db.session.add_all(
            [Location(name=n) for n in ["Canteen", "Library", "Hostel", "Main Block"]]
        )
    if Reward.query.count() == 0:
        db.session.add_all([
            Reward(name="Canteen coupon", points_cost=100, stock=50),
            Reward(name="Stationery pack", points_cost=60, stock=50),
        ])
    db.session.commit()