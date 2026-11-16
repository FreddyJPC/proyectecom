"""
Cliente de la API de Marketing de Meta (ADR-017, plan v2.0 §6.2): leer los anuncios de la cuenta publicitaria y su gasto diario, y
PAUSAR un anuncio. Es lo único que habla con esa API.

Notas de diseño:
- Usa el mismo token del usuario del sistema que el aviso de ventas (regla D5: el nivel sin revisión permite un solo usuario del
  sistema). Necesita los permisos `ads_read` (leer) y `ads_management` (pausar) y que el usuario tenga asignada la cuenta publicitaria.
- Leer no tiene efectos: cualquier fallo es «inténtalo en la próxima pasada» (`MetaRechazoError`).
- Pausar SÍ tiene efecto: si no se sabe si Meta lo hizo (se cortó, tardó, error 5xx), es `MetaRespuestaDudosaError` y quien llama
  debe leer el estado del anuncio antes de volver a intentar. Nunca se reactiva un anuncio ni se toca un presupuesto desde aquí.
- El token va en el encabezado, nunca en la dirección, y jamás en un mensaje de error (de `requests` solo se usa el nombre de la clase).
- Límites (documentación «Marketing API Rate Limiting», leída el 2026-11-16): en el nivel Limited, por cuenta y hora, unas
  600 + 400 × anuncios activos lecturas de resultados: leer una vez por hora gasta unos pocos puntos.
"""
import json
import logging
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Iterator, List, Optional

import requests

from .client import GRAPH_API_VERSION, MetaRechazoError, MetaRespuestaDudosaError

logger = logging.getLogger(__name__)

ACCION_CONVERSACION = "onsite_conversion.messaging_conversation_started_7d"
_CAMPOS_ANUNCIO = (
    "id,name,status,effective_status,adset{id,name,daily_budget},campaign{id,name},creative{title,body,thumbnail_url}"
)
_MAXIMO_PAGINAS = 20


def _decimal(valor: Any) -> Decimal:
    try:
        return Decimal(str(valor or "0")).quantize(Decimal("0.01"))
    except InvalidOperation:
        return Decimal("0.00")


def _entero(valor: Any) -> int:
    try:
        return int(Decimal(str(valor or "0")))
    except InvalidOperation:
        return 0


def normalizar_cuenta(cuenta: str) -> str:
    """«act_123», «123» o « 123 » -> «123». Solo dígitos (si no, vacío)."""
    limpio = (cuenta or "").strip()
    if limpio.startswith("act_"):
        limpio = limpio[4:]
    return limpio if limpio.isdigit() else ""


def anuncio_desde_meta(fila: Dict[str, Any]) -> Dict[str, Any]:
    conjunto = fila.get("adset") or {}
    campana = fila.get("campaign") or {}
    creativo = fila.get("creative") or {}
    presupuesto = conjunto.get("daily_budget")
    return {
        "id_anuncio": str(fila.get("id")),
        "nombre": fila.get("name"),
        "estado": fila.get("status"),
        "estado_efectivo": fila.get("effective_status"),
        "id_conjunto": conjunto.get("id"),
        "nombre_conjunto": conjunto.get("name"),
        # Meta da el presupuesto en la unidad mínima de la moneda (centavos de dólar).
        "presupuesto_diario": (_decimal(presupuesto) / 100).quantize(Decimal("0.01")) if presupuesto not in (None, "") else None,
        "id_campana": campana.get("id"),
        "nombre_campana": campana.get("name"),
        "titulo": creativo.get("title"),
        "texto": creativo.get("body"),
        "miniatura_url": creativo.get("thumbnail_url"),
    }


def metrica_desde_meta(fila: Dict[str, Any]) -> Dict[str, Any]:
    conversaciones = 0
    for accion in fila.get("actions") or []:
        if accion.get("action_type") == ACCION_CONVERSACION:
            conversaciones = _entero(accion.get("value"))
    return {
        "id_anuncio": str(fila.get("ad_id")),
        "fecha": fila.get("date_start"),
        "gasto": _decimal(fila.get("spend")),
        "impresiones": _entero(fila.get("impressions")),
        "clics": _entero(fila.get("clicks")),
        "conversaciones": conversaciones,
    }


