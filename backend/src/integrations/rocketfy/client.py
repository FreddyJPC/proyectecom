"""
Cliente HTTP para la API de Rocketfy.

Notas de diseño (ver Rocketfy-API-Integracion-Sistemas-Propios.md):
- Auth-user = sha256(correo de la cuenta) en hex minúscula; Auth-token =
  token de API tal cual lo entrega Rocketfy.
- La respuesta NO siempre trae un nodo "content": el ejemplo documentado de
  /orders/create trae "id" y "products_stock" al mismo nivel que ok/code/
  message, sin "content" — pese a que la sección 3.3 del doc dice que "la
  mayoría" de endpoints sí lo usan. Por eso este cliente NO intenta
  desenvolver "content" de forma genérica: cada método público hace su
  propia extracción, documentando qué asume. Ver PROGRESS.md, duda #11.
- Reintentos: solo ante HTTP 500 (vía urllib3 Retry) o ante un ok=0 cuyo
  mensaje indica mantenimiento transitorio (reintento manual con backoff).
  Cualquier otro ok=0 se trata como error de negocio definitivo.
"""
import hashlib
import time
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .constants import MENSAJE_MANTENIMIENTO
from .exceptions import RocketfyAuthError, RocketfyBusinessError, RocketfyRequestError


class RocketfyClient:
    def __init__(
        self,
        base_url: str,
        account_email: str,
        api_token: str,
        timeout: int = 20,
        max_retries: int = 3,
    ):
        self._base_url = base_url.rstrip("/")
        self._auth_user = hashlib.sha256(account_email.encode("utf-8")).hexdigest()
        self._api_token = api_token
        self._timeout = timeout
        self._max_retries = max_retries
        self._session = self._build_session()

    def _build_session(self) -> requests.Session:
        session = requests.Session()
        retry = Retry(
            total=self._max_retries,
            status_forcelist=[500],
            allowed_methods=["GET", "POST"],
            backoff_factor=1.0,
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def _headers(self) -> dict:
        return {
            "Auth-user": self._auth_user,
            "Auth-token": self._api_token,
            "Content-Type": "application/json",
        }

    def _call(self, method: str, path: str, payload: Optional[dict] = None) -> dict:
        url = f"{self._base_url}{path}"
        intento = 0

        while True:
            intento += 1
            try:
                resp = self._session.request(
                    method,
                    url,
                    json=payload if method == "POST" else None,
                    params=payload if method == "GET" else None,
                    headers=self._headers(),
                    timeout=self._timeout,
                )
            except requests.RequestException as exc:
                raise RocketfyRequestError(f"Error de red llamando a {path}: {exc}") from exc

            try:
                data = resp.json()
            except ValueError as exc:
                raise RocketfyRequestError(
                    f"Respuesta no-JSON de {path} (HTTP {resp.status_code})"
                ) from exc

            if resp.status_code == 401:
                raise RocketfyAuthError(
                    data.get("message", "Acceso denegado (401)")
                )

            ok = data.get("ok")
            mensaje = data.get("message", "")

            if ok == 0 and MENSAJE_MANTENIMIENTO in mensaje.lower() and intento <= self._max_retries:
                time.sleep(2 ** (intento - 1))
                continue

            if ok == 0:
                raise RocketfyBusinessError(
                    message=mensaje or "Error de negocio sin mensaje",
                    code=data.get("code", resp.status_code),
                    raw=data,
                )

            return data

    # ------------------------------------------------------------------
    # Fase 1 — Requerimiento 1: crear + confirmar pedido
    # ------------------------------------------------------------------
    def crear_pedido(self, payload: dict) -> dict:
        """POST /orders/create. Devuelve la respuesta completa: usar
        data['id'] (id Rocketfy) y data['products_stock'] (una entrada por
        cada SKU simple enviado; si faltan, alguna línea fue descartada en
        silencio por SKU inexistente)."""
        return self._call("POST", "/orders/create", payload)

    def confirmar_pedido(self, order_id: int = None, shopify_order_id: int = None) -> dict:
        """POST /orders/confirm. Un ok=0 aquí es un resultado de negocio
        esperado (sin cobertura, saldo insuficiente, etc.) — se propaga como
        RocketfyBusinessError para que la capa de servicio decida qué hacer
        según el mensaje (ver sección 5.1 del doc del proveedor)."""
        payload = {}
        if order_id is not None:
            payload["order_id"] = order_id
        if shopify_order_id is not None:
            payload["shopify_order_id"] = shopify_order_id
        return self._call("POST", "/orders/confirm", payload)

    # ------------------------------------------------------------------
    # Fase 1 — Requerimiento 3: sincronización de estados
    # ------------------------------------------------------------------
    def consultar_pedido(self, order_id: int) -> dict:
        """POST /orders/getInfo/{id}. Respuesta SIN nodo 'content': los datos
        cuelgan de data['order'], data['status_record'], data['incidence_details']."""
        return self._call("POST", f"/orders/getInfo/{order_id}")

    def consultar_pedidos_lote(self, id_start: int, id_end: int) -> dict:
        """POST /orders/bulk/getInfo. Mantener rangos acotados (unos pocos
        miles de IDs como máximo) — el proveedor advierte que el endpoint
        materializa todo el intervalo internamente."""
        return self._call(
            "POST", "/orders/bulk/getInfo", {"id_start": id_start, "id_end": id_end}
        )

    # ------------------------------------------------------------------
    # Fase 2 (adelantado) — Requerimiento 5: modificar / cancelar
    # ------------------------------------------------------------------
    def modificar_pedido(self, campos: dict) -> dict:
        """POST /orders/modify. Solo se aplican los campos enviados; el resto
        se conserva. No permite cambiar líneas de producto ni el total."""
        return self._call("POST", "/orders/modify", campos)

    def rechazar_pedido(self, order_id: int) -> dict:
        """POST /orders/reject. Posible hasta que se imprime la guía."""
        return self._call("POST", "/orders/reject", {"order_id": order_id})

    # ------------------------------------------------------------------
    # Fase 2 (adelantado) — Requerimientos 4 y 7: catálogo, precios, stock
    # ------------------------------------------------------------------
    def listar_productos(self, q: Optional[str] = None, page: int = 1) -> dict:
        """POST /products/list. Devuelve content['data'] (lista de productos)
        y content['pagination']."""
        payload = {"page": page}
        if q is not None:
            payload["q"] = q
        data = self._call("POST", "/products/list", payload)
        return data.get("content", {})

    def ver_producto(self, product_id: int) -> dict:
        """POST /products/view/{id}. Misma estructura de producto que listar_productos."""
        data = self._call("POST", f"/products/view/{product_id}")
        return data.get("content", {})

    # ------------------------------------------------------------------
    # Fase 2 (adelantado) — Requerimiento 6 (parcial): métricas
    # ------------------------------------------------------------------
    def estadisticas_generales(self) -> dict:
        """GET /statistics/general. NO es el saldo real de wallet — solo
        agregados (ver ADR-003 en PROGRESS.md)."""
        data = self._call("GET", "/statistics/general")
        return data.get("content", data)
