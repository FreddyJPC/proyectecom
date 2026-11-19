"""
Entrega en agencia de Servientrega, versión 1 (docs/PLAN_ENTREGA_EN_AGENCIA.md §0, entrada 0.0.140), y lo que va con ella:
referencia e indicaciones a Rocketfy, coordenadas de la ubicación compartida, «pasar_a_asesor» con su porqué para
«Aprendizaje de Victoria» y el resumen que confirma el cliente.
"""
import json
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
import responses

from src.config.parametros import parametros
from src.routes.whatsapp.confirmacion import datos_que_faltan, texto_de_confirmacion
from src.routes.whatsapp.ubicacion_compartida import coordenadas_compartidas
from tests.unit.routes.whatsapp.test_tools import (
    BASE_URL,
    LEAD_COMPLETO_CONTRAENTREGA,
    FakeConversacionRepository,
    FakeLeadRepository,
    FakeMinimoRepository,
    FakePedidoRepository,
    FakeProductoBotRepository,
    FakeStockChecker,
    _producto,
)
from src.integrations.rocketfy import RocketfyClient
from src.routes.pedidos.services import PedidoService
from src.routes.whatsapp.tools import HerramientasVictoria
from src.routes.ventas.origen import CIERRE_MANUAL


class LeadsConEntrega(FakeLeadRepository):
    def obtener_por_conversacion(self, conversacion_id):
        return self.leads.get(1)

    def actualizar_referencia(self, lead_id, referencia):
        self.leads.setdefault(lead_id, {})["referencia"] = referencia

    def actualizar_tipo_entrega(self, lead_id, tipo, agencia_indicada):
        lead = self.leads.setdefault(lead_id, {})
        if lead.get("tipo_entrega") != tipo:
            lead.update(tipo_entrega=tipo, agencia_definida_en=None, datos_confirmados_en=None)
            lead["agencia_indicada"] = agencia_indicada if tipo == "agencia" else None
        elif agencia_indicada:
            lead["agencia_indicada"] = agencia_indicada

    def marcar_confirmacion_pedida(self, lead_id):
        self.leads[lead_id]["datos_confirmacion_pedida_en"] = "ahora"


class MensajesFalsos:
    def __init__(self, filas=None):
        self.filas = list(filas or [])

    def obtener_por_conversacion(self, conversacion_id):
        return list(self.filas)


class AprendizajeFalso:
    def __init__(self):
        self.casos = []

    def anotar(self, tipo, origen, motivo, conversacion_id, lead=None, contexto=None):
        self.casos.append({"tipo": tipo, "origen": origen, "motivo": motivo, "conversacion_id": conversacion_id})


@pytest.fixture
def con_parametros(monkeypatch):
    valores = {"entrega.ofrecer_agencia": True, "bot.confirmar_datos_antes_de_cerrar": True}
    real = parametros.valor
    monkeypatch.setattr(parametros, "valor", lambda clave: valores[clave] if clave in valores else real(clave))
    return valores


def _herramientas(leads, mensajes=None, productos=None, aprendizaje=None, telegram=None, conversaciones=None):
    return HerramientasVictoria(
        lead_repo=leads,
        conversacion_repo=conversaciones or FakeConversacionRepository(),
        producto_repo=productos or FakeProductoBotRepository({"DEMO-1": _producto()}),
        pedido_service=PedidoService(client=RocketfyClient(BASE_URL, "vendedor@ejemplo.com", "token"), repo=FakePedidoRepository()),
        telegram_notifier=telegram or MagicMock(),
        stock_checker=FakeStockChecker(),
        minimo_repo=FakeMinimoRepository(),
        mensaje_repo=mensajes or MensajesFalsos(),
        aprendizaje=aprendizaje or AprendizajeFalso(),
        catalogo_ubicaciones=MagicMock(),
    )


def _usar(herramientas, nombre, **entrada):
    return herramientas.ejecutar(nombre, lead_id=1, conversacion_id=1, entrada=entrada, id_llamada="t").contenido


