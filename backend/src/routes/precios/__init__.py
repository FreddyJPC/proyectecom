"""Precios: cotización, reglas por producto, regateo y ofertas (ADR-017, docs/PLAN_MODULO_ANUNCIOS.md)."""
from flask import Blueprint

precios_bp = Blueprint("precios", __name__, url_prefix="/precios")

from . import controllers  # noqa: E402,F401
