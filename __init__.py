from flask import Flask
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


solarEngine = db.create_engine('mysql+pymysql://root:powerhouse@192.168.3.104/solar_project')



def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'Secret!'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:powerhouse@192.168.3.104/solar_project'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)

    from views import views
    from atlantaviews import atlantaviews

    app.register_blueprint(views, url_prefix='/')
    app.register_blueprint(atlantaviews, url_prefix='/atlanta')

    return app


