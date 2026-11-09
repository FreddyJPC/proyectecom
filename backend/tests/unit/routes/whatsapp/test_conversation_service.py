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

    def obtener_o_crear(self, conversacion_id, contacto_id, telefono, dias_atribucion=30):
        return self._lead

    def resumen_del_contacto(self, contacto_id, lead_actual_id):
        return {"previos": [], "compras": 0}


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
        conversacion_repo=FakeConversacionRepository({1: {"id": 1, "contacto_id": 1, "telefono": "593987654321", "id_anuncio": None}}),
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

        assert resultado == "Un momento...\n\n¡Listo! Ya registré tu producto."
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
            conversacion_repo=FakeConversacionRepository({1: {"id": 1, "contacto_id": 1, "telefono": "593987654321", "id_anuncio": None}}),
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

        assert resultado == "Ya te conecto con un asesor.\n\n¡Que tengas un buen día!"
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


class CatalogoFalso:
    """Productos de ventas con el flag `activo`, como los devuelve el repositorio real."""

    def __init__(self, productos):
        self._por_sku = {p["sku"]: p for p in productos}
        self._por_anuncio = {}

    def vincular(self, id_anuncio, sku):
        self._por_anuncio[id_anuncio] = self._por_sku[sku]

    def obtener_por_sku(self, sku):
        return self._por_sku.get(sku)

    def obtener_por_id_anuncio(self, id_anuncio):
        return self._por_anuncio.get(id_anuncio)

    def listar_activos(self):
        return [p for p in self._por_sku.values() if p["activo"]]


def _producto(sku, nombre, activo=True, descripcion="Descripción de venta."):
    return {
        "sku": sku,
        "nombre": nombre,
        "descripcion": descripcion,
        "precio": "24.99",
        "tiempo_entrega": "2 a 4 días hábiles",
        "metodos_pago_aceptados": "contraentrega",
        "max_unidades_por_pedido": 1,
        "activo": activo,
    }


def _system_prompt_del_turno(catalogo, lead, id_anuncio=None):
    llm = LLMProviderFalso([RespuestaLLM(texto="Hola", llamadas_herramientas=[], razon_de_parada="fin")])
    servicio = VictoriaConversationService(
        llm_client=llm,
        lead_repo=FakeLeadRepository(lead),
        conversacion_repo=FakeConversacionRepository({1: {"id": 1, "contacto_id": 1, "telefono": "593987654321", "id_anuncio": id_anuncio}}),
        mensaje_repo=FakeMensajeRepository(historial=[{"rol": "cliente", "contenido": "Hola"}]),
        producto_repo=catalogo,
        ejecutor_herramientas=EjecutorHerramientasFalso(),
        max_turnos_herramientas=5,
        max_mensajes_historial=40,
    )
    servicio.procesar_turno(conversacion_id=1, mensaje_cliente="Hola")
    return llm.llamadas[0]["system"], llm.llamadas[0]["herramientas"]


