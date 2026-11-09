import time
from unittest.mock import MagicMock

from src.routes.whatsapp.worker import BotWorker
from tests.helpers_canales import registro_de_whatsapp


class FakeMensajeRepository:
    def __init__(self):
        self.mensajes = []

    def crear(self, conversacion_id, rol, contenido, tipo="texto", wamid=None):
        mensaje = {
            "conversacion_id": conversacion_id,
            "rol": rol,
            "contenido": contenido,
            "tipo": tipo,
            "wamid": wamid,
        }
        self.mensajes.append(mensaje)
        return mensaje


class FakeColaMensajeRepository:
    """Simula la tabla cola_mensajes en memoria. obtener_pendientes() se
    apoya en `telefono_por_conversacion` porque la fake no tiene una tabla
    `conversaciones` real contra la cual hacer el JOIN que sí hace el
    repositorio real."""

    def __init__(self, telefono_por_conversacion=None):
        self.filas = {}
        self._siguiente_id = 1
        self._telefonos = telefono_por_conversacion or {}

    def crear(self, conversacion_id, modo, mensaje_id=None, texto_fijo=None):
        fila = {
            "id": self._siguiente_id,
            "conversacion_id": conversacion_id,
            "mensaje_id": mensaje_id,
            "modo": modo,
            "texto_fijo": texto_fijo,
            "estado": "pendiente",
            "intentos": 0,
            "error_detalle": None,
        }
        self.filas[fila["id"]] = fila
        self._siguiente_id += 1
        return dict(fila)

    def marcar_procesando(self, cola_mensajes_id):
        self.filas[cola_mensajes_id]["estado"] = "procesando"

    def marcar_completado(self, cola_mensajes_id):
        self.filas[cola_mensajes_id]["estado"] = "completado"

    def marcar_error(self, cola_mensajes_id, error_detalle):
        fila = self.filas[cola_mensajes_id]
        fila["estado"] = "error"
        fila["error_detalle"] = error_detalle
        fila["intentos"] += 1

    def marcar_para_reintento(self, cola_mensajes_id, error_detalle):
        fila = self.filas[cola_mensajes_id]
        fila["estado"] = "pendiente"
        fila["error_detalle"] = error_detalle
        fila["intentos"] += 1
        return fila["intentos"]

    def obtener_pendientes(self):
        return [
            {
                "id": f["id"],
                "conversacion_id": f["conversacion_id"],
                "modo": f["modo"],
                "texto_fijo": f["texto_fijo"],
                "canal": "whatsapp",
                "id_externo": self._telefonos.get(f["conversacion_id"], "593987654321"),
                "mensaje_cliente_texto": None,
                "intentos": f["intentos"],
            }
            for f in self.filas.values()
            if f["estado"] in ("pendiente", "procesando")
        ]


