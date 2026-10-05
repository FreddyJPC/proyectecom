from flask import Blueprint

whatsapp_bp = Blueprint("whatsapp", __name__, url_prefix="/webhooks")

from . import controllers  # noqa: E402,F401
