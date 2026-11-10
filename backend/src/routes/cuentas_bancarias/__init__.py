from flask import Blueprint

cuentas_bancarias_bp = Blueprint("cuentas_bancarias", __name__, url_prefix="/cuentas-bancarias")

from . import controllers  # noqa: E402,F401
