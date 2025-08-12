from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()

from .user import User  # noqa: E402,F401
