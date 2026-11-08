"""Ventas cerradas de cualquier proveedor, con precio y costo congelados al vender. ADR-012."""
from flask import Blueprint

ventas_bp = Blueprint("ventas", __name__, url_prefix="/ventas")

from . import controllers  # noqa: E402,F401
