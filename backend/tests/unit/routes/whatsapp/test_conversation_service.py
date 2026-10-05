"""
Tests del loop de herramientas de VictoriaConversationService (Fase 3.2,
Tarea 6). Usan un LLMProvider falso propio -- una clase de prueba que
implementa la interfaz LLMProvider y devuelve una secuencia guionada de
RespuestaLLM -- sin mockear HTTP ni nada de Anthropic. Ninguno de estos
tests importa `anthropic`.
"""
from src.integrations.llm.contratos import (
    LlamadaHerramienta,
    LLMProvider,
    ResultadoHerramienta,
    RespuestaLLM,
)
from src.routes.whatsapp.conversation_service import VictoriaConversationService


class LLMProviderFalso(LLMProvider):
    def __init__(self, respuestas):
        self._respuestas = list(respuestas)
        self.llamadas = []

    def generar_respuesta(self, system, mensajes, herramientas, max_tokens=1024):
        self.llamadas.append({"system": system, "mensajes": list(mensajes), "herramientas": herramientas})
        return self._respuestas.pop(0)


class EjecutorHerramientasFalso:
    def __init__(self):
        self.llamadas = []

    def ejecutar(self, nombre, lead_id, conversacion_id, entrada, id_llamada):
        self.llamadas.append(
            {"nombre": nombre, "lead_id": lead_id, "conversacion_id": conversacion_id, "entrada": entrada}
        )
        return ResultadoHerramienta(id_llamada=id_llamada, contenido=f"resultado de {nombre}")


class FakeConversacionRepository:
    def __init__(self, conversaciones):
        self._tabla = conversaciones

    def obtener_por_id(self, conversacion_id):
        return self._tabla.get(conversacion_id)


class FakeLeadRepository:
    def __init__(self, lead=None):
        self._lead = lead or {"id": 1}

    def obtener_o_crear(self, conversacion_id, telefono):
        return self._lead


class FakeMensajeRepository:
    def __init__(self, historial=None):
        self._historial = historial or []
        self.guardados = []

    def obtener_por_conversacion(self, conversacion_id):
        return self._historial

    def crear(self, conversacion_id, rol, contenido, tipo="texto", wamid=None):
        fila = {"conversacion_id": conversacion_id, "rol": rol, "contenido": contenido, "tipo": tipo, "wamid": wamid}
        self.guardados.append(fila)
        return fila


class FakeProductoBotRepository:
    def obtener_por_sku(self, sku):
        return None

    def obtener_por_id_anuncio(self, id_anuncio):
        return None

    def listar_activos(self):
        return []


def _servicio(llm, historial_cliente, max_turnos=5, ejecutor=None):
    return VictoriaConversationService(
        llm_client=llm,
        lead_repo=FakeLeadRepository(),
        conversacion_repo=FakeConversacionRepository({1: {"id": 1, "telefono": "593987654321", "id_anuncio": None}}),
        mensaje_repo=FakeMensajeRepository(historial=[{"rol": "cliente", "contenido": historial_cliente}]),
        producto_repo=FakeProductoBotRepository(),
        ejecutor_herramientas=ejecutor or EjecutorHerramientasFalso(),
        max_turnos_herramientas=max_turnos,
        max_mensajes_historial=40,
    )