class TestPersistenciaDeCola:
    def test_tarea_pendiente_se_recupera_y_procesa_al_reiniciar(self):
        cola_repo = FakeColaMensajeRepository(telefono_por_conversacion={1: "593987654321"})

        # Simula un primer proceso que encola pero muere antes de procesar
        # (su thread nunca arranca -- la fila queda en cola_mensajes con
        # estado='pendiente', que es justo lo que recuperar_pendientes()
        # busca).
        worker_caido = BotWorker(
            canales=registro_de_whatsapp(MagicMock()),
            mensaje_repository=FakeMensajeRepository(),
            cola_repository=cola_repo,
            telegram=MagicMock(),
        )
        worker_caido.encolar(conversacion_id=1, canal="whatsapp", id_externo="593987654321", modo="fijo", texto_fijo="hola de prueba")

        cliente_nuevo = MagicMock()
        msg_repo_nuevo = FakeMensajeRepository()
        worker_nuevo = BotWorker(
            canales=registro_de_whatsapp(cliente_nuevo),
            mensaje_repository=msg_repo_nuevo,
            cola_repository=cola_repo,
            telegram=MagicMock(),
        )
        worker_nuevo.iniciar()
        worker_nuevo._cola.join()

        assert cola_repo.filas[1]["estado"] == "completado"
        cliente_nuevo.enviar_texto.assert_called_once_with(telefono="593987654321", mensaje="hola de prueba")
        assert msg_repo_nuevo.mensajes[0]["contenido"] == "hola de prueba"

    def test_tarea_modo_ia_invoca_a_victoria_y_no_guarda_el_mensaje_dos_veces(self):
        class ConversationServiceFalso:
            def __init__(self):
                self.llamadas = []

            def procesar_turno(self, conversacion_id, mensaje_cliente):
                self.llamadas.append((conversacion_id, mensaje_cliente))
                return "Respuesta de Victoria"

        cola_repo = FakeColaMensajeRepository(telefono_por_conversacion={5: "593987654321"})
        cliente = MagicMock()
        msg_repo = FakeMensajeRepository()
        conversation_service = ConversationServiceFalso()

        worker = BotWorker(
            canales=registro_de_whatsapp(cliente),
            mensaje_repository=msg_repo,
            cola_repository=cola_repo,
            conversation_service=conversation_service,
            segundos_espera=0,
        )
        worker.iniciar()
        worker.encolar(
            conversacion_id=5, canal="whatsapp", id_externo="593987654321", modo="ia", texto_mensaje_cliente="Quiero comprar"
        )
        worker._cola.join()

        assert conversation_service.llamadas == [(5, "Quiero comprar")]
        cliente.enviar_texto.assert_called_once_with(telefono="593987654321", mensaje="Respuesta de Victoria")
        # VictoriaConversationService.procesar_turno() ya guarda el mensaje
        # del bot por su cuenta (Tarea 6) -- el worker no debe duplicarlo.
        assert msg_repo.mensajes == []
        assert cola_repo.filas[1]["estado"] == "completado"

    def test_tarea_que_falla_queda_en_error_y_el_worker_sigue_procesando(self):
        cola_repo = FakeColaMensajeRepository()
        cliente = MagicMock()
        cliente.enviar_texto.side_effect = [RuntimeError("boom"), None]

        worker = BotWorker(
            canales=registro_de_whatsapp(cliente),
            mensaje_repository=FakeMensajeRepository(),
            cola_repository=cola_repo,
            telegram=MagicMock(),
        )
        worker.iniciar()
        worker.encolar(conversacion_id=1, canal="whatsapp", id_externo="593987654321", modo="fijo", texto_fijo="primero")
        worker.encolar(conversacion_id=1, canal="whatsapp", id_externo="593987654321", modo="fijo", texto_fijo="segundo")
        worker._cola.join()

        assert cola_repo.filas[1]["estado"] == "error"
        assert "boom" in cola_repo.filas[1]["error_detalle"]
        assert cola_repo.filas[1]["intentos"] == 1
        assert cola_repo.filas[2]["estado"] == "completado"


class TestCanales:
    def test_la_respuesta_sale_por_el_canal_de_la_tarea(self):
        cola_repo = FakeColaMensajeRepository()
        cliente = MagicMock()
        worker = BotWorker(
            canales=registro_de_whatsapp(cliente), mensaje_repository=FakeMensajeRepository(), cola_repository=cola_repo,
            telegram=MagicMock(),
        )
        worker.iniciar()
        worker.encolar(conversacion_id=1, canal="whatsapp", id_externo="593987654321", modo="fijo", texto_fijo="hola")
        worker._cola.join()
        cliente.enviar_texto.assert_called_once_with(telefono="593987654321", mensaje="hola")

    def test_un_canal_sin_conectar_deja_la_tarea_en_error_y_el_worker_sigue(self):
        cola_repo = FakeColaMensajeRepository()
        cliente = MagicMock()
        worker = BotWorker(
            canales=registro_de_whatsapp(cliente), mensaje_repository=FakeMensajeRepository(), cola_repository=cola_repo,
            telegram=MagicMock(),
        )
        worker.iniciar()
        worker.encolar(conversacion_id=1, canal="instagram", id_externo="1784", modo="fijo", texto_fijo="no sale")
        worker.encolar(conversacion_id=1, canal="whatsapp", id_externo="593987654321", modo="fijo", texto_fijo="sí sale")
        worker._cola.join()

        assert cola_repo.filas[1]["estado"] == "error" and "todavía no está conectado" in cola_repo.filas[1]["error_detalle"]
        assert cola_repo.filas[2]["estado"] == "completado"
        cliente.enviar_texto.assert_called_once_with(telefono="593987654321", mensaje="sí sale")


def _esperar(condicion, segundos=3.0):
    limite = time.monotonic() + segundos
    while time.monotonic() < limite:
        if condicion():
            return True
        time.sleep(0.01)
    return False


class ServicioQueRecuerda:
    def __init__(self, respuestas):
        self.respuestas = list(respuestas)
        self.llamadas = []

    def procesar_turno(self, conversacion_id, mensaje_cliente):
        self.llamadas.append((conversacion_id, mensaje_cliente))
        respuesta = self.respuestas.pop(0)
        if isinstance(respuesta, Exception):
            raise respuesta
        return respuesta


def _worker(servicio, cola_repo, cliente=None, telegram=None, espera=0, pausas=(0.0,)):
    return BotWorker(
        canales=registro_de_whatsapp(cliente or MagicMock()),
        mensaje_repository=FakeMensajeRepository(),
        cola_repository=cola_repo,
        conversation_service=servicio,
        segundos_espera=espera,
        telegram=telegram or MagicMock(),
        pausas_reintento=pausas,
    )


