"""
Contra la base real: lo que el lead y la conversación guardan para el envío por producto y la gestión del dueño
(ADR-012). Autocontenido: teléfono de prueba propio y limpieza antes y después.
"""
from decimal import Decimal

import pytest

from src.config.database import get_connection
from src.routes.whatsapp.repository import ConversacionRepository, LeadRepository

TELEFONO = "593900009999"


def _limpiar():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("delete from conversaciones where telefono = %s", (TELEFONO,))  # cascada: leads


@pytest.fixture(autouse=True)
def limpio():
    _limpiar()
    yield
    _limpiar()


@pytest.fixture
def lead():
    conversacion = ConversacionRepository.crear(telefono=TELEFONO, origen="directo")
    return LeadRepository.obtener_o_crear(conversacion["id"], telefono=TELEFONO)


class TestEntregaEnElLead:
    def test_un_lead_nuevo_no_tiene_entrega_ni_costo_de_envio(self, lead):
        assert lead["entrega_opcion_id"] is None and lead["costo_envio"] == Decimal("0.00") and lead["subtotal"] is None

    def test_registrar_el_producto_guarda_el_subtotal(self, lead):
        LeadRepository.actualizar_producto(lead["id"], "P-1", "Zapatos", Decimal("60.00"), cantidad=2)
        actual = LeadRepository.obtener_por_id(lead["id"])
        assert (actual["total"], actual["subtotal"], actual["cantidad"]) == (Decimal("60.00"), Decimal("60.00"), 2)

    def test_elegir_la_entrega_suma_el_envio_y_conserva_el_subtotal(self, lead):
        LeadRepository.actualizar_producto(lead["id"], "P-1", "Zapatos", Decimal("60.00"), cantidad=2)

        LeadRepository.actualizar_entrega(lead["id"], 7, "Envío en Cuenca", "envio", Decimal("2.00"), Decimal("62.00"))

        actual = LeadRepository.obtener_por_id(lead["id"])
        assert (actual["subtotal"], actual["costo_envio"], actual["total"]) == (Decimal("60.00"), Decimal("2.00"), Decimal("62.00"))
        assert (actual["entrega_opcion_id"], actual["entrega_nombre"], actual["entrega_tipo"]) == (7, "Envío en Cuenca", "envio")

    def test_volver_a_registrar_el_producto_borra_la_entrega_y_el_envio(self, lead):
        LeadRepository.actualizar_producto(lead["id"], "P-1", "Zapatos", Decimal("30.00"))
        LeadRepository.actualizar_entrega(lead["id"], 7, "Envío en Cuenca", "envio", Decimal("2.00"), Decimal("32.00"))

        LeadRepository.actualizar_producto(lead["id"], "P-1", "Zapatos", Decimal("60.00"), cantidad=2)

        actual = LeadRepository.obtener_por_id(lead["id"])
        assert actual["entrega_opcion_id"] is None and actual["entrega_nombre"] is None
        assert (actual["costo_envio"], actual["total"]) == (Decimal("0.00"), Decimal("60.00"))

    def test_borrar_la_entrega_con_valores_nulos(self, lead):
        LeadRepository.actualizar_producto(lead["id"], "P-1", "Zapatos", Decimal("30.00"))
        LeadRepository.actualizar_entrega(lead["id"], 7, "Envío en Cuenca", "envio", Decimal("2.00"), Decimal("32.00"))
        LeadRepository.actualizar_entrega(lead["id"], None, None, None, Decimal("0.00"), Decimal("30.00"))
        actual = LeadRepository.obtener_por_id(lead["id"])
        assert actual["entrega_opcion_id"] is None and actual["total"] == Decimal("30.00")


class TestMetodoDePago:
    def test_en_rocketfy_la_transferencia_deja_el_lead_esperando_el_pago(self, lead):
        LeadRepository.actualizar_metodo_pago(lead["id"], "transferencia")
        assert LeadRepository.obtener_por_id(lead["id"])["estado"] == "esperando_pago"

    def test_en_un_producto_propio_no_espera_comprobante(self, lead):
        LeadRepository.actualizar_metodo_pago(lead["id"], "transferencia", esperar_comprobante=False)
        actual = LeadRepository.obtener_por_id(lead["id"])
        assert actual["metodo_pago"] == "transferencia" and actual["estado"] == "recopilando_datos"

    def test_contraentrega_nunca_cambia_el_estado(self, lead):
        LeadRepository.actualizar_metodo_pago(lead["id"], "contraentrega")
        assert LeadRepository.obtener_por_id(lead["id"])["estado"] == "recopilando_datos"


class TestPedidoPrevio:
    def _con_estado(self, lead, estado):
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("update leads set estado = %s where id = %s", (estado, lead["id"]))

    @pytest.mark.parametrize("estado,esperado", [
        ("despachado", True), ("por_gestionar", True), ("recopilando_datos", False), ("esperando_pago", False),
    ])
    def test_solo_cuentan_los_pedidos_ya_cerrados(self, lead, estado, esperado):
        self._con_estado(lead, estado)
        assert LeadRepository.existe_pedido_previo_por_telefono(TELEFONO) is esperado


class TestConversacionEnGestion:
    def test_marcar_en_gestion_limpia_vista_en_y_se_cuenta_aparte(self):
        conversacion = ConversacionRepository.crear(telefono=TELEFONO, origen="directo")
        ConversacionRepository.marcar_vista(conversacion["id"])
        antes = ConversacionRepository.contar_por_filtro_rapido()

        ConversacionRepository.marcar_en_gestion(conversacion["id"])

        actual = ConversacionRepository.obtener_por_id(conversacion["id"])
        assert actual["estado"] == "en_gestion" and actual["vista_en"] is None
        despues = ConversacionRepository.contar_por_filtro_rapido()
        assert despues["en_gestion"] == antes["en_gestion"] + 1
        assert despues["escaladas"] == antes["escaladas"]

    def test_se_puede_filtrar_la_lista_por_en_gestion(self):
        conversacion = ConversacionRepository.crear(telefono=TELEFONO, origen="directo")
        ConversacionRepository.marcar_en_gestion(conversacion["id"])
        lista = ConversacionRepository.listar(estado="en_gestion", origen=None, q=None, page=1, page_size=50)
        assert conversacion["id"] in [c["id"] for c in lista["items"]]
