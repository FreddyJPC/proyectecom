from flask import Blueprint

pedidos_bp = Blueprint("pedidos", __name__, url_prefix="/pedidos")

from . import controllers  # noqa: E402,F401
