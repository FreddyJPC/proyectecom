from unittest.mock import MagicMock

from src.routes.webhooks.services import WebhookService


class FakeWebhookRepository:
    def __init__(self, datos_pedido=None):
        self.eventos_guardados = []
        self.estados_actualizados = []
        self.marcados_procesados = []
        self._datos_pedido = datos_pedido or {}

    def guardar_evento(self, id_rocketfy, status_id, event_date, shopify_order_id, payload):
        clave = (id_rocketfy, status_id, event_date)
        if clave in [e for e, _ in self.eventos_guardados]:
            return False
        self.eventos_guardados.append((clave, payload))
        return True

    def actualizar_estado_pedido(self, id_rocketfy, status_id):
        self.estados_actualizados.append((id_rocketfy, status_id))

    def marcar_procesado(self, id_rocketfy, status_id, event_date):
        self.marcados_procesados.append((id_rocketfy, status_id, event_date))

    def obtener_datos_pedido(self, id_rocketfy):
        return self._datos_pedido.get(id_rocketfy)


def _payload(order_id=9315702, status_id=8, event_date="2026-08-23T19:32:10.000000Z", **extra):
    base = {
        "order_id": order_id,
        "status_id": status_id,
        "event_date": event_date,
        "status_name": "Entregado",
        "shopify_order_id": 100245,
        "details": "",
    }
    base.update(extra)
    return base


class TestPersistenciaIdempotente:
    def test_evento_nuevo_se_guarda_y_actualiza_el_pedido(self):
        repo = FakeWebhookRepository()
        WebhookService(repo=repo).procesar_evento(_payload())
        assert repo.estados_actualizados == [(9315702, 8)]
        assert len(repo.eventos_guardados) == 1
        assert repo.marcados_procesados == [(9315702, 8, "2026-08-23T19:32:10.000000Z")]

    def test_mismo_evento_dos_veces_no_se_reprocesa(self):
        repo = FakeWebhookRepository()
        service = WebhookService(repo=repo)
        service.procesar_evento(_payload())
        service.procesar_evento(_payload())  # mismo order_id/status_id/event_date

        assert repo.estados_actualizados == [(9315702, 8)]  # solo la primera vez
        assert len(repo.eventos_guardados) == 1
        assert len(repo.marcados_procesados) == 1

    def test_mismo_order_id_status_distinto_si_se_procesa(self):
        repo = FakeWebhookRepository()
        service = WebhookService(repo=repo)
        service.procesar_evento(_payload(status_id=6, event_date="2026-08-23T10:00:00Z"))
        service.procesar_evento(_payload(status_id=7, event_date="2026-08-23T11:00:00Z"))

        assert repo.estados_actualizados == [(9315702, 6), (9315702, 7)]

    def test_ping_sin_order_id_no_hace_nada(self):
        repo = FakeWebhookRepository()
        WebhookService(repo=repo).procesar_evento({})
        assert repo.eventos_guardados == []
        assert repo.estados_actualizados == []


class TestToleranciaAFallos:
    def test_excepcion_interna_nunca_se_propaga(self):
        repo = MagicMock()
        repo.guardar_evento.side_effect = RuntimeError("boom")
        service = WebhookService(repo=repo)
        service.procesar_evento(_payload())  # NO debe lanzar

    def test_status_id_desconocido_se_guarda_sin_fallar(self):
        repo = FakeWebhookRepository()
        WebhookService(repo=repo).procesar_evento(_payload(status_id=999))
        assert repo.estados_actualizados == [(9315702, 999)]


class TestNotificacion:
    def test_en_ruta_con_telefono_conocido_dispara_notificacion(self):
        repo = FakeWebhookRepository(datos_pedido={9315702: {"telefono": "0991234567"}})
        notificador = MagicMock()
        WebhookService(repo=repo, notificador=notificador).procesar_evento(
            _payload(status_id=6)  # EN_RUTA
        )
        notificador.send.assert_called_once()
        mensaje_enviado = notificador.send.call_args.args[0]
        assert mensaje_enviado.to == "0991234567"

    def test_en_ruta_sin_telefono_local_no_falla_y_no_notifica(self):
        repo = FakeWebhookRepository(datos_pedido={})
        notificador = MagicMock()
        WebhookService(repo=repo, notificador=notificador).procesar_evento(_payload(status_id=6))
        notificador.send.assert_not_called()

    def test_entregado_no_dispara_notificacion_al_cliente(self):
        repo = FakeWebhookRepository(datos_pedido={9315702: {"telefono": "0991234567"}})
        notificador = MagicMock()
        WebhookService(repo=repo, notificador=notificador).procesar_evento(_payload(status_id=8))
        notificador.send.assert_not_called()
