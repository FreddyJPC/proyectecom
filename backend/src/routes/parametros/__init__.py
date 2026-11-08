from flask import Blueprint

parametros_bp = Blueprint("parametros", __name__, url_prefix="/parametros")

from . import controllers  # noqa: E402,F401
