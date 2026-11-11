"""
Cliente de la API de Conversiones para mensajería (ADR-016): forma exacta del evento, dinero sin `float`, el token nunca en los errores,
y la diferencia entre «Meta lo rechazó» (se puede reintentar) y «no sabemos si lo recibió» (NO reintentar a ciegas: Meta no deduplica).
"""
import json
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
import requests

from src.integrations.meta import MetaConversionesClient, MetaRechazoError, MetaRespuestaDudosaError
from src.integrations.meta.client import GRAPH_API_VERSION, _cuerpo_json

TOKEN = "token-secreto-de-prueba-123"
MOMENTO = datetime(2026, 11, 11, 15, 30, tzinfo=timezone.utc)


def _respuesta(status=200, cuerpo=None, json_valido=True):
    r = MagicMock()
    r.status_code = status
    if json_valido:
        r.json.return_value = cuerpo if cuerpo is not None else {"events_received": 1}
    else:
        r.json.side_effect = ValueError("no es json")
    return r


def _cliente(respuesta=None, error=None):
    c = MetaConversionesClient(TOKEN, "999000111", "555666777")
    c._session = MagicMock()
    if error is not None:
        c._session.post.side_effect = error
    else:
        c._session.post.return_value = respuesta or _respuesta()
    return c


class TestElEvento:
    def test_tiene_la_forma_que_documenta_meta(self):
        cuerpo = json.loads(_cuerpo_json("555666777", "clic-abc", Decimal("29.90"), "USD", MOMENTO))
        evento = cuerpo["data"][0]
        assert evento["event_name"] == "Purchase"
        assert evento["action_source"] == "business_messaging"
        assert evento["messaging_channel"] == "whatsapp"
        assert evento["event_time"] == int(MOMENTO.timestamp())
        assert evento["user_data"] == {"whatsapp_business_account_id": "555666777", "ctwa_clid": "clic-abc"}
        assert evento["custom_data"] == {"currency": "USD", "value": 29.9}

    def test_el_valor_viaja_con_los_centavos_exactos_y_como_numero(self):
        texto = _cuerpo_json("1", "c", Decimal("60"), "USD", MOMENTO)
        assert '"value": 60.00' in texto  # número JSON, no texto, con dos decimales
        assert '"value": 0.10' in _cuerpo_json("1", "c", Decimal("0.1"), "USD", MOMENTO)
        assert '"value": 1234567.89' in _cuerpo_json("1", "c", Decimal("1234567.89"), "USD", MOMENTO)

    def test_no_lleva_datos_personales_del_cliente(self):
        texto = _cuerpo_json("1", "c", Decimal("10"), "USD", MOMENTO)
        for prohibido in ("phone", "email", "ph", "em", "fn", "external_id"):
            assert f'"{prohibido}"' not in texto


class TestElEnvio:
    def test_envia_al_dataset_con_el_token_en_el_encabezado_y_no_en_la_direccion(self):
        c = _cliente()
        c.enviar_compra("clic-abc", Decimal("20.00"), "USD", MOMENTO)
        args, kwargs = c._session.post.call_args
        assert args[0] == f"https://graph.facebook.com/{GRAPH_API_VERSION}/999000111/events"
        assert TOKEN not in args[0]
        assert kwargs["headers"]["Authorization"] == f"Bearer {TOKEN}"
        assert json.loads(kwargs["data"])["data"][0]["user_data"]["ctwa_clid"] == "clic-abc"

    def test_devuelve_la_respuesta_de_meta_si_la_acepto(self):
        c = _cliente(_respuesta(200, {"events_received": 1, "fbtrace_id": "XYZ"}))
        assert "events_received" in c.enviar_compra("c", Decimal("1"), "USD", MOMENTO)

    def test_un_error_de_meta_con_cuerpo_de_error_es_un_rechazo_seguro_de_reintentar(self):
        c = _cliente(_respuesta(400, {"error": {"message": "Invalid parameter", "code": 100}}))
        with pytest.raises(MetaRechazoError, match="Invalid parameter"):
            c.enviar_compra("c", Decimal("1"), "USD", MOMENTO)

    def test_una_respuesta_200_con_error_tambien_es_rechazo(self):
        c = _cliente(_respuesta(200, {"error": {"message": "algo falló", "code": 190}}))
        with pytest.raises(MetaRechazoError):
            c.enviar_compra("c", Decimal("1"), "USD", MOMENTO)

    @pytest.mark.parametrize("status", [500, 502, 503])
    def test_un_error_del_servidor_de_meta_es_dudoso(self, status):
        with pytest.raises(MetaRespuestaDudosaError):
            _cliente(_respuesta(status, {})).enviar_compra("c", Decimal("1"), "USD", MOMENTO)

    def test_una_respuesta_ilegible_es_dudosa(self):
        with pytest.raises(MetaRespuestaDudosaError):
            _cliente(_respuesta(200, json_valido=False)).enviar_compra("c", Decimal("1"), "USD", MOMENTO)

    def test_tardar_en_responder_es_dudoso_porque_pudo_haberlo_recibido(self):
        with pytest.raises(MetaRespuestaDudosaError):
            _cliente(error=requests.ReadTimeout("lento")).enviar_compra("c", Decimal("1"), "USD", MOMENTO)

    def test_no_poder_conectar_es_un_rechazo_seguro_de_reintentar(self):
        with pytest.raises(MetaRechazoError):
            _cliente(error=requests.ConnectTimeout("sin conexión")).enviar_compra("c", Decimal("1"), "USD", MOMENTO)

    def test_el_token_nunca_aparece_en_los_mensajes_de_error(self):
        # `requests` suele incluir la dirección completa (y a veces el token) en sus errores: no se copia el mensaje.
        errores = [
            requests.ReadTimeout(f"https://graph.facebook.com/?access_token={TOKEN}"),
            requests.ConnectTimeout(f"https://graph.facebook.com/?access_token={TOKEN}"),
        ]
        for error in errores:
            with pytest.raises((MetaRechazoError, MetaRespuestaDudosaError)) as excinfo:
                _cliente(error=error).enviar_compra("c", Decimal("1"), "USD", MOMENTO)
            assert TOKEN not in str(excinfo.value)
