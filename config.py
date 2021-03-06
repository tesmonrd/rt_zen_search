import os

basedir = os.path.abspath(os.path.dirname(__file__))


class AppConfig(object):
    CSRF_ENABLED = True
    SECRET_KEY = os.environ['SECRET_KEY']
    SQLALCHEMY_DATABASE_URI = os.environ['DATABASE_URL']
    SQLALCHEMY_TRACK_MODIFICATIONS = False


class TestConfig(object):
	TESTING = True
	WTF_CSRF_ENABLED = False
	SECRET_KEY = os.environ['SECRET_KEY']
	SQLALCHEMY_DATABASE_URI = "postgresql:///test_db"
	SQLALCHEMY_TRACK_MODIFICATIONS = False
