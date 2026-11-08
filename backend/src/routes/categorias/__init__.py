from flask import Blueprint

categorias_bp = Blueprint("categorias", __name__, url_prefix="/categorias-producto")

from . import controllers  # noqa: E402,F401
