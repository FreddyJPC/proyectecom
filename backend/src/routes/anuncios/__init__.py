from flask import Blueprint

anuncios_bp = Blueprint("anuncios", __name__, url_prefix="/anuncios")

from . import controllers  # noqa: E402,F401