class TestRafagasDeMensajes:
    def test_mensajes_seguidos_dentro_de_la_espera_se_responden_una_sola_vez(self):
        cola_repo = FakeColaMensajeRepository()
        servicio = ServicioQueRecuerda(["Respuesta única"])
        cliente = MagicMock()
        worker = _worker(servicio, cola_repo, cliente, espera=0.3)
        worker.iniciar()

        for texto in ("Hola", "Buenas tardes", "Quiero", "Unos audífonos"):
            worker.encolar(conversacion_id=7, canal="whatsapp", id_externo="593987654321", texto_mensaje_cliente=texto)
            time.sleep(0.05)

        assert _esperar(lambda: cliente.enviar_texto.call_count == 1)
        time.sleep(0.4)
        # Una sola fila en la cola y una sola respuesta, aunque llegaron cuatro mensajes.
        assert len(cola_repo.filas) == 1
        assert len(servicio.llamadas) == 1
        cliente.enviar_texto.assert_called_once_with(telefono="593987654321", mensaje="Respuesta única")
        assert cola_repo.filas[1]["estado"] == "completado"

    def test_la_espera_se_reinicia_con_cada_mensaje_nuevo(self):
        cola_repo = FakeColaMensajeRepository()
        servicio = ServicioQueRecuerda(["ok"])
        worker = _worker(servicio, cola_repo, espera=0.3)
        worker.iniciar()

        worker.encolar(conversacion_id=7, canal="whatsapp", id_externo="593987654321")
        time.sleep(0.2)
        worker.encolar(conversacion_id=7, canal="whatsapp", id_externo="593987654321")
        time.sleep(0.2)
        # Pasaron 0.4 s desde el primero, pero solo 0.2 desde el último: todavía espera.
        assert servicio.llamadas == []
        assert _esperar(lambda: len(servicio.llamadas) == 1)

    def test_la_espera_tiene_tope_para_quien_escribe_sin_parar(self):
        cola_repo = FakeColaMensajeRepository()
        servicio = ServicioQueRecuerda(["ok"])
        worker = _worker(servicio, cola_repo, espera=0.2)
        worker.iniciar()

        inicio = time.monotonic()
        # Un mensaje cada 0.1 s: sin tope la espera no terminaría nunca. Tope = 3 × 0.2 = 0.6 s.
        while time.monotonic() - inicio < 1.5 and not servicio.llamadas:
            worker.encolar(conversacion_id=7, canal="whatsapp", id_externo="593987654321")
            time.sleep(0.1)
        assert servicio.llamadas, "debió responder aunque el cliente siguiera escribiendo"
        assert time.monotonic() - inicio < 1.2

    def test_conversaciones_distintas_no_se_mezclan(self):
        cola_repo = FakeColaMensajeRepository()
        servicio = ServicioQueRecuerda(["a", "b"])
        worker = _worker(servicio, cola_repo, espera=0.1)
        worker.iniciar()

        worker.encolar(conversacion_id=1, canal="whatsapp", id_externo="593111111111")
        worker.encolar(conversacion_id=2, canal="whatsapp", id_externo="593222222222")

        assert _esperar(lambda: len(servicio.llamadas) == 2)
        assert {c for c, _ in servicio.llamadas} == {1, 2}
        assert len(cola_repo.filas) == 2

    def test_si_ya_estaba_contestado_no_se_envia_nada(self):
        cola_repo = FakeColaMensajeRepository()
        cliente = MagicMock()
        worker = _worker(ServicioQueRecuerda([""]), cola_repo, cliente)
        worker.iniciar()
        worker.encolar(conversacion_id=1, canal="whatsapp", id_externo="593987654321")
        worker._cola.join()

        cliente.enviar_texto.assert_not_called()
        assert cola_repo.filas[1]["estado"] == "completado"

    def test_los_avisos_fijos_no_esperan(self):
        cola_repo = FakeColaMensajeRepository()
        cliente = MagicMock()
        worker = _worker(ServicioQueRecuerda([]), cola_repo, cliente, espera=30)
        worker.iniciar()
        worker.encolar(conversacion_id=1, canal="whatsapp", id_externo="593987654321", modo="fijo", texto_fijo="ya te atiende una persona")
        worker._cola.join()

        cliente.enviar_texto.assert_called_once()

    def test_el_parametro_manda_cuando_no_se_fija_la_espera(self, monkeypatch):
        from src.config.parametros import parametros

        # Se lee en cada mensaje: con 0 no hay espera y la tarea ya está en la cola real.
        monkeypatch.setattr(parametros, "valor", lambda clave: 0)
        worker = BotWorker(
            canales=registro_de_whatsapp(MagicMock()),
            mensaje_repository=FakeMensajeRepository(),
            cola_repository=FakeColaMensajeRepository(),
            conversation_service=ServicioQueRecuerda(["ok"]),
            telegram=MagicMock(),
        )
        worker.iniciar()
        worker.encolar(conversacion_id=1, canal="whatsapp", id_externo="593987654321")
        worker._cola.join()

    def test_el_valor_por_defecto_del_parametro_es_cinco_segundos(self):
        from src.config.parametros import parametros

        assert parametros.valor("bot.segundos_espera_mensajes") == 5