class TestElegirTipoEntrega:
    def test_agencia_guarda_lo_que_dijo_el_cliente_y_prohibe_nombrar_agencias(self):
        leads = LeadsConEntrega({1: dict(LEAD_COMPLETO_CONTRAENTREGA, direccion=None)})
        respuesta = _usar(_herramientas(leads), "elegir_tipo_entrega", tipo="agencia", lo_que_dijo="una por el centro")
        assert leads.leads[1]["tipo_entrega"] == "agencia" and leads.leads[1]["agencia_indicada"] == "una por el centro"
        assert "No nombres" in respuesta and "mostrar_resumen_para_confirmar" in respuesta

    def test_domicilio_pide_direccion_y_referencia(self):
        leads = LeadsConEntrega({1: dict(LEAD_COMPLETO_CONTRAENTREGA, direccion=None)})
        respuesta = _usar(_herramientas(leads), "elegir_tipo_entrega", tipo="domicilio")
        assert leads.leads[1]["tipo_entrega"] == "domicilio" and "referencia" in respuesta

    def test_un_producto_propio_no_usa_la_agencia(self):
        productos = FakeProductoBotRepository({"DEMO-1": _producto(proveedor_cierre=CIERRE_MANUAL)})
        leads = LeadsConEntrega({1: dict(LEAD_COMPLETO_CONTRAENTREGA)})
        respuesta = _usar(_herramientas(leads, productos=productos), "elegir_tipo_entrega", tipo="agencia")
        assert "sus propias opciones de entrega" in respuesta and "tipo_entrega" not in leads.leads[1]

    def test_tipo_invalido_no_guarda(self):
        leads = LeadsConEntrega({1: dict(LEAD_COMPLETO_CONTRAENTREGA)})
        assert "agencia" in _usar(_herramientas(leads), "elegir_tipo_entrega", tipo="oficina")
        assert "tipo_entrega" not in leads.leads[1]


class TestAgenciaPorDefinir:
    def test_con_todo_lo_demas_el_codigo_pasa_a_un_asesor_y_lo_anota(self, con_parametros):
        lead = dict(LEAD_COMPLETO_CONTRAENTREGA, id=1, direccion=None, tipo_entrega="agencia", agencia_indicada="la de Urdesa")
        leads, conversaciones, aprendizaje, telegram = LeadsConEntrega({1: lead}), FakeConversacionRepository(), AprendizajeFalso(), MagicMock()
        h = _herramientas(leads, aprendizaje=aprendizaje, telegram=telegram, conversaciones=conversaciones)

        respuesta = _usar(h, "mostrar_resumen_para_confirmar")

        assert conversaciones.estados[1] == "escalada"
        assert "un asesor le confirma la agencia" in respuesta and "No nombres" in respuesta
        assert aprendizaje.casos[0]["tipo"] == "agencia_por_definir" and aprendizaje.casos[0]["origen"] == "sistema"
        assert "la de Urdesa" in telegram.notificar_escalado.call_args.args[2]
        assert leads.leads[1].get("datos_confirmacion_pedida_en") is None  # no se muestra el resumen sin la agencia

    def test_si_falta_otro_dato_primero_se_pide_ese(self, con_parametros):
        lead = dict(LEAD_COMPLETO_CONTRAENTREGA, nombre_cliente=None, direccion=None, tipo_entrega="agencia")
        conversaciones = FakeConversacionRepository()
        respuesta = _usar(_herramientas(LeadsConEntrega({1: lead}), conversaciones=conversaciones), "mostrar_resumen_para_confirmar")
        assert "el nombre del cliente" in respuesta and 1 not in conversaciones.estados

    def test_cerrar_venta_tampoco_cierra_sin_la_agencia(self, con_parametros):
        lead = dict(LEAD_COMPLETO_CONTRAENTREGA, id=1, tipo_entrega="agencia", datos_confirmados_en="ayer")
        conversaciones = FakeConversacionRepository()
        respuesta = _usar(_herramientas(LeadsConEntrega({1: lead}), conversaciones=conversaciones), "cerrar_venta")
        assert "asesor" in respuesta and conversaciones.estados[1] == "escalada"

    def test_con_la_agencia_definida_muestra_el_resumen_de_retiro(self, con_parametros):
        lead = dict(
            LEAD_COMPLETO_CONTRAENTREGA, direccion="Servientrega Urdesa, Av. Víctor Emilio Estrada 123", tipo_entrega="agencia",
            agencia_definida_en="hoy", referencia="frente al banco",
        )
        respuesta = _usar(_herramientas(LeadsConEntrega({1: lead})), "mostrar_resumen_para_confirmar")
        assert "Retiro en agencia Servientrega: Servientrega Urdesa" in respuesta
        assert "Referencia: frente al banco" in respuesta and "cédula" in respuesta

    def test_con_la_oferta_encendida_pide_elegir_antes_del_resumen(self, con_parametros):
        respuesta = _usar(_herramientas(LeadsConEntrega({1: dict(LEAD_COMPLETO_CONTRAENTREGA)})), "mostrar_resumen_para_confirmar")
        assert "agencia" in respuesta and "elegir_tipo_entrega" in respuesta

    def test_apagada_el_resumen_sale_como_siempre(self, con_parametros):
        con_parametros["entrega.ofrecer_agencia"] = False
        respuesta = _usar(_herramientas(LeadsConEntrega({1: dict(LEAD_COMPLETO_CONTRAENTREGA)})), "mostrar_resumen_para_confirmar")
        assert "• Dirección: Av. Siempre Viva 123" in respuesta


