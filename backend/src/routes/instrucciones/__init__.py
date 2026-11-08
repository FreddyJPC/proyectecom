from flask import Blueprint

instrucciones_bp = Blueprint("instrucciones", __name__, url_prefix="/instrucciones-victoria")

from . import controllers  # noqa: E402,F401
