from flask import Flask
from app.routes.auth_routes import auth_bp
from app.routes.user_routes import user_bp
from app.routes.officer_routes import officer_bp  # ✅ Import officer blueprint
from app.routes.senior_routes import senior_bp

def create_app():
    app = Flask(__name__)
    app.secret_key = 'supersecretkey'  # Replace with environment secret in production

    # ✅ Register all route blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(officer_bp)  # ✅ Register officer blueprint
    app.register_blueprint(senior_bp)

    return app