class TestFallosYReintentos:
    def test_si_la_ia_falla_una_vez_se_reintenta_y_el_cliente_recibe_la_respuesta(self):
        cola_repo = FakeColaMensajeRepository()
        cliente = MagicMock()
        telegram = MagicMock()
        servicio = ServicioQueRecuerda([RuntimeError("IA saturada"), "Ya sí, aquí estoy"])
        worker = _worker(servicio, cola_repo, cliente, telegram)
        worker.iniciar()
        worker.encolar(conversacion_id=1, canal="whatsapp", id_externo="593987654321")

        assert _esperar(lambda: cola_repo.filas[1]["estado"] == "completado")
        cliente.enviar_texto.assert_called_once_with(telefono="593987654321", mensaje="Ya sí, aquí estoy")
        assert cola_repo.filas[1]["intentos"] == 1
        telegram.notificar_aviso.assert_not_called()

    def test_si_sigue_fallando_queda_en_error_y_se_avisa_al_dueno(self):
        cola_repo = FakeColaMensajeRepository()
        telegram = MagicMock()
        servicio = ServicioQueRecuerda([RuntimeError("falla 1"), RuntimeError("falla 2"), RuntimeError("falla 3")])
        worker = _worker(servicio, cola_repo, MagicMock(), telegram)
        worker.iniciar()
        worker.encolar(conversacion_id=9, canal="whatsapp", id_externo="593987654321")

        assert _esperar(lambda: cola_repo.filas[1]["estado"] == "error")
        assert len(servicio.llamadas) == 3  # el intento inicial y dos reintentos
        telegram.notificar_aviso.assert_called_once()
        titulo, detalle = telegram.notificar_aviso.call_args.args
        assert "sin respuesta" in titulo and "9" in detalle and "falla 3" in detalle

    def test_un_fallo_al_enviar_no_se_reintenta_pero_si_se_avisa(self):
        cola_repo = FakeColaMensajeRepository()
        cliente = MagicMock()
        cliente.enviar_texto.side_effect = RuntimeError("WhatsApp caído")
        telegram = MagicMock()
        servicio = ServicioQueRecuerda(["Respuesta lista"])
        worker = _worker(servicio, cola_repo, cliente, telegram)
        worker.iniciar()
        worker.encolar(conversacion_id=1, canal="whatsapp", id_externo="593987654321")
        worker._cola.join()

        assert cola_repo.filas[1]["estado"] == "error"
        assert len(servicio.llamadas) == 1  # no volvió a redactar
        telegram.notificar_aviso.assert_called_once()

    def test_si_el_aviso_de_telegram_falla_el_worker_sigue(self):
        cola_repo = FakeColaMensajeRepository()
        cliente = MagicMock()
        cliente.enviar_texto.side_effect = [RuntimeError("boom"), None]
        telegram = MagicMock()
        telegram.notificar_aviso.side_effect = RuntimeError("Telegram caído")
        worker = _worker(ServicioQueRecuerda([]), cola_repo, cliente, telegram)
        worker.iniciar()
        worker.encolar(conversacion_id=1, canal="whatsapp", id_externo="593987654321", modo="fijo", texto_fijo="uno")
        worker.encolar(conversacion_id=1, canal="whatsapp", id_externo="593987654321", modo="fijo", texto_fijo="dos")
        worker._cola.join()

        assert cola_repo.filas[1]["estado"] == "error"
        assert cola_repo.filas[2]["estado"] == "completado"

    def test_al_reiniciar_se_recupera_tambien_una_tarea_que_estaba_procesando(self):
        cola_repo = FakeColaMensajeRepository()
        cola_repo.crear(conversacion_id=1, modo="fijo", texto_fijo="a medias")
        cola_repo.marcar_procesando(1)  # el proceso anterior murió con ella en marcha
        cliente = MagicMock()
        worker = _worker(ServicioQueRecuerda([]), cola_repo, cliente)
        worker.iniciar()
        worker._cola.join()

        assert cola_repo.filas[1]["estado"] == "completado"
        cliente.enviar_texto.assert_called_once()
