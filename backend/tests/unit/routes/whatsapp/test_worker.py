from unittest.mock import MagicMock

from src.routes.whatsapp.worker import BotWorker


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

    def obtener_pendientes(self):
        return [
            {
                "id": f["id"],
                "conversacion_id": f["conversacion_id"],
                "modo": f["modo"],
                "texto_fijo": f["texto_fijo"],
                "telefono": self._telefonos.get(f["conversacion_id"], "593987654321"),
                "mensaje_cliente_texto": None,
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
            whatsapp_client=MagicMock(),
            mensaje_repository=FakeMensajeRepository(),
            cola_repository=cola_repo,
        )
        worker_caido.encolar(conversacion_id=1, telefono="593987654321", modo="fijo", texto_fijo="hola de prueba")

        cliente_nuevo = MagicMock()
        msg_repo_nuevo = FakeMensajeRepository()
        worker_nuevo = BotWorker(
            whatsapp_client=cliente_nuevo,
            mensaje_repository=msg_repo_nuevo,
            cola_repository=cola_repo,
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
            whatsapp_client=cliente,
            mensaje_repository=msg_repo,
            cola_repository=cola_repo,
            conversation_service=conversation_service,
        )
        worker.iniciar()
        worker.encolar(
            conversacion_id=5, telefono="593987654321", modo="ia", texto_mensaje_cliente="Quiero comprar"
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
            whatsapp_client=cliente,
            mensaje_repository=FakeMensajeRepository(),
            cola_repository=cola_repo,
        )
        worker.iniciar()
        worker.encolar(conversacion_id=1, telefono="593987654321", modo="fijo", texto_fijo="primero")
        worker.encolar(conversacion_id=1, telefono="593987654321", modo="fijo", texto_fijo="segundo")
        worker._cola.join()

        assert cola_repo.filas[1]["estado"] == "error"
        assert "boom" in cola_repo.filas[1]["error_detalle"]
        assert cola_repo.filas[1]["intentos"] == 1
        assert cola_repo.filas[2]["estado"] == "completado"