class TestContextoDeProducto:
    """Hueco H6 (pausar de verdad) y H7 (ficha bajo demanda) del plan de gestión de productos."""

    def test_producto_activo_del_lead_muestra_la_ficha_completa_con_sku(self):
        catalogo = CatalogoFalso([_producto("DEMO-1", "Producto Demo", descripcion="Descripción única de prueba.")])

        system, _ = _system_prompt_del_turno(catalogo, {"id": 1, "producto_sku": "DEMO-1"})

        assert "SKU: DEMO-1" in system
        assert "Descripción única de prueba." in system
        assert "AVISO" not in system

    def test_producto_pausado_del_lead_no_muestra_la_ficha_y_avisa_a_victoria(self):
        catalogo = CatalogoFalso(
            [
                _producto("VIEJO", "Producto Viejo", activo=False, descripcion="Texto del producto pausado."),
                _producto("NUEVO", "Producto Nuevo"),
            ]
        )
        lead = {"id": 1, "producto_sku": "VIEJO", "producto_nombre": "Producto Viejo"}

        system, _ = _system_prompt_del_turno(catalogo, lead)

        assert "Texto del producto pausado." not in system
        assert "AVISO: el producto que el cliente había elegido (Producto Viejo) ya no está disponible" in system
        assert "- Producto Nuevo (SKU NUEVO): $24.99" in system

    def test_anuncio_vinculado_a_un_producto_pausado_se_ignora(self):
        catalogo = CatalogoFalso([_producto("VIEJO", "Producto Viejo", activo=False, descripcion="Texto del pausado.")])
        catalogo.vincular("AD-1", "VIEJO")

        system, _ = _system_prompt_del_turno(catalogo, {"id": 1}, id_anuncio="AD-1")

        assert "Texto del pausado." not in system
        assert "AVISO" not in system  # el lead nunca había elegido ese producto

    def test_anuncio_vinculado_a_un_producto_activo_muestra_su_ficha(self):
        catalogo = CatalogoFalso([_producto("DEMO-1", "Producto Demo", descripcion="Ficha del anuncio.")])
        catalogo.vincular("AD-1", "DEMO-1")

        system, _ = _system_prompt_del_turno(catalogo, {"id": 1}, id_anuncio="AD-1")

        assert "Ficha del anuncio." in system

    def test_sin_producto_identificado_la_lista_indica_usar_ver_ficha_producto(self):
        catalogo = CatalogoFalso([_producto("A", "Producto A"), _producto("B", "Producto B")])

        system, _ = _system_prompt_del_turno(catalogo, {"id": 1})

        assert "- Producto A (SKU A): $24.99" in system
        assert "- Producto B (SKU B): $24.99" in system
        assert "ver_ficha_producto" in system

    def test_victoria_recibe_la_herramienta_nueva_y_ya_no_envia_el_total(self):
        _, herramientas = _system_prompt_del_turno(CatalogoFalso([]), {"id": 1})

        por_nombre = {h.nombre: h for h in herramientas}
        assert "ver_ficha_producto" in por_nombre
        registrar = por_nombre["registrar_producto"].parametros
        assert "total" not in registrar["properties"]
        assert "cantidad" in registrar["properties"]
        assert registrar["required"] == ["producto_sku", "producto_nombre"]


class TestHerramientasOfrecidasAlModelo:
    """Fase G2: la foto solo se ofrece si BOT_ENVIAR_FOTOS está encendido."""

    @staticmethod
    def _nombres_ofrecidos(monkeypatch, valor):
        if valor is None:
            monkeypatch.delenv("BOT_ENVIAR_FOTOS", raising=False)
        else:
            monkeypatch.setenv("BOT_ENVIAR_FOTOS", valor)
        llm = LLMProviderFalso([RespuestaLLM(texto="Hola", llamadas_herramientas=[], razon_de_parada="fin")])
        _servicio(llm, "Hola").procesar_turno(conversacion_id=1, mensaje_cliente="Hola")
        return [h.nombre for h in llm.llamadas[0]["herramientas"]]

    def test_por_defecto_esta_apagada_y_el_resto_de_herramientas_sigue_igual(self, monkeypatch):
        nombres = self._nombres_ofrecidos(monkeypatch, None)
        assert "enviar_foto_producto" not in nombres and "cerrar_venta" in nombres and "escalar_a_humano" in nombres

    def test_encendida_se_ofrece_al_final_de_la_lista(self, monkeypatch):
        nombres = self._nombres_ofrecidos(monkeypatch, "true")
        assert nombres[-1] == "enviar_foto_producto" and "cerrar_venta" in nombres

    def test_el_parametro_manda_sobre_la_variable_de_entorno(self, monkeypatch):
        monkeypatch.delenv("BOT_ENVIAR_FOTOS", raising=False)
        llm = LLMProviderFalso([RespuestaLLM(texto="Hola", llamadas_herramientas=[], razon_de_parada="fin")])
        servicio = VictoriaConversationService(
            llm_client=llm, lead_repo=FakeLeadRepository(),
            conversacion_repo=FakeConversacionRepository({1: {"id": 1, "contacto_id": 1, "telefono": "593987654321", "id_anuncio": None}}),
            mensaje_repo=FakeMensajeRepository(historial=[{"rol": "cliente", "contenido": "Hola"}]),
            producto_repo=FakeProductoBotRepository(), ejecutor_herramientas=EjecutorHerramientasFalso(),
            max_turnos_herramientas=5, max_mensajes_historial=40, enviar_fotos=True,
        )
        servicio.procesar_turno(conversacion_id=1, mensaje_cliente="Hola")
        assert "enviar_foto_producto" in [h.nombre for h in llm.llamadas[0]["herramientas"]]


