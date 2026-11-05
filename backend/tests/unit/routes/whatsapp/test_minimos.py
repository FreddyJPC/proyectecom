from decimal import Decimal

import pytest

from src.routes.whatsapp.minimos import extraer_minimo_rocketfy


class TestExtraerMinimoRocketfy:
    def test_mensaje_real_de_rocketfy(self):
        mensaje = "El importe mínimo del pedido debe ser el del valor de los productos + el costo del envío ($18.47)"
        assert extraer_minimo_rocketfy(mensaje) == Decimal("18.47")

    @pytest.mark.parametrize(
        "mensaje, esperado",
        [
            ("El importe minimo debe ser $20", Decimal("20")),  # sin tilde y sin decimales
            ("EL IMPORTE MÍNIMO DEBE SER $9.5", Decimal("9.5")),  # mayúsculas, un decimal
            ("importe mínimo: $ 12,30", Decimal("12.30")),  # coma decimal y espacio tras el $
            ("Aviso previo.\nEl importe mínimo es\n($33.10)", Decimal("33.10")),  # con saltos de línea
        ],
    )
    def test_variantes_de_formato(self, mensaje, esperado):
        assert extraer_minimo_rocketfy(mensaje) == esperado

    @pytest.mark.parametrize(
        "mensaje",
        ["", None, "Sin cobertura para esta zona", "El pedido costó $18.47 en total", "importe mínimo sin monto"],
    )
    def test_si_no_calza_devuelve_none(self, mensaje):
        assert extraer_minimo_rocketfy(mensaje) is None

    def test_devuelve_decimal_nunca_float(self):
        assert isinstance(extraer_minimo_rocketfy("importe mínimo ($18.47)"), Decimal)
