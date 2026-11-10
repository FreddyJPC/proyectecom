"""
Confirmar el pago y que Victoria continúe (pedido de Freddy, pendiente #76): el dueño verifica la transferencia en su banco, pulsa
«Confirmar pago» y Victoria sigue cerrando la venta (en Rocketfy crea el pedido; en un producto propio toma lo que falte y se lo
pasa al dueño). Sin esa confirmación, una transferencia nunca cierra.
"""
from unittest.mock import MagicMock

import pytest
import responses

from src.integrations.llm.contratos import RespuestaLLM
from src.routes.entregas.logica import texto_para_la_ficha
from src.routes.whatsapp.conversation_service import VictoriaConversationService
from src.routes.whatsapp.ficha import formatear_ficha_producto
from src.routes.whatsapp.repository import ConversacionRepository, LeadRepository, MensajeRepository
from tests.helpers_db import borrar_conversaciones_de_prueba
from tests.unit.routes.whatsapp.test_conversation_service import (
    EjecutorHerramientasFalso,
    FakeConversacionRepository,
    FakeLeadRepository,
    FakeProductoBotRepository,
    LLMProviderFalso,
)
from tests.unit.routes.whatsapp.test_imagenes import MensajesConArchivos, _fin
from tests.unit.routes.whatsapp.test_tools import (
    BASE_URL,
    LEAD_COMPLETO_CONTRAENTREGA,
    FakeLeadRepository as FakeLeadsDeHerramientas,
    FakeProductoBotRepository as FakeProductosDeHerramientas,
    _herramientas,
    _producto,
)

AVISO = "[Aviso interno del sistema, no lo escribió el cliente: el dueño verificó su cuenta y CONFIRMÓ el pago]"


def _servicio(mensajes, lead=None):
    llm = LLMProviderFalso([_fin("¡Recibimos su pago!")])
    servicio = VictoriaConversationService(
        llm_client=llm,
        lead_repo=FakeLeadRepository(),
        conversacion_repo=FakeConversacionRepository({1: {"id": 1, "contacto_id": 1, "telefono": "593987654321", "canal": "whatsapp", "id_anuncio": None}}),
        mensaje_repo=mensajes,
        producto_repo=FakeProductoBotRepository(),
        ejecutor_herramientas=EjecutorHerramientasFalso(),
        max_turnos_herramientas=5,
        max_mensajes_historial=40,
    )
    return servicio, llm


class TestElAvisoDelSistemaHaceResponderAVictoria:
    def test_un_aviso_del_sistema_sin_mensajes_nuevos_del_cliente_dispara_un_turno(self):
        mensajes = MensajesConArchivos([
            {"rol": "cliente", "contenido": "ya transferí"},
            {"rol": "bot", "contenido": "Gracias, un asesor lo revisa"},
            {"rol": "sistema", "contenido": AVISO},
        ])
        servicio, llm = _servicio(mensajes)

        texto = servicio.procesar_turno(1, "")

        assert texto == "¡Recibimos su pago!"
        assert llm.llamadas[0]["mensajes"][-1].texto == AVISO
        assert llm.llamadas[0]["mensajes"][-1].rol == "user"

    def test_si_ya_respondio_no_se_vuelve_a_disparar(self):
        mensajes = MensajesConArchivos([{"rol": "sistema", "contenido": AVISO}, {"rol": "bot", "contenido": "¡Recibimos su pago!"}])
        servicio, llm = _servicio(mensajes)
        assert servicio.procesar_turno(1, "") == "" and llm.llamadas == []

    def test_el_cliente_que_escribe_junto_al_aviso_se_responde_con_los_dos(self):
        mensajes = MensajesConArchivos([{"rol": "sistema", "contenido": AVISO}, {"rol": "cliente", "contenido": "¿ya llegó?"}])
        servicio, llm = _servicio(mensajes)
        servicio.procesar_turno(1, "")
        assert llm.llamadas[0]["mensajes"][-1].texto == f"{AVISO}\n¿ya llegó?"

    def test_un_aviso_viejo_queda_en_el_historial_como_contexto(self):
        mensajes = MensajesConArchivos([
            {"rol": "sistema", "contenido": AVISO},
            {"rol": "bot", "contenido": "¡Recibimos su pago!"},
            {"rol": "cliente", "contenido": "gracias"},
        ])
        servicio, llm = _servicio(mensajes)
        servicio.procesar_turno(1, "")
        historial = llm.llamadas[0]["mensajes"][:-1]
        assert [(m.rol, m.texto) for m in historial] == [("user", AVISO), ("assistant", "¡Recibimos su pago!")]

    def test_victoria_sabe_que_el_pago_ya_esta_confirmado(self):
        confirmado = VictoriaConversationService._formatear_contexto_lead({"metodo_pago": "transferencia", "estado_pago": "confirmado"})
        pendiente = VictoriaConversationService._formatear_contexto_lead({"metodo_pago": "transferencia", "estado_pago": "pendiente"})
        assert "CONFIRMADO por el dueño" in confirmado and "CONFIRMADO" not in pendiente
        contraentrega = VictoriaConversationService._formatear_contexto_lead({"metodo_pago": "contraentrega", "estado_pago": "confirmado"})
        assert "CONFIRMADO" not in contraentrega