def _servicio_sin_fijar(llm, historial):
    """Como en producción: el servicio NO recibe memoria, vueltas ni fotos; los lee de los parámetros."""
    return VictoriaConversationService(
        llm_client=llm,
        lead_repo=FakeLeadRepository(),
        conversacion_repo=FakeConversacionRepository({1: {"id": 1, "contacto_id": 1, "telefono": "593987654321", "id_anuncio": None}}),
        mensaje_repo=FakeMensajeRepository(historial=historial),
        producto_repo=FakeProductoBotRepository(),
        ejecutor_herramientas=EjecutorHerramientasFalso(),
    )


def _con_parametros(monkeypatch, valores):
    """Fija el valor de algunos parámetros durante el test (los demás siguen valiendo lo de siempre)."""
    from src.config.parametros import parametros

    real = parametros.valor
    monkeypatch.setattr(parametros, "valor", lambda clave: valores[clave] if clave in valores else real(clave))


class TestParametrosDeVictoria:
    """ADR-011: memoria, vueltas y textos se leen en CADA turno, así un cambio hecho en la app
    se nota en el siguiente mensaje sin reiniciar el worker (que construye el servicio una sola vez)."""

    @staticmethod
    def _historial(cantidad):
        filas = [{"rol": "cliente" if i % 2 == 0 else "bot", "contenido": f"mensaje {i}"} for i in range(cantidad)]
        return filas + [{"rol": "cliente", "contenido": "el mensaje nuevo"}]

    @staticmethod
    def _fin():
        return RespuestaLLM(texto="Hola", llamadas_herramientas=[], razon_de_parada="fin")

    def test_la_memoria_por_defecto_son_cuarenta_mensajes(self, monkeypatch):
        monkeypatch.delenv("BOT_MAX_MENSAJES_HISTORIAL", raising=False)
        llm = LLMProviderFalso([self._fin()])
        _servicio_sin_fijar(llm, self._historial(60)).procesar_turno(1, "el mensaje nuevo")
        assert len(llm.llamadas[0]["mensajes"]) == 40 + 1  # 40 anteriores + el mensaje nuevo

    def test_cambiar_la_memoria_se_nota_en_el_siguiente_turno_con_el_mismo_servicio(self, monkeypatch):
        llm = LLMProviderFalso([self._fin(), self._fin()])
        servicio = _servicio_sin_fijar(llm, self._historial(60))

        _con_parametros(monkeypatch, {"bot.max_mensajes_historial": 12})
        servicio.procesar_turno(1, "el mensaje nuevo")
        _con_parametros(monkeypatch, {"bot.max_mensajes_historial": 30})
        servicio.procesar_turno(1, "el mensaje nuevo")

        assert [len(c["mensajes"]) for c in llm.llamadas] == [12 + 1, 30 + 1]

    def test_cambiar_las_vueltas_con_herramientas_se_nota_en_el_siguiente_turno(self, monkeypatch):
        def pide_herramienta(i):
            return RespuestaLLM(
                texto="",
                llamadas_herramientas=[LlamadaHerramienta(id=f"t{i}", nombre="guardar_datos_cliente", entrada={})],
                razon_de_parada="necesita_herramientas",
            )

        llm = LLMProviderFalso([pide_herramienta(i) for i in range(2)] + [pide_herramienta(i) for i in range(2, 5)])
        servicio = _servicio_sin_fijar(llm, [{"rol": "cliente", "contenido": "hola"}])

        _con_parametros(monkeypatch, {"bot.max_turnos_herramientas": 2})
        servicio.procesar_turno(1, "hola")
        assert len(llm.llamadas) == 2  # con 2 vueltas, escala

        _con_parametros(monkeypatch, {"bot.max_turnos_herramientas": 3})
        servicio.procesar_turno(1, "hola")
        assert len(llm.llamadas) == 2 + 3

    def test_el_mensaje_de_limite_alcanzado_es_el_parametro(self, monkeypatch):
        respuestas = [
            RespuestaLLM(
                texto="",
                llamadas_herramientas=[LlamadaHerramienta(id=f"t{i}", nombre="guardar_datos_cliente", entrada={})],
                razon_de_parada="necesita_herramientas",
            )
            for i in range(2)
        ]
        _con_parametros(monkeypatch, {"bot.max_turnos_herramientas": 2, "bot.texto_limite_alcanzado": "Texto editado desde la app"})
        servicio = _servicio_sin_fijar(LLMProviderFalso(respuestas), [{"rol": "cliente", "contenido": "hola"}])
        assert servicio.procesar_turno(1, "hola") == "Texto editado desde la app"

    def test_el_cliente_de_ia_se_pide_en_cada_turno_para_que_un_cambio_de_modelo_se_note(self, monkeypatch):
        usados = []

        class LLMDelTurno(LLMProviderFalso):
            def __init__(self, nombre):
                super().__init__([RespuestaLLM(texto=nombre, llamadas_herramientas=[], razon_de_parada="fin")])

        turnos = iter([LLMDelTurno("modelo A"), LLMDelTurno("modelo B")])
        monkeypatch.setattr("src.routes.whatsapp.conversation_service.get_llm_client", lambda: usados.append(1) or next(turnos))
        servicio = VictoriaConversationService(
            lead_repo=FakeLeadRepository(),
            conversacion_repo=FakeConversacionRepository({1: {"id": 1, "contacto_id": 1, "telefono": "593987654321", "id_anuncio": None}}),
            mensaje_repo=FakeMensajeRepository(historial=[{"rol": "cliente", "contenido": "hola"}]),
            producto_repo=FakeProductoBotRepository(),
            ejecutor_herramientas=EjecutorHerramientasFalso(),
        )
        assert servicio.procesar_turno(1, "hola") == "modelo A"
        assert servicio.procesar_turno(1, "hola") == "modelo B"
        assert len(usados) == 2


