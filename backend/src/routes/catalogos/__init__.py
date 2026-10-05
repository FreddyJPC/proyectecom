from flask import Blueprint

catalogos_bp = Blueprint("catalogos", __name__, url_prefix="/catalogos")

from . import controllers  # noqa: E402,F401
