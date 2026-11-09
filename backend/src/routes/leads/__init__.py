from flask import Blueprint

leads_bp = Blueprint("leads", __name__, url_prefix="/leads")
contactos_bp = Blueprint("contactos", __name__, url_prefix="/contactos")

from . import controllers  # noqa: E402,F401