class TestInstruccionesDeVictoria:
    """ADR-011, fase P3: lo que Victoria recibe como instrucciones sale de la versión publicada
    (o del archivo del código), se lee en cada turno y nunca se rompe por el texto editado."""

    @staticmethod
    def _system_del_turno(**kw):
        llm = LLMProviderFalso([RespuestaLLM(texto="Hola", llamadas_herramientas=[], razon_de_parada="fin")])
        servicio = VictoriaConversationService(
            llm_client=llm, lead_repo=FakeLeadRepository(),
            conversacion_repo=FakeConversacionRepository({1: {"id": 1, "contacto_id": 1, "telefono": "593987654321", "id_anuncio": None}}),
            mensaje_repo=FakeMensajeRepository(historial=[{"rol": "cliente", "contenido": "Hola"}]),
            producto_repo=FakeProductoBotRepository(), ejecutor_herramientas=EjecutorHerramientasFalso(),
            max_turnos_herramientas=5, max_mensajes_historial=40, **kw,
        )
        servicio.procesar_turno(conversacion_id=1, mensaje_cliente="Hola")
        return llm.llamadas[0]["system"]

    def test_sin_version_publicada_usa_el_archivo_del_codigo(self):
        from src.routes.whatsapp.instrucciones import cuerpo_fijo

        system = self._system_del_turno()
        assert system.startswith("Eres Victoria, asesora de ventas de AzoShop")
        # las secciones editables y las bloqueadas del archivo original llegan completas y sin huecos sin rellenar
        assert "Hablas como una persona real" in system and cuerpo_fijo("herramientas") in system and "{" not in system

    def test_una_plantilla_fija_manda_sobre_la_vigente(self):
        system = self._system_del_turno(plantilla="Solo prueba. Producto: {contexto_producto}. Fecha: {fecha_actual}. Lead: {contexto_lead_actual}")
        assert system.startswith("Solo prueba. Producto:") and "## Tu personalidad" not in system

    def test_lo_publicado_se_lee_en_cada_turno_sin_reiniciar(self, monkeypatch):
        from src.routes.whatsapp import conversation_service as modulo
        from src.routes.whatsapp.instrucciones import InstruccionesVigentes, ensamblar, secciones_originales

        publicada = {"secciones": {**secciones_originales(), "personalidad": "Eres de Loja, con acento lojano."}}

        class Repo:
            def publicada(self):
                return publicada

        monkeypatch.setattr(modulo, "instrucciones_vigentes", InstruccionesVigentes(repo=Repo()))
        system = self._system_del_turno()
        assert "Eres de Loja, con acento lojano." in system and "Hablas como una persona real" not in system
        assert "## Estado actual de este lead" in system  # las secciones bloqueadas siguen ahí
        assert ensamblar({**secciones_originales(), "personalidad": "Eres de Loja, con acento lojano."}).count("{contexto_producto}") == 1

    def test_las_llaves_del_texto_publicado_no_rompen_el_turno(self, monkeypatch):
        from src.routes.whatsapp import conversation_service as modulo
        from src.routes.whatsapp.instrucciones import InstruccionesVigentes, secciones_originales

        publicada = {"secciones": {**secciones_originales(), "reglas": "Nunca digas {esto} ni } aquello { ni {contexto_producto}."}}

        class Repo:
            def publicada(self):
                return publicada

        monkeypatch.setattr(modulo, "instrucciones_vigentes", InstruccionesVigentes(repo=Repo()))
        system = self._system_del_turno()  # no debe lanzar KeyError/ValueError
        assert "{esto}" in system and "aquello {" in system