class MetaMarketingClient:
    def __init__(self, access_token: str, cuenta_publicitaria: str, timeout: int = 30):
        self._token = access_token
        self._cuenta = normalizar_cuenta(cuenta_publicitaria)
        self._timeout = timeout
        self._session = requests.Session()

    @property
    def _base(self) -> str:
        return f"https://graph.facebook.com/{GRAPH_API_VERSION}"

    def _encabezados(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    def _leer(self, url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        try:
            resp = self._session.get(url, params=params, headers=self._encabezados(), timeout=self._timeout)
        except requests.RequestException as exc:
            raise MetaRechazoError(f"No se pudo leer de Meta ({exc.__class__.__name__})") from None
        try:
            datos = resp.json()
        except ValueError:
            raise MetaRechazoError(f"Respuesta ilegible de Meta (HTTP {resp.status_code})") from None
        if resp.status_code >= 400 or (isinstance(datos, dict) and "error" in datos):
            error = datos.get("error", {}) if isinstance(datos, dict) else {}
            raise MetaRechazoError(f"Meta rechazó la lectura: {error.get('message', 'sin detalle')} (código {error.get('code', resp.status_code)})"[:500])
        return datos if isinstance(datos, dict) else {}

    def _paginas(self, url: str, params: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
        datos = self._leer(url, params)
        for _ in range(_MAXIMO_PAGINAS):
            for fila in datos.get("data") or []:
                yield fila
            siguiente = (datos.get("paging") or {}).get("next")
            if not siguiente:
                return
            datos = self._leer(siguiente)

    def listar_anuncios(self) -> List[Dict[str, Any]]:
        if not self._cuenta:
            raise MetaRechazoError("Falta la cuenta publicitaria (Conexión con Meta)")
        url = f"{self._base}/act_{self._cuenta}/ads"
        return [anuncio_desde_meta(f) for f in self._paginas(url, {"fields": _CAMPOS_ANUNCIO, "limit": 200})]

    def metricas_diarias(self, desde: date, hasta: date) -> List[Dict[str, Any]]:
        if not self._cuenta:
            raise MetaRechazoError("Falta la cuenta publicitaria (Conexión con Meta)")
        url = f"{self._base}/act_{self._cuenta}/insights"
        params = {
            "level": "ad",
            "fields": "ad_id,spend,impressions,clicks,actions",
            "time_increment": 1,
            "time_range": json.dumps({"since": desde.isoformat(), "until": hasta.isoformat()}),
            "limit": 500,
        }
        return [metrica_desde_meta(f) for f in self._paginas(url, params)]

    def estado_de_anuncio(self, id_anuncio: str) -> Optional[str]:
        datos = self._leer(f"{self._base}/{id_anuncio}", {"fields": "status"})
        return datos.get("status")

    def pausar_anuncio(self, id_anuncio: str) -> None:
        """Pausa un anuncio. `MetaRechazoError` = Meta dijo que no (no cambió nada); `MetaRespuestaDudosaError` = no se sabe."""
        try:
            resp = self._session.post(
                f"{self._base}/{id_anuncio}", data={"status": "PAUSED"}, headers=self._encabezados(), timeout=self._timeout
            )
        except requests.ConnectTimeout as exc:
            raise MetaRechazoError(f"No se pudo conectar con Meta ({exc.__class__.__name__})") from None
        except requests.RequestException as exc:
            raise MetaRespuestaDudosaError(f"Se cortó la comunicación con Meta ({exc.__class__.__name__})") from None
        if resp.status_code >= 500:
            raise MetaRespuestaDudosaError(f"Meta respondió con un error de su servidor (HTTP {resp.status_code})")
        try:
            datos = resp.json()
        except ValueError:
            raise MetaRespuestaDudosaError(f"Respuesta ilegible de Meta (HTTP {resp.status_code})") from None
        if resp.status_code >= 400 or (isinstance(datos, dict) and "error" in datos):
            error = datos.get("error", {}) if isinstance(datos, dict) else {}
            raise MetaRechazoError(f"Meta no pausó el anuncio: {error.get('message', 'sin detalle')} (código {error.get('code', resp.status_code)})"[:500])
        if not (isinstance(datos, dict) and datos.get("success")):
            raise MetaRespuestaDudosaError("Meta respondió sin confirmar la pausa")
