from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from openrouteservice import client

db = SQLAlchemy()

ors_API_key = '5b3ce3597851110001cf624819743d9af4454a189cb1389e6f22df78'
base_url = 'http://192.168.3.104:8080/ors'
ors_client = client.Client(key=ors_API_key, base_url=base_url)


solarEngine = db.create_engine('mysql+pymysql://root:powerhouse@192.168.3.45/solar_project')


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'Secret!'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:powerhouse@192.168.3.45/solar_project'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)

    from views import views
    from atlantaviews import atlantaviews
    from texasviews import texasviews
    from uberviews import uberviews
    from webviews import webviews

    app.register_blueprint(views, url_prefix='/views')
    app.register_blueprint(atlantaviews, url_prefix='/atlanta')
    app.register_blueprint(texasviews, url_prefix='/texas')
    app.register_blueprint(uberviews, url_prefix='/')
    app.register_blueprint(webviews, url_prefix='/web')

    return app


