from flask import Blueprint

conversaciones_bp = Blueprint("conversaciones", __name__, url_prefix="/conversaciones")

from . import controllers  # noqa: E402,F401