class TestSugerirAgencia:
    def test_al_guardar_la_ciudad_recomienda_la_agencia_una_vez(self, con_parametros, monkeypatch):
        leads = LeadsConEntrega({1: {"producto_sku": "DEMO-1"}})
        h = _herramientas(leads)
        monkeypatch.setattr(h, "_ubicacion_a_guardar", lambda lead_id, c, p: ("GUAYAQUIL", "GUAYAS", "", ""))
        respuesta = _usar(h, "guardar_datos_cliente", canton="Guayaquil")
        assert "agencia de Servientrega" in respuesta and "elegir_tipo_entrega" in respuesta
        leads.leads[1]["tipo_entrega"] = "domicilio"
        assert "agencia" not in _usar(h, "guardar_datos_cliente", canton="Guayaquil")

    def test_guarda_la_referencia(self):
        leads = LeadsConEntrega({1: {}})
        _usar(_herramientas(leads), "guardar_datos_cliente", referencia="  casa verde esquinera ")
        assert leads.leads[1]["referencia"] == "casa verde esquinera"


class TestPedidoARocketfy:
    @responses.activate
    def test_lleva_referencia_indicaciones_y_ubicacion_compartida(self):
        responses.add(responses.POST, f"{BASE_URL}/orders/create", json={"ok": 1, "code": 200, "message": "ok", "id": 7001, "products_stock": []}, status=200)
        responses.add(responses.POST, f"{BASE_URL}/orders/confirm", json={"ok": 1, "code": 200, "message": "ok"}, status=200)
        lead = dict(LEAD_COMPLETO_CONTRAENTREGA, referencia="frente al parque", indicaciones_entrega="Llamar antes")
        mensajes = MensajesFalsos([{"rol": "cliente", "tipo": "ubicacion", "contenido": "[Ubicación compartida — https://maps.google.com/?q=-2.17,-79.92]"}])
        _usar(_herramientas(LeadsConEntrega({1: lead}), mensajes=mensajes), "cerrar_venta")
        enviado = json.loads(responses.calls[0].request.body)
        assert enviado["address_2"] == "frente al parque" and enviado["carrier_observations"] == "Llamar antes"
        assert enviado["latitude"] == -2.17 and enviado["longitude"] == -79.92

    @responses.activate
    def test_retiro_en_agencia_usa_la_indicacion_por_defecto_y_no_manda_la_ubicacion_de_la_casa(self):
        responses.add(responses.POST, f"{BASE_URL}/orders/create", json={"ok": 1, "code": 200, "message": "ok", "id": 7002, "products_stock": []}, status=200)
        responses.add(responses.POST, f"{BASE_URL}/orders/confirm", json={"ok": 1, "code": 200, "message": "ok"}, status=200)
        lead = dict(LEAD_COMPLETO_CONTRAENTREGA, direccion="Servientrega Centro", tipo_entrega="agencia", agencia_definida_en="hoy")
        mensajes = MensajesFalsos([{"rol": "cliente", "tipo": "ubicacion", "contenido": "[Ubicación compartida — https://maps.google.com/?q=-2.1,-79.9]"}])
        _usar(_herramientas(LeadsConEntrega({1: lead}), mensajes=mensajes), "cerrar_venta")
        enviado = json.loads(responses.calls[0].request.body)
        assert enviado["carrier_observations"].startswith("RETIRO EN AGENCIA") and enviado["address"] == "Servientrega Centro"
        assert "latitude" not in enviado