class TestConversacionEnManosDelDueno:
    """ADR-012: si una herramienta deja la conversación «en gestión» (aviso que traspasa o pedido cerrado),
    Victoria tiene UNA vuelta más para despedirse y después se corta, igual que con una escalada."""

    def test_en_gestion_permite_una_iteracion_mas_para_la_despedida(self):
        llm = LLMProviderFalso([
            RespuestaLLM(
                texto="",
                llamadas_herramientas=[LlamadaHerramienta(id="t1", nombre="cerrar_venta", entrada={})],
                razon_de_parada="necesita_herramientas",
            ),
            RespuestaLLM(texto="¡Gracias! El dueño te escribe pronto.", llamadas_herramientas=[], razon_de_parada="fin"),
        ])
        conversaciones = FakeConversacionRepository({1: {"id": 1, "contacto_id": 1, "telefono": "593987654321", "id_anuncio": None, "estado": "activa"}})

        class EjecutorQueTraspasa(EjecutorHerramientasFalso):
            def ejecutar(self, nombre, lead_id, conversacion_id, entrada, id_llamada):
                conversaciones._tabla[1]["estado"] = "en_gestion"  # lo que hace el cierre manual en la base
                return super().ejecutar(nombre, lead_id, conversacion_id, entrada, id_llamada)

        servicio = VictoriaConversationService(
            llm_client=llm, lead_repo=FakeLeadRepository(), conversacion_repo=conversaciones,
            mensaje_repo=FakeMensajeRepository(historial=[{"rol": "cliente", "contenido": "listo"}]),
            producto_repo=FakeProductoBotRepository(), ejecutor_herramientas=EjecutorQueTraspasa(),
            max_turnos_herramientas=5, max_mensajes_historial=40,
        )

        resultado = servicio.procesar_turno(conversacion_id=1, mensaje_cliente="listo")

        assert resultado == "¡Gracias! El dueño te escribe pronto."
        assert len(llm.llamadas) == 2

    def test_el_contexto_del_lead_pide_la_entrega_solo_si_el_envio_no_va_incluido(self):
        lead = {"nombre_cliente": "Ana", "producto_nombre": "Zapatos", "entrega_nombre": None}
        sin_incluir = VictoriaConversationService._formatear_contexto_lead(lead, {"envio_incluido": False})
        incluido = VictoriaConversationService._formatear_contexto_lead(lead, {"envio_incluido": True})
        sin_producto = VictoriaConversationService._formatear_contexto_lead(lead, None)

        assert "Entrega" in sin_incluir.split("falta:")[1]
        assert "Entrega" not in incluido and "Entrega" not in sin_producto

    def test_con_la_entrega_elegida_ya_figura_entre_lo_que_se_sabe(self):
        lead = {"nombre_cliente": "Ana", "entrega_nombre": "Envío en Cuenca"}
        texto = VictoriaConversationService._formatear_contexto_lead(lead, {"envio_incluido": False})
        assert "Entrega: Envío en Cuenca" in texto.split("Todavía falta")[0]


