"""
Victoria y el módulo de Leads (F2): el historial del cliente en su contexto, las herramientas `clasificar_lead` y
`no_contactar`, el trato de usted, y el escenario «cliente recurrente» de «Probar con Victoria» (cero efectos reales).
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
import responses

from src.integrations.llm.contratos import RespuestaLLM
from src.routes.leads.temperaturas import TEMPERATURAS
from src.routes.productos_bot.simulacion import ClasificacionEnEnsayo
from src.routes.whatsapp import instrucciones as ins
from src.routes.whatsapp.contexto_contacto import formatear_historial
from src.routes.whatsapp.conversation_service import VictoriaConversationService
from src.routes.whatsapp.tools import HERRAMIENTAS_VICTORIA, HerramientasVictoria
from tests.unit.routes.productos_bot.test_simulacion import LLMGuionado, ficha, herramientas, texto, turno
from tests.unit.routes.whatsapp.test_conversation_service import (
    EjecutorHerramientasFalso,
    FakeConversacionRepository,
    FakeLeadRepository,
    FakeMensajeRepository,
    FakeProductoBotRepository,
    LLMProviderFalso,
)

AHORA = datetime(2026, 11, 9, 15, 0, tzinfo=timezone.utc)


def _previo(producto="Audífonos", temperatura="ganado", motivo=None, hace_creado=62, hace_cerrado=60):
    return {
        "producto_nombre": producto, "temperatura": temperatura, "motivo_perdida": motivo,
        "creado_en": AHORA - timedelta(days=hace_creado), "cerrado_en": AHORA - timedelta(days=hace_cerrado) if hace_cerrado is not None else None,
    }


class TestHistorialDelCliente:
    def test_un_cliente_sin_pasado_no_lleva_nada(self):
        assert formatear_historial([], 0, "Ana", AHORA) == ""

    def test_un_cliente_que_ya_compro_se_presenta_como_conocido(self):
        texto_ = formatear_historial([_previo()], 1, "Ana", AHORA)
        assert "Es un cliente conocido: ya compró una vez" in texto_ and "Su nombre es Ana" in texto_
        assert "Audífonos (lo compró hace 2 meses)" in texto_
        assert "escalar_a_humano" in texto_  # lo del pedido anterior lo resuelve una persona

    def test_un_cliente_que_solo_pregunto_antes_no_se_dice_que_compro(self):
        texto_ = formatear_historial([_previo("Zapatos", "perdido", "precio", 120, 110)], 0, None, AHORA)
        assert "todavía no ha comprado" in texto_ and "Zapatos (no se concretó (el precio))" in texto_

    def test_varias_compras_y_un_lead_que_quedo_abierto(self):
        texto_ = formatear_historial([_previo("Reloj", "tibio", None, 3, None)], 3, None, AHORA)
        assert "ya compró 3 veces" in texto_ and "Reloj (quedó tibio, hace 3 días)" in texto_

    def test_solo_cuenta_los_cinco_mas_recientes(self):
        previos = [_previo(f"Producto {i}") for i in range(9)]
        texto_ = formatear_historial(previos, 9, None, AHORA)
        assert "Producto 4" in texto_ and "Producto 5" not in texto_


class _LeadsConHistorial(FakeLeadRepository):
    def __init__(self, resumen=None, falla=False):
        super().__init__()
        self._resumen, self._falla = resumen, falla

    def resumen_del_contacto(self, contacto_id, lead_actual_id):
        if self._falla:
            raise RuntimeError("la base no responde")
        return self._resumen


def _servicio(leads, llm):
    return VictoriaConversationService(
        llm_client=llm, lead_repo=leads,
        conversacion_repo=FakeConversacionRepository({1: {"id": 1, "contacto_id": 4, "telefono": "593987654321", "id_anuncio": None, "contacto_nombre": "Ana"}}),
        mensaje_repo=FakeMensajeRepository(historial=[{"rol": "cliente", "contenido": "Hola"}]),
        producto_repo=FakeProductoBotRepository(), ejecutor_herramientas=EjecutorHerramientasFalso(),
        max_turnos_herramientas=5, max_mensajes_historial=40,
    )


class TestElHistorialLlegaAVictoria:
    def test_el_historial_va_en_lo_que_ya_se_sabe_del_cliente(self):
        llm = LLMProviderFalso([RespuestaLLM(texto="Hola de nuevo", llamadas_herramientas=[], razon_de_parada="fin")])
        _servicio(_LeadsConHistorial({"previos": [_previo()], "compras": 1}), llm).procesar_turno(1, "Hola")
        system = llm.llamadas[0]["system"]
        assert "Historial de este cliente: Es un cliente conocido: ya compró una vez" in system
        assert system.index("Estado actual de este lead") < system.index("Historial de este cliente")

    def test_un_cliente_nuevo_no_ve_historial(self):
        llm = LLMProviderFalso([RespuestaLLM(texto="Hola", llamadas_herramientas=[], razon_de_parada="fin")])
        _servicio(_LeadsConHistorial({"previos": [], "compras": 0}), llm).procesar_turno(1, "Hola")
        assert "Historial de este cliente" not in llm.llamadas[0]["system"]

    def test_si_falla_leer_el_historial_victoria_responde_igual(self):
        llm = LLMProviderFalso([RespuestaLLM(texto="Hola", llamadas_herramientas=[], razon_de_parada="fin")])
        assert _servicio(_LeadsConHistorial(falla=True), llm).procesar_turno(1, "Hola") == "Hola"


class TestHerramientasDeLeads:
    def _herramientas(self, servicio):
        repo = MagicMock()
        repo.obtener_por_id.return_value = {"id": 1, "contacto_id": 9}
        return HerramientasVictoria(
            lead_repo=repo, conversacion_repo=MagicMock(), producto_repo=MagicMock(), pedido_service=MagicMock(),
            telegram_notifier=MagicMock(), stock_checker=MagicMock(), minimo_repo=MagicMock(), mensaje_repo=MagicMock(),
            canales=MagicMock(), leads_servicio=servicio, enviar_fotos=False,
        )

    def _ejecutar(self, h, nombre, entrada):
        return h.ejecutar(nombre, lead_id=1, conversacion_id=1, entrada=entrada, id_llamada="t1").contenido

    def test_ambas_herramientas_se_le_ofrecen_a_victoria_con_sus_valores_validos(self):
        por_nombre = {h.nombre: h for h in HERRAMIENTAS_VICTORIA}
        temperaturas = por_nombre["clasificar_lead"].parametros["properties"]["temperatura"]["enum"]
        assert set(temperaturas) == set(TEMPERATURAS) - {"ganado"}  # «ganado» lo decide la venta, no su juicio
        assert por_nombre["clasificar_lead"].parametros["required"] == ["temperatura", "motivo"]
        assert "no_contactar" in por_nombre and por_nombre["no_contactar"].parametros["required"] == []

    def test_clasificar_pasa_temperatura_y_motivo_y_le_dice_que_no_se_lo_mencione_al_cliente(self):
        servicio = MagicMock()
        servicio.clasificar_por_ia.return_value = {"aplicado": True, "razon": ""}
        respuesta = self._ejecutar(self._herramientas(servicio), "clasificar_lead", {"temperatura": "caliente", "motivo": "Pidió cómo pagar"})
        assert servicio.clasificar_por_ia.call_args.args == (1, "caliente", "Pidió cómo pagar", None)
        assert "No se lo menciones al cliente" in respuesta

    def test_si_no_se_aplica_le_explica_por_que_para_que_siga_con_la_conversacion(self):
        servicio = MagicMock()
        servicio.clasificar_por_ia.return_value = {"aplicado": False, "razon": "El dueño fijó la temperatura de este lead a mano: no se cambia."}
        respuesta = self._ejecutar(self._herramientas(servicio), "clasificar_lead", {"temperatura": "frio", "motivo": "x"})
        assert "El dueño fijó la temperatura" in respuesta and "Sigue con la conversación" in respuesta

    def test_un_fallo_al_clasificar_nunca_interrumpe_la_venta(self):
        servicio = MagicMock()
        servicio.clasificar_por_ia.side_effect = RuntimeError("base caída")
        respuesta = self._ejecutar(self._herramientas(servicio), "clasificar_lead", {"temperatura": "tibio", "motivo": "x"})
        assert "no importa" in respuesta

    def test_no_contactar_marca_al_contacto_y_le_pide_despedirse(self):
        servicio = MagicMock()
        respuesta = self._ejecutar(self._herramientas(servicio), "no_contactar", {"motivo": "No quiere que le escriban"})
        assert servicio.no_contactar_por_ia.call_args.args == (9, "No quiere que le escriban")  # el CONTACTO del lead
        assert "último mensaje" in respuesta

    def test_no_contactar_sin_motivo_y_con_fallo(self):
        servicio = MagicMock()
        self._ejecutar(self._herramientas(servicio), "no_contactar", {})
        assert servicio.no_contactar_por_ia.call_args.args == (9, None)
        servicio.no_contactar_por_ia.side_effect = RuntimeError("x")
        assert "despídete" in self._ejecutar(self._herramientas(servicio), "no_contactar", {})


class TestElTextoDeVictoria:
    def test_trata_de_usted(self):
        assert "Tratas a los clientes de usted" in ins.texto_original()

    def test_sabe_cuando_clasificar_y_cuando_no_contactar(self):
        texto_ = ins.texto_original()
        assert "clasificar_lead" in texto_ and "no_contactar" in texto_
        for definicion in ("caliente:", "tibio:", "frio:", "perdido:"):
            assert definicion in texto_

    def test_la_seccion_de_clasificacion_es_editable_y_atiende_a_clientes_conocidos(self):
        seccion = next(s for s in ins.SECCIONES if s.id == "clasificacion")
        assert seccion.editable and seccion.maximo > 0
        assert "cliente conocido" in " ".join(ins.secciones_originales()["clasificacion"].split())

    def test_el_prompt_completo_sigue_cabiendo_en_el_limite(self):
        assert len(ins.texto_original()) < ins.MAXIMO_TOTAL


class TestProbarConVictoria:
    def test_el_escenario_de_cliente_recurrente_le_muestra_el_historial(self):
        llm = LLMGuionado(texto("¡Hola de nuevo!"))
        from src.routes.productos_bot.simulacion import simular_turno

        simular_turno(producto=ficha(), mensaje="Hola", historial=[], estado=None, desde_anuncio=False, llm=llm, cliente_recurrente=True)
        system = llm.llamadas[0]["system"]
        assert "Historial de este cliente: Es un cliente conocido: ya compró una vez" in system
        assert "Auriculares (pedido de ejemplo)" in system

    def test_por_defecto_el_cliente_de_prueba_no_tiene_historial(self):
        llm = LLMGuionado(texto("Hola"))
        turno(llm)
        assert "Historial de este cliente" not in llm.llamadas[0]["system"]

    @responses.activate
    def test_clasificar_y_no_contactar_se_ven_en_la_bitacora_sin_tocar_la_base(self, monkeypatch):
        monkeypatch.setattr("src.config.database._get_pool", lambda: (_ for _ in ()).throw(AssertionError("La simulación abrió la base")))
        llm = LLMGuionado(
            herramientas(("clasificar_lead", {"temperatura": "caliente", "motivo": "Pidió cómo pagar"}),
                         ("no_contactar", {"motivo": "No quiere más mensajes"})),
            texto("Gracias por su tiempo, que tenga un buen día."),
        )
        r = turno(llm)
        por_nombre = {h["nombre"]: h for h in r.herramientas}
        assert por_nombre["clasificar_lead"]["entrada"]["temperatura"] == "caliente"
        assert "Clasificación registrada" in por_nombre["clasificar_lead"]["resultado"]
        assert "último mensaje" in por_nombre["no_contactar"]["resultado"]
        assert len(responses.calls) == 0

    def test_en_el_ensayo_victoria_tampoco_puede_dar_ganado(self):
        servicio = ClasificacionEnEnsayo()
        assert servicio.clasificar_por_ia(1, "ganado", "x")["aplicado"] is False
        assert servicio.clasificar_por_ia(1, "hirviendo", "x")["aplicado"] is False
        assert servicio.clasificar_por_ia(1, "tibio", "x")["aplicado"] is True and servicio.clasificaciones == [{"temperatura": "tibio", "motivo": "x"}]
        assert servicio.no_contactar_por_ia(1, None) is True and servicio.no_contactar
