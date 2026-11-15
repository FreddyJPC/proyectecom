from flask import Blueprint

meta_bp = Blueprint("meta", __name__, url_prefix="/meta")

from . import controllers  # noqa: E402,F401