class MensajesConId:
    """Mensajes con id y hora, como en la base: ordenados por hora y, a igual hora, por id. Permite probar qué pasa
    cuando el cliente escribe mientras Victoria redacta (`al_generar` simula ese mensaje)."""

    def __init__(self, filas):
        self.filas = [{"id": i + 1, "creado_en": i + 1, "tipo": "texto", **f} for i, f in enumerate(filas)]
        self.al_generar = None

    def _siguiente_id(self):
        return max((f["id"] for f in self.filas), default=0) + 1

    def agregar_cliente(self, texto):
        # Llega después de todo lo que hay: id y hora nuevos.
        ultimo = max((f["creado_en"] for f in self.filas), default=0)
        self.filas.append({"id": self._siguiente_id(), "creado_en": ultimo + 1, "rol": "cliente", "contenido": texto, "tipo": "texto"})

    def obtener_por_conversacion(self, conversacion_id):
        return sorted(self.filas, key=lambda f: (f["creado_en"], f["id"]))

    def crear(self, conversacion_id, rol, contenido, tipo="texto", wamid=None, creado_en=None):
        ultimo = max((f["creado_en"] for f in self.filas), default=0)
        fila = {"id": self._siguiente_id(), "creado_en": creado_en if creado_en is not None else ultimo + 1,
                "rol": rol, "contenido": contenido, "tipo": tipo}
        self.filas.append(fila)
        return fila


class LLMQueEscribeMientrasRedacta(LLMProviderFalso):
    def __init__(self, respuestas, mensajes, texto_nuevo=None):
        super().__init__(respuestas)
        self._mensajes = mensajes
        self._texto_nuevo = texto_nuevo

    def generar_respuesta(self, system, mensajes, herramientas, max_tokens=1024):
        resultado = super().generar_respuesta(system, mensajes, herramientas, max_tokens)
        if self._texto_nuevo:
            self._mensajes.agregar_cliente(self._texto_nuevo)
            self._texto_nuevo = None
        return resultado


def _servicio_con(llm, mensajes):
    return VictoriaConversationService(
        llm_client=llm,
        lead_repo=FakeLeadRepository(),
        conversacion_repo=FakeConversacionRepository({1: {"id": 1, "contacto_id": 1, "telefono": "593987654321", "id_anuncio": None}}),
        mensaje_repo=mensajes,
        producto_repo=FakeProductoBotRepository(),
        ejecutor_herramientas=EjecutorHerramientasFalso(),
        max_turnos_herramientas=5,
        max_mensajes_historial=40,
    )


def _fin(texto):
    return RespuestaLLM(texto=texto, llamadas_herramientas=[], razon_de_parada="fin")