class TestCerrarVentaPorTransferencia:
    def test_sin_confirmar_el_pago_no_cierra_y_pide_el_comprobante(self):
        lead = dict(LEAD_COMPLETO_CONTRAENTREGA, metodo_pago="transferencia", estado_pago="pendiente")
        leads = FakeLeadsDeHerramientas(leads={1: lead})
        r = _herramientas(lead_repo=leads).ejecutar("cerrar_venta", lead_id=1, conversacion_id=1, entrada={}, id_llamada="t")
        assert "comprobante" in r.contenido.lower() and leads.leads[1].get("estado") != "despachado"

    @responses.activate
    def test_con_el_pago_confirmado_por_el_dueno_si_crea_el_pedido(self):
        responses.add(responses.POST, f"{BASE_URL}/orders/create", json={"ok": 1, "code": 200, "message": "ok", "id": 5101, "products_stock": [{"id": 1, "stock": 10}]}, status=200)
        responses.add(responses.POST, f"{BASE_URL}/orders/confirm", json={"ok": 1, "code": 200, "message": "ok"}, status=200)
        lead = dict(LEAD_COMPLETO_CONTRAENTREGA, metodo_pago="transferencia", estado_pago="confirmado")
        leads = FakeLeadsDeHerramientas(leads={1: lead})
        herramientas = _herramientas(lead_repo=leads, producto_repo=FakeProductosDeHerramientas({"DEMO-1": _producto()}))

        r = herramientas.ejecutar("cerrar_venta", lead_id=1, conversacion_id=1, entrada={}, id_llamada="t")

        assert "pedido confirmado" in r.contenido.lower()
        assert leads.leads[1]["estado"] == "despachado" and leads.leads[1]["id_pedido_rocketfy"] == 5101


TELEFONO = "593900007773"


@pytest.fixture
def lead_real():
    borrar_conversaciones_de_prueba(TELEFONO)
    c = ConversacionRepository.crear(id_externo=TELEFONO, origen="directo")
    lead = LeadRepository.obtener_o_crear(c["id"], contacto_id=c["contacto_id"], telefono=TELEFONO)
    yield c["id"], lead["id"]
    borrar_conversaciones_de_prueba(TELEFONO)


class TestContraLaBaseReal:
    def test_confirmar_el_pago_lo_marca_y_el_lead_deja_de_esperar_pago(self, lead_real):
        _, lead_id = lead_real
        LeadRepository.actualizar_metodo_pago(lead_id, "transferencia")
        assert LeadRepository.obtener_por_id(lead_id)["estado"] == "esperando_pago"
        LeadRepository.marcar_pago_confirmado(lead_id)
        fila = LeadRepository.obtener_por_id(lead_id)
        assert fila["estado_pago"] == "confirmado" and fila["estado"] == "recopilando_datos"

    def test_cambiar_el_metodo_de_pago_vuelve_el_pago_a_pendiente(self, lead_real):
        _, lead_id = lead_real
        LeadRepository.actualizar_metodo_pago(lead_id, "transferencia")
        LeadRepository.marcar_pago_confirmado(lead_id)
        LeadRepository.actualizar_metodo_pago(lead_id, "contraentrega")
        assert LeadRepository.obtener_por_id(lead_id)["estado_pago"] == "pendiente"

    def test_repetir_el_mismo_metodo_no_borra_el_pago_confirmado(self, lead_real):
        _, lead_id = lead_real
        LeadRepository.actualizar_metodo_pago(lead_id, "transferencia")
        LeadRepository.marcar_pago_confirmado(lead_id)
        LeadRepository.actualizar_metodo_pago(lead_id, "transferencia")
        assert LeadRepository.obtener_por_id(lead_id)["estado_pago"] == "confirmado"

    def test_el_aviso_del_sistema_no_es_el_ultimo_mensaje_de_la_lista(self, lead_real):
        conversacion_id, _ = lead_real
        MensajeRepository.crear(conversacion_id=conversacion_id, rol="cliente", contenido="ya transferí", tipo="texto", wamid=None)
        MensajeRepository.crear(conversacion_id=conversacion_id, rol="sistema", contenido=AVISO, tipo="texto", wamid=None)
        fila = next(f for f in ConversacionRepository.listar()["items"] if f["id"] == conversacion_id)
        assert fila["ultimo_mensaje_rol"] == "cliente" and fila["ultimo_mensaje_contenido"] == "ya transferí"


class TestServientrega:
    def test_con_envio_incluido_se_dice_la_transportadora(self):
        assert "Se despacha por Servientrega" in texto_para_la_ficha(True, [], "Servientrega")

    def test_sin_transportadora_el_texto_es_el_de_siempre(self):
        assert texto_para_la_ficha(True, []) == "Envío: INCLUIDO en el precio; no se le cobra nada aparte al cliente."

    def test_en_un_retiro_no_se_menciona_la_transportadora(self):
        opciones = [
            {"nombre": "Envío a todo el país", "tipo": "envio", "costo_cliente": "3.00", "activo": True, "cobertura": []},
            {"nombre": "Retiro en Cuenca", "tipo": "retiro", "costo_cliente": "0", "direccion_retiro": "Av. Loja 1", "activo": True, "cobertura": []},
        ]
        texto = texto_para_la_ficha(False, opciones, "Servientrega")
        envio, retiro = [l for l in texto.splitlines() if l.startswith("- ")]
        assert "se despacha por Servientrega" in envio and "Servientrega" not in retiro
        assert "NO menciones Servientrega" in texto

    def test_la_ficha_toma_la_transportadora_del_parametro(self):
        ficha = formatear_ficha_producto(_producto(envio_incluido=True), entregas=[])
        assert "Se despacha por Servientrega" in ficha
