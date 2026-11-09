"""La confirmación de datos contra la base real (la desechable de pruebas): cuándo se borra y cuándo no."""
from decimal import Decimal

import pytest

from src.routes.whatsapp.repository import ConversacionRepository, LeadRepository
from tests.helpers_db import borrar_conversaciones_de_prueba

TELEFONO = "593900007772"


@pytest.fixture
def lead():
    borrar_conversaciones_de_prueba(TELEFONO)
    c = ConversacionRepository.crear(id_externo=TELEFONO, origen="directo")
    creado = LeadRepository.obtener_o_crear(c["id"], contacto_id=c["contacto_id"], telefono=TELEFONO)
    yield creado["id"]
    borrar_conversaciones_de_prueba(TELEFONO)


def _confirmar(lead_id):
    LeadRepository.marcar_confirmacion_pedida(lead_id)
    LeadRepository.confirmar_datos(lead_id)
    estado = LeadRepository.obtener_por_id(lead_id)
    assert estado["datos_confirmados_en"] is not None
    return estado


def test_empieza_sin_confirmar(lead):
    estado = LeadRepository.obtener_por_id(lead)
    assert estado["datos_confirmacion_pedida_en"] is None and estado["datos_confirmados_en"] is None


def test_pedir_la_confirmacion_borra_una_anterior(lead):
    _confirmar(lead)
    LeadRepository.marcar_confirmacion_pedida(lead)
    estado = LeadRepository.obtener_por_id(lead)
    assert estado["datos_confirmacion_pedida_en"] is not None and estado["datos_confirmados_en"] is None


def test_cambiar_un_dato_del_cliente_borra_la_confirmacion(lead):
    LeadRepository.actualizar_datos_cliente(lead, nombre_cliente="Ana", direccion="Calle 1", canton="Quito", provincia="Pichincha")
    _confirmar(lead)
    LeadRepository.actualizar_datos_cliente(lead, direccion="Calle 2")
    estado = LeadRepository.obtener_por_id(lead)
    assert estado["datos_confirmados_en"] is None and estado["datos_confirmacion_pedida_en"] is None


def test_repetir_los_mismos_datos_no_la_borra(lead):
    LeadRepository.actualizar_datos_cliente(lead, nombre_cliente="Ana", direccion="Calle 1", canton="Quito", provincia="Pichincha")
    _confirmar(lead)
    LeadRepository.actualizar_datos_cliente(lead, nombre_cliente="Ana", direccion="Calle 1")
    LeadRepository.actualizar_datos_cliente(lead)  # sin datos nuevos
    assert LeadRepository.obtener_por_id(lead)["datos_confirmados_en"] is not None


def test_cambiar_producto_cantidad_pago_o_entrega_la_borra(lead):
    LeadRepository.actualizar_producto(lead, "SKU-1", "Reloj", Decimal("20.00"), cantidad=1)
    LeadRepository.actualizar_metodo_pago(lead, "contraentrega")
    for cambio in (
        lambda: LeadRepository.actualizar_producto(lead, "SKU-1", "Reloj", Decimal("40.00"), cantidad=2),
        lambda: LeadRepository.actualizar_producto(lead, "SKU-2", "Otro", Decimal("40.00"), cantidad=2),
        lambda: LeadRepository.actualizar_metodo_pago(lead, "transferencia"),
        lambda: LeadRepository.actualizar_entrega(lead, None, "Envío express", "envio", Decimal("3.00"), Decimal("43.00")),
    ):
        _confirmar(lead)
        cambio()
        assert LeadRepository.obtener_por_id(lead)["datos_confirmados_en"] is None


def test_volver_a_registrar_lo_mismo_no_la_borra(lead):
    LeadRepository.actualizar_producto(lead, "SKU-1", "Reloj", Decimal("20.00"), cantidad=1)
    LeadRepository.actualizar_metodo_pago(lead, "contraentrega")
    _confirmar(lead)
    LeadRepository.actualizar_producto(lead, "SKU-1", "Reloj", Decimal("20.00"), cantidad=1)
    LeadRepository.actualizar_metodo_pago(lead, "contraentrega")
    assert LeadRepository.obtener_por_id(lead)["datos_confirmados_en"] is not None


def test_registrar_otra_vez_el_producto_borra_la_entrega_y_por_eso_la_confirmacion(lead):
    LeadRepository.actualizar_producto(lead, "SKU-1", "Reloj", Decimal("20.00"), cantidad=1)
    LeadRepository.actualizar_entrega(lead, None, "Envío express", "envio", Decimal("3.00"), Decimal("23.00"))
    _confirmar(lead)
    LeadRepository.actualizar_producto(lead, "SKU-1", "Reloj", Decimal("20.00"), cantidad=1)
    assert LeadRepository.obtener_por_id(lead)["datos_confirmados_en"] is None
