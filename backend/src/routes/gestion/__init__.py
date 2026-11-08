from flask import Blueprint

gestion_bp = Blueprint("gestion", __name__, url_prefix="/gestion")

from . import controllers  # noqa: E402,F401