class TestLoopDeHerramientas:
    def test_necesita_herramientas_seguido_de_fin_termina_correctamente(self):
        llm = LLMProviderFalso([
            RespuestaLLM(
                texto="Un momento...",
                llamadas_herramientas=[
                    LlamadaHerramienta(
                        id="toolu_1",
                        nombre="registrar_producto",
                        entrada={"producto_sku": "X", "producto_nombre": "Y", "total": 10},
                    )
                ],
                razon_de_parada="necesita_herramientas",
            ),
            RespuestaLLM(texto="¡Listo! Ya registré tu producto.", llamadas_herramientas=[], razon_de_parada="fin"),
        ])
        ejecutor = EjecutorHerramientasFalso()
        servicio = _servicio(llm, "Quiero el producto X", ejecutor=ejecutor)

        resultado = servicio.procesar_turno(conversacion_id=1, mensaje_cliente="Quiero el producto X")

        assert resultado == "Un momento...¡Listo! Ya registré tu producto."
        assert len(llm.llamadas) == 2
        assert len(ejecutor.llamadas) == 1
        assert ejecutor.llamadas[0]["nombre"] == "registrar_producto"
        assert ejecutor.llamadas[0]["lead_id"] == 1
        assert ejecutor.llamadas[0]["conversacion_id"] == 1

    def test_guarda_el_texto_final_en_mensajes_con_rol_bot(self):
        llm = LLMProviderFalso([RespuestaLLM(texto="Hola, ¿en qué te ayudo?", llamadas_herramientas=[], razon_de_parada="fin")])
        servicio = VictoriaConversationService(
            llm_client=llm,
            lead_repo=FakeLeadRepository(),
            conversacion_repo=FakeConversacionRepository({1: {"id": 1, "telefono": "593987654321", "id_anuncio": None}}),
            mensaje_repo=(mensajes := FakeMensajeRepository(historial=[{"rol": "cliente", "contenido": "Hola"}])),
            producto_repo=FakeProductoBotRepository(),
            ejecutor_herramientas=EjecutorHerramientasFalso(),
            max_turnos_herramientas=5,
            max_mensajes_historial=40,
        )

        resultado = servicio.procesar_turno(conversacion_id=1, mensaje_cliente="Hola")

        assert mensajes.guardados[-1]["rol"] == "bot"
        assert mensajes.guardados[-1]["contenido"] == resultado

    def test_escalar_a_humano_permite_una_iteracion_mas_para_la_despedida(self):
        llm = LLMProviderFalso([
            RespuestaLLM(
                texto="Ya te conecto con un asesor.",
                llamadas_herramientas=[
                    LlamadaHerramienta(id="toolu_1", nombre="escalar_a_humano", entrada={"motivo": "pidió hablar con alguien"})
                ],
                razon_de_parada="necesita_herramientas",
            ),
            RespuestaLLM(texto=" ¡Que tengas un buen día!", llamadas_herramientas=[], razon_de_parada="fin"),
        ])
        ejecutor = EjecutorHerramientasFalso()
        servicio = _servicio(llm, "Quiero hablar con una persona", ejecutor=ejecutor)

        resultado = servicio.procesar_turno(conversacion_id=1, mensaje_cliente="Quiero hablar con una persona")

        assert resultado == "Ya te conecto con un asesor. ¡Que tengas un buen día!"
        assert len(llm.llamadas) == 2
        assert len(ejecutor.llamadas) == 1
        assert ejecutor.llamadas[0]["nombre"] == "escalar_a_humano"

    def test_escalar_a_humano_no_permite_mas_de_una_iteracion_extra(self):
        llm = LLMProviderFalso([
            RespuestaLLM(
                texto="",
                llamadas_herramientas=[
                    LlamadaHerramienta(id="toolu_1", nombre="escalar_a_humano", entrada={"motivo": "x"})
                ],
                razon_de_parada="necesita_herramientas",
            ),
            RespuestaLLM(
                texto="",
                llamadas_herramientas=[
                    LlamadaHerramienta(id="toolu_2", nombre="guardar_datos_cliente", entrada={})
                ],
                razon_de_parada="necesita_herramientas",
            ),
        ])
        ejecutor = EjecutorHerramientasFalso()
        servicio = _servicio(llm, "hola", max_turnos=5, ejecutor=ejecutor)

        servicio.procesar_turno(conversacion_id=1, mensaje_cliente="hola")

        # Solo 2 llamadas al LLM: la que escala + la despedida -- nunca se
        # ejecuta la segunda herramienta que el modelo pidió después.
        assert len(llm.llamadas) == 2

    def test_limite_de_turnos_escala_automaticamente(self):
        respuestas = [
            RespuestaLLM(
                texto="",
                llamadas_herramientas=[
                    LlamadaHerramienta(id=f"toolu_{i}", nombre="guardar_datos_cliente", entrada={})
                ],
                razon_de_parada="necesita_herramientas",
            )
            for i in range(3)
        ]
        llm = LLMProviderFalso(respuestas)
        ejecutor = EjecutorHerramientasFalso()
        servicio = _servicio(llm, "hola", max_turnos=3, ejecutor=ejecutor)

        resultado = servicio.procesar_turno(conversacion_id=1, mensaje_cliente="hola")

        assert "asesor" in resultado.lower()
        assert len(llm.llamadas) == 3
        assert any(l["nombre"] == "escalar_a_humano" for l in ejecutor.llamadas)
