from flask import Blueprint

ajustes_bp = Blueprint("ajustes", __name__, url_prefix="/ajustes")

from . import controllers  # noqa: E402,F401