class TestMensajesSeguidosDelCliente:
    def test_los_mensajes_seguidos_se_leen_juntos_como_un_solo_mensaje(self):
        mensajes = MensajesConId([
            {"rol": "cliente", "contenido": "Hola"},
            {"rol": "bot", "contenido": "¡Hola! ¿En qué te ayudo?"},
            {"rol": "cliente", "contenido": "Buenas tardes"},
            {"rol": "cliente", "contenido": "Quiero"},
            {"rol": "cliente", "contenido": "Unos audífonos"},
        ])
        llm = LLMProviderFalso([_fin("Claro, te cuento de los audífonos.")])

        resultado = _servicio_con(llm, mensajes).procesar_turno(1, "Unos audífonos")

        enviado = llm.llamadas[0]["mensajes"]
        assert [(m.rol, m.texto) for m in enviado] == [
            ("user", "Hola"),
            ("assistant", "¡Hola! ¿En qué te ayudo?"),
            ("user", "Buenas tardes\nQuiero\nUnos audífonos"),
        ]
        assert resultado == "Claro, te cuento de los audífonos."

    def test_si_ya_estaba_respondido_no_vuelve_a_responder(self):
        mensajes = MensajesConId([{"rol": "cliente", "contenido": "Hola"}, {"rol": "bot", "contenido": "¡Hola!"}])
        llm = LLMProviderFalso([])

        resultado = _servicio_con(llm, mensajes).procesar_turno(1, "Hola")

        assert resultado == ""
        assert llm.llamadas == []
        assert [f["rol"] for f in mensajes.filas] == ["cliente", "bot"]

    def test_la_respuesta_anterior_de_victoria_si_aparece_en_el_historial_del_siguiente_turno(self):
        mensajes = MensajesConId([{"rol": "cliente", "contenido": "Hola"}])
        llm = LLMProviderFalso([_fin("¡Hola! ¿Qué buscas?"), _fin("Tenemos de varios precios.")])
        servicio = _servicio_con(llm, mensajes)

        servicio.procesar_turno(1, "Hola")
        mensajes.agregar_cliente("Unos audífonos")
        servicio.procesar_turno(1, "Unos audífonos")

        assert [(m.rol, m.texto) for m in llm.llamadas[1]["mensajes"]] == [
            ("user", "Hola"),
            ("assistant", "¡Hola! ¿Qué buscas?"),
            ("user", "Unos audífonos"),
        ]

    def test_un_mensaje_que_llega_mientras_redacta_sigue_sin_responder_para_el_siguiente_turno(self):
        mensajes = MensajesConId([{"rol": "cliente", "contenido": "Hola"}])
        llm = LLMQueEscribeMientrasRedacta([_fin("¡Hola!"), _fin("Sí, tenemos.")], mensajes, texto_nuevo="¿Tienen audífonos?")
        servicio = _servicio_con(llm, mensajes)

        primera = servicio.procesar_turno(1, "Hola")
        # El mensaje nuevo quedó DESPUÉS de la respuesta: no parece contestado.
        assert [f["rol"] for f in mensajes.obtener_por_conversacion(1)] == ["cliente", "bot", "cliente"]
        segunda = servicio.procesar_turno(1, "¿Tienen audífonos?")

        assert primera == "¡Hola!" and segunda == "Sí, tenemos."
        assert [(m.rol, m.texto) for m in llm.llamadas[1]["mensajes"]] == [
            ("user", "Hola"),
            ("assistant", "¡Hola!"),
            ("user", "¿Tienen audífonos?"),
        ]

    def test_sin_mensajes_guardados_usa_el_mensaje_recibido(self):
        llm = LLMProviderFalso([_fin("Hola")])
        servicio = _servicio_con(llm, MensajesConId([]))

        assert servicio.procesar_turno(1, "Hola") == "Hola"
        assert [(m.rol, m.texto) for m in llm.llamadas[0]["mensajes"]] == [("user", "Hola")]


class TestRespuestaVacia:
    def test_si_la_ia_no_escribe_nada_se_escala_y_el_cliente_recibe_el_aviso(self):
        mensajes = MensajesConId([{"rol": "cliente", "contenido": "Hola"}])
        llm = LLMProviderFalso([_fin("   ")])
        ejecutor = EjecutorHerramientasFalso()
        servicio = _servicio_con(llm, mensajes)
        servicio._ejecutor = ejecutor

        resultado = servicio.procesar_turno(1, "Hola")

        assert resultado.strip() != ""
        assert [l["nombre"] for l in ejecutor.llamadas] == ["escalar_a_humano"]
        # Lo que se guarda y se envía es el aviso, no un mensaje vacío.
        assert mensajes.filas[-1]["rol"] == "bot" and mensajes.filas[-1]["contenido"] == resultado

    def test_el_texto_de_antes_y_de_despues_de_una_herramienta_sale_separado_por_un_renglon(self):
        llm = LLMProviderFalso([
            RespuestaLLM(
                texto="Un momento, lo reviso.",
                llamadas_herramientas=[LlamadaHerramienta(id="t1", nombre="ver_ficha_producto", entrada={"producto_sku": "X"})],
                razon_de_parada="necesita_herramientas",
            ),
            _fin("Cuesta $20."),
        ])
        servicio = _servicio_con(llm, MensajesConId([{"rol": "cliente", "contenido": "¿Cuánto cuesta?"}]))

        assert servicio.procesar_turno(1, "¿Cuánto cuesta?") == "Un momento, lo reviso.\n\nCuesta $20."
