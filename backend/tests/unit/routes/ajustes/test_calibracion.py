"""
Calibración del envío con los rechazos de Rocketfy por importe mínimo. Mínimo =
valor de los productos + envío (mensaje real del proveedor), así que
envío = mínimo − costo × cantidad.
"""
from decimal import Decimal

from src.routes.ajustes.calibracion import calibrar_envio


def _obs(minimo, costo, cantidad=1):
    return {"minimo": Decimal(minimo), "costo_rocketfy": Decimal(costo), "cantidad": cantidad}


def test_sin_observaciones_no_hay_calibracion():
    assert calibrar_envio([]) is None


def test_envio_es_el_minimo_menos_el_costo_de_los_productos():
    c = calibrar_envio([_obs("18.47", "10.00")])
    assert (c.observaciones, c.minimo, c.mediana, c.maximo) == (1, "8.47", "8.47", "8.47")


def test_con_varias_unidades_se_resta_el_costo_de_todas():
    # 2 unidades a $10 = $20 de productos; mínimo $28.50 -> envío $8.50.
    assert calibrar_envio([_obs("28.50", "10.00", cantidad=2)]).mediana == "8.50"


def test_minimo_mediana_y_maximo_con_cantidad_impar():
    c = calibrar_envio([_obs("17.00", "10.00"), _obs("19.00", "10.00"), _obs("26.00", "10.00")])
    assert (c.observaciones, c.minimo, c.mediana, c.maximo) == (3, "7.00", "9.00", "16.00")


def test_mediana_con_cantidad_par_es_el_promedio_de_los_dos_del_medio():
    c = calibrar_envio([_obs("17.00", "10.00"), _obs("19.00", "10.00")])
    assert c.mediana == "8.00"


def test_descarta_lo_que_no_se_puede_interpretar_o_no_da_un_envio_positivo():
    c = calibrar_envio(
        [
            {"minimo": Decimal("18.47"), "costo_rocketfy": None, "cantidad": 1},  # sin costo
            {"minimo": Decimal("18.47"), "costo_rocketfy": Decimal("10"), "cantidad": None},  # sin cantidad
            {"minimo": Decimal("18.47"), "costo_rocketfy": Decimal("10"), "cantidad": 0},
            _obs("9.00", "10.00"),  # el mínimo no supera al costo: no era un mensaje de envío
            _obs("20.00", "10.00"),  # la única válida: envío $10.00
        ]
    )
    assert (c.observaciones, c.mediana) == (1, "10.00")


def test_si_todo_se_descarta_no_hay_calibracion():
    assert calibrar_envio([_obs("9.00", "10.00")]) is None
