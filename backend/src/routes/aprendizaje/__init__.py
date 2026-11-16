from flask import Blueprint

aprendizaje_bp = Blueprint("aprendizaje", __name__, url_prefix="/aprendizaje")

from . import controllers  # noqa: E402,F401
