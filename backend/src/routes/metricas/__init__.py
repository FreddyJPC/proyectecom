from flask import Blueprint

metricas_bp = Blueprint("metricas", __name__, url_prefix="/metricas")

from . import controllers  # noqa: E402,F401
