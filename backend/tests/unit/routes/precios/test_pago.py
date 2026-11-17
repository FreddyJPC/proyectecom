"""Reglas del método de pago (ADR-017, regla 17)."""
from src.routes.precios.pago import pago_confirmado, pedido_prepagado


def test_solo_la_transferencia_confirmada_es_prepagada():
    assert pedido_prepagado({"metodo_pago": "transferencia", "estado_pago": "confirmado"}) is True
    assert pedido_prepagado({"metodo_pago": "transferencia", "estado_pago": None}) is False
    assert pedido_prepagado({"metodo_pago": "transferencia"}) is False
    assert pedido_prepagado({"metodo_pago": "contraentrega", "estado_pago": "confirmado"}) is False
    assert pedido_prepagado({}) is False


def test_pago_confirmado_exige_transferencia():
    assert pago_confirmado({"metodo_pago": "transferencia", "estado_pago": "confirmado"})
    assert not pago_confirmado({"metodo_pago": "contraentrega", "estado_pago": "confirmado"})