class TestPasarAAsesor:
    def test_anota_el_porque_y_no_dice_humano(self):
        aprendizaje = AprendizajeFalso()
        respuesta = _usar(
            _herramientas(LeadsConEntrega({1: {}}), aprendizaje=aprendizaje), "pasar_a_asesor", tipo="sin_respuesta",
            motivo="Preguntó si sirve para iPhone 12 y la ficha no lo dice",
        )
        assert aprendizaje.casos == [{"tipo": "sin_respuesta", "origen": "victoria", "motivo": "Preguntó si sirve para iPhone 12 y la ficha no lo dice", "conversacion_id": 1}]
        assert "asesor" in respuesta and "humano" not in respuesta.replace("«humana»", "")

    def test_el_nombre_anterior_sigue_funcionando(self):
        conversaciones = FakeConversacionRepository()
        _usar(_herramientas(LeadsConEntrega({1: {}}), conversaciones=conversaciones), "escalar_a_humano", motivo="x")
        assert conversaciones.estados[1] == "escalada"

    def test_verificar_un_pago_no_se_anota_como_falla(self):
        aprendizaje = AprendizajeFalso()
        h = _herramientas(LeadsConEntrega({1: {}}), aprendizaje=aprendizaje)
        h._handle_pasar_a_asesor(1, 1, {"motivo": "VERIFICAR el pago", "_origen": "sistema", "_sin_aprendizaje": True})
        assert aprendizaje.casos == []


class TestConfirmacionYFaltantes:
    def test_con_agencia_la_direccion_no_se_le_pide_al_cliente(self):
        lead = dict(LEAD_COMPLETO_CONTRAENTREGA, direccion=None, tipo_entrega="agencia")
        assert "la dirección" not in datos_que_faltan(lead, None)
        assert "la dirección" in datos_que_faltan(dict(lead, tipo_entrega=None), None)

    def test_el_resumen_de_domicilio_incluye_la_referencia(self):
        texto = texto_de_confirmacion(dict(LEAD_COMPLETO_CONTRAENTREGA, referencia="casa azul", total=Decimal("24.99")))
        assert "• Dirección: Av. Siempre Viva 123" in texto and "• Referencia: casa azul" in texto and "cédula" not in texto


class TestUbicacionCompartida:
    def test_toma_la_ultima_ubicacion_del_cliente(self):
        filas = [
            {"rol": "cliente", "tipo": "ubicacion", "contenido": "[Ubicación compartida — https://maps.google.com/?q=-0.18,-78.47]"},
            {"rol": "cliente", "tipo": "ubicacion", "contenido": "[Ubicación compartida: Casa — https://maps.google.com/?q=-2.19,-79.88]"},
        ]
        assert coordenadas_compartidas(filas) == (-2.19, -79.88)

    def test_un_enlace_pegado_a_mano_o_de_otro_rol_no_cuenta(self):
        assert coordenadas_compartidas([{"rol": "cliente", "tipo": "texto", "contenido": "https://maps.google.com/?q=-2.1,-79.9"}]) is None
        assert coordenadas_compartidas([{"rol": "bot", "tipo": "ubicacion", "contenido": "https://maps.google.com/?q=-2.1,-79.9"}]) is None

    def test_coordenadas_imposibles_se_descartan(self):
        assert coordenadas_compartidas([{"rol": "cliente", "tipo": "ubicacion", "contenido": "https://maps.google.com/?q=95.1,-79.9"}]) is None


class TestNoPreguntaDomicilioOAgencia:
    """Con la recomendación de agencia apagada, Victoria preguntaba sola «¿a domicilio o en agencia?» y lo repetía en cada mensaje
    si el cliente no contestaba (entrada 0.0.157): el envío va a domicilio salvo que el cliente pida retirar o una herramienta lo pida."""

    def test_la_herramienta_y_las_instrucciones_lo_dicen(self):
        from pathlib import Path

        from src.routes.whatsapp.tools import HERRAMIENTAS_VICTORIA as HERRAMIENTAS

        herramienta = next(h for h in HERRAMIENTAS if h.nombre == "elegir_tipo_entrega")
        assert "NO le preguntes tú «¿a domicilio o en agencia?»" in herramienta.descripcion
        prompt = (Path(__file__).parents[4] / "src/routes/whatsapp/victoria_system_prompt.txt").read_text(encoding="utf-8")
        assert "no le preguntes «¿a domicilio o\n  en agencia?»" in prompt
