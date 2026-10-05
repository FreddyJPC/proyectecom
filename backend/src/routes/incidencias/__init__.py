from flask import Blueprint

incidencias_bp = Blueprint("incidencias", __name__, url_prefix="/incidencias")

from . import controllers  # noqa: E402,F401
