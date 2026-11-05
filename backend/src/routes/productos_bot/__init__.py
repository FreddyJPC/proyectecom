from flask import Blueprint

productos_bot_bp = Blueprint("productos_bot", __name__, url_prefix="/productos-bot")

from . import controllers  # noqa: E402,F401
