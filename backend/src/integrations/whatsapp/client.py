"""
Cliente HTTP para la Cloud API de WhatsApp (Meta).

Notas de diseño:
- Un cliente = un número de teléfono (phone_number_id). Los tres métodos
  llaman al mismo endpoint POST /{phone_number_id}/messages con distinto
  body -- a diferencia de Rocketfy, acá no hay operaciones GET salientes.
- A diferencia de RocketfyClient, NO hay reintento automático ante 5xx:
  reintentar un envío de mensaje a un cliente real podría duplicarlo -- se
  prefiere fallar y que la capa de servicio decida, no reintentar a ciegas
  (mismo principio que la advertencia de Rocketfy sobre /orders/create).
- El cuerpo de error de Meta siempre viene en data["error"] (message, type,
  code, fbtrace_id), tanto para 401 como para 400 -- Graph API usa el mismo
  sobre para cualquier código de error.
"""
from typing import List, Optional

import requests

from .exceptions import WhatsAppAuthError, WhatsAppBusinessError, WhatsAppRequestError

_GRAPH_API_VERSION = "v21.0"


class WhatsAppClient:
    def __init__(self, phone_number_id: str, api_token: str, timeout: int = 20):
        self._url = f"https://graph.facebook.com/{_GRAPH_API_VERSION}/{phone_number_id}/messages"
        self._api_token = api_token
        self._timeout = timeout
        self._session = requests.Session()

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._api_token}",
            "Content-Type": "application/json",
        }

    def _post(self, payload: dict) -> dict:
        try:
            resp = self._session.post(self._url, json=payload, headers=self._headers(), timeout=self._timeout)
        except requests.RequestException as exc:
            raise WhatsAppRequestError(f"Error de red llamando a WhatsApp Cloud API: {exc}") from exc

        try:
            data = resp.json()
        except ValueError as exc:
            raise WhatsAppRequestError(
                f"Respuesta no-JSON de WhatsApp Cloud API (HTTP {resp.status_code})"
            ) from exc

        if resp.status_code == 401:
            error = data.get("error", {})
            raise WhatsAppAuthError(error.get("message", "Acceso denegado (401)"))

        if resp.status_code == 400:
            error = data.get("error", {})
            raise WhatsAppBusinessError(
                message=error.get("message", "Error de negocio sin mensaje"),
                code=error.get("code", resp.status_code),
                raw=data,
            )

        if resp.status_code >= 400:
            raise WhatsAppRequestError(f"HTTP {resp.status_code} inesperado de WhatsApp Cloud API: {data}")

        return data

    def enviar_texto(self, telefono: str, mensaje: str) -> dict:
        """POST .../messages, type=text. La respuesta exitosa trae
        messages[0]['id'] -- el wamid que WhatsApp asigna a ESTE envío
        nuestro (no confundir con el wamid del mensaje entrante que se está
        respondiendo)."""
        payload = {
            "messaging_product": "whatsapp",
            "to": telefono,
            "type": "text",
            "text": {"body": mensaje},
        }
        return self._post(payload)

    def enviar_plantilla(self, telefono: str, nombre_plantilla: str, variables: Optional[List[str]] = None) -> dict:
        """POST .../messages, type=template. Única forma permitida de
        escribirle primero a un cliente, o de reabrir la conversación tras
        24h sin respuesta -- Meta exige plantillas pre-aprobadas para eso
        (ver docs/BotPlanifiacion.md, sección 4, Flujo 2)."""
        payload = {
            "messaging_product": "whatsapp",
            "to": telefono,
            "type": "template",
            "template": {
                "name": nombre_plantilla,
                "language": {"code": "es"},
                "components": [
                    {
                        "type": "body",
                        "parameters": [{"type": "text", "text": variable} for variable in (variables or [])],
                    }
                ],
            },
        }
        return self._post(payload)

    def marcar_como_leido(self, wamid: str) -> dict:
        """POST .../messages, status=read. Marca el mensaje ENTRANTE del
        cliente (identificado por su wamid) como leído -- el cliente ve los
        dos ticks azules."""
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": wamid,
        }
        return self._post(payload)
