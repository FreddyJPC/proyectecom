"""
Cliente de la API de Conversiones para mensajería de Meta (ADR-016, docs/PLAN_META_ADS.md): le avisa a Meta que un clic en un anuncio
de Click-to-WhatsApp terminó en una compra, para que optimice los anuncios hacia quien compra.

Notas de diseño:
- Es el ÚNICO lugar que habla con ese servicio de Meta. El resto del sistema entrega datos y recibe un resultado.
- Meta NO deduplica estos eventos (lo dice su documentación): por eso la bandeja `eventos_meta` tiene clave única por venta y este cliente
  distingue dos fallos distintos, igual que Rocketfy y WhatsApp:
    * `MetaRechazoError`: Meta contestó que NO lo aceptó (error 4xx con cuerpo de error, o éxito sin confirmación). Es seguro reintentar.
    * `MetaRespuestaDudosaError`: no sabemos si lo recibió (se cortó la conexión, tardó demasiado, error 5xx o respuesta ilegible).
      Reintentar a ciegas podría duplicar la compra: quien llama NO debe reintentar sin una persona.
- El dinero viaja como número JSON con los centavos exactos (`Decimal`, nunca `float`): ver `_cuerpo_json`.
- Jamás se escribe el token en logs, mensajes de error ni respuestas guardadas. Los mensajes de error de `requests` pueden traer la
  dirección completa, por eso aquí solo se usa el nombre de la clase del error.
- Versión del Graph API y forma del evento: tomadas de la documentación oficial leída el 2026-11-11 (ver el plan, §6). La ventana
  máxima del evento y el mínimo para optimizar NO los dice la documentación: se verifican con datos reales (pendiente #79).
"""
import json
import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict

import requests

logger = logging.getLogger(__name__)

GRAPH_API_VERSION = "v27.0"
_MAXIMO_RESPUESTA = 500
_MARCADOR_VALOR = "__VALOR_EXACTO__"


class MetaError(Exception):
    """Base de los errores de este cliente."""


class MetaRechazoError(MetaError):
    """Meta respondió que no aceptó el evento: no quedó registrado y se puede reintentar."""


class MetaRespuestaDudosaError(MetaError):
    """No se sabe si Meta recibió el evento. NO reintentar a ciegas (podría duplicarse)."""


def _cuerpo_json(whatsapp_business_account_id: str, ctwa_clid: str, valor: Decimal, moneda: str, ocurrido_en: datetime) -> str:
    """Arma el JSON del evento de compra. El valor se escribe como número con dos decimales exactos (sin pasar por `float`)."""
    cuerpo = {
        "data": [
            {
                "event_name": "Purchase",
                "event_time": int(ocurrido_en.timestamp()),
                "action_source": "business_messaging",
                "messaging_channel": "whatsapp",
                "user_data": {
                    "whatsapp_business_account_id": whatsapp_business_account_id,
                    "ctwa_clid": ctwa_clid,
                },
                "custom_data": {"currency": moneda, "value": _MARCADOR_VALOR},
            }
        ]
    }
    texto = json.dumps(cuerpo, ensure_ascii=False)
    return texto.replace(f'"{_MARCADOR_VALOR}"', f"{Decimal(valor).quantize(Decimal('0.01'))}")


def _recortar(texto: str) -> str:
    return texto if len(texto) <= _MAXIMO_RESPUESTA else texto[: _MAXIMO_RESPUESTA - 1] + "…"


class MetaConversionesClient:
    def __init__(self, access_token: str, dataset_id: str, whatsapp_business_account_id: str, timeout: int = 20):
        self._access_token = access_token
        self._whatsapp_business_account_id = whatsapp_business_account_id
        self._url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{dataset_id}/events"
        self._timeout = timeout
        self._session = requests.Session()

    def enviar_compra(self, ctwa_clid: str, valor: Decimal, moneda: str, ocurrido_en: datetime) -> str:
        """Envía un evento `Purchase`. Devuelve la respuesta de Meta (recortada) si lo aceptó."""
        cuerpo = _cuerpo_json(self._whatsapp_business_account_id, ctwa_clid, valor, moneda, ocurrido_en)
        try:
            resp = self._session.post(
                self._url,
                data=cuerpo.encode("utf-8"),
                headers={"Authorization": f"Bearer {self._access_token}", "Content-Type": "application/json"},
                timeout=self._timeout,
            )
        except requests.ConnectTimeout as exc:
            # Nunca llegó a conectar: Meta no pudo recibir nada.
            raise MetaRechazoError(f"No se pudo conectar con Meta ({exc.__class__.__name__})") from None
        except requests.RequestException as exc:
            raise MetaRespuestaDudosaError(f"Se cortó la comunicación con Meta ({exc.__class__.__name__})") from None

        if resp.status_code >= 500:
            raise MetaRespuestaDudosaError(f"Meta respondió con un error de su servidor (HTTP {resp.status_code})")
        try:
            datos: Dict[str, Any] = resp.json()
        except ValueError:
            raise MetaRespuestaDudosaError(f"Respuesta ilegible de Meta (HTTP {resp.status_code})") from None

        if resp.status_code >= 400 or (isinstance(datos, dict) and "error" in datos):
            error = datos.get("error", {}) if isinstance(datos, dict) else {}
            detalle = f"{error.get('message', 'sin detalle')} (código {error.get('code', resp.status_code)})"
            raise MetaRechazoError(_recortar(f"Meta rechazó el evento: {detalle}"))

        return _recortar(json.dumps(datos, ensure_ascii=False))
