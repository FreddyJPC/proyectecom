"""
«Ya hice el pedido en Rocketfy» (pendiente #89, pedido de Freddy 2026-11-23).

Para qué: a veces el dueño crea el pedido A MANO en el panel de Rocketfy (p. ej. para elegir Servientrega, el retiro en una
agencia de su lista o la caja, cosas que la API no permite). Este sistema no se entera: la venta queda «recopilando datos»,
no cuenta en las métricas, el aviso «paquete en agencia» no sabe de quién es, y los botones «Continuar» o «Devolver»
podrían terminar en un SEGUNDO pedido real.

Aquí el dueño une ese pedido a la conversación:
  1. Elige el pedido de una lista (los pedidos de los que Rocketfy nos avisó por el webhook y que no son nuestros) o escribe
     su número.
  2. Se verifica con Rocketfy que existe en su cuenta y que es de ESTE cliente (mismo teléfono): un número mal escrito no
     puede unir el pedido de otra persona.
  3. Se guarda en `pedidos` con su número de Rocketfy (los avisos del webhook y la reconciliación lo siguen desde ahí), la venta
     pasa a «despachado» (y a «ganado», como cuando lo crea Victoria), se guarda la foto de la venta para los reportes y queda
     una nota interna en la conversación.

Nunca crea nada en Rocketfy: solo lee (`/orders/getInfo`). Lo que no coincide con lo acordado en el chat (el total, la ciudad)
no frena el registro: se devuelve como aviso para que el dueño lo revise.
"""
import logging
import re
import time
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from src.integrations.rocketfy import RocketfyAuthError, RocketfyBusinessError, RocketfyRequestError, get_rocketfy_client
from src.routes.entregas.repository import EntregaRepository
from src.routes.pedidos.repository import PedidoRepository
from src.routes.ventas.origen import es_de_cierre_manual
from src.routes.ventas.servicio import VentasService
from src.routes.whatsapp.repository import ConversacionRepository, LeadRepository, MensajeRepository, ProductoBotRepository

from .exceptions import ConversacionNoEncontradaError, PedidoYaCerradoError, SinPedidoEnCursoError

logger = logging.getLogger(__name__)

# Estados del lead en los que ya hay un pedido (o el dueño lo gestiona, o se canceló): no se une otro.
ESTADOS_SIN_PEDIDO_NUEVO = ("despachado", "por_gestionar", "cancelado")
# Cuántos días atrás se buscan pedidos sin unir, y cuántos se muestran.
DIAS_SIN_VINCULAR = 14
MAXIMO_SIN_VINCULAR = 20
ORIGEN_PANEL_ROCKETFY = "panel_rocketfy"


class PedidoExternoInvalidoError(Exception):
    """El pedido no se puede unir: no existe en Rocketfy, es de otro cliente, ya estaba registrado o es un producto propio."""


class RocketfyNoDisponibleError(Exception):
    """No se pudo consultar a Rocketfy (red, credenciales): no se guardó nada; se puede reintentar."""


def _digitos(telefono: Any) -> str:
    """Los últimos 9 dígitos: 0993669219, 593993669219 y +593 99 366 9219 son el mismo número."""
    return re.sub(r"\D", "", str(telefono or ""))[-9:]


def _dinero(valor: Any) -> Optional[Decimal]:
    try:
        return Decimal(str(valor)).quantize(Decimal("0.01")) if valor not in (None, "") else None
    except (InvalidOperation, ValueError):
        return None


def _normalizar(texto: Any) -> str:
    import unicodedata

    sin_tildes = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode()
    return " ".join(sin_tildes.lower().split())


class PedidoExternoService:
    def __init__(
        self,
        client=None,
        pedido_repo=None,
        lead_repo=None,
        conversacion_repo=None,
        mensaje_repo=None,
        producto_repo=None,
        entrega_repo=None,
        ventas=None,
    ):
        self._client_fijo = client
        self._pedidos = pedido_repo or PedidoRepository()
        self._leads = lead_repo or LeadRepository()
        self._conversaciones = conversacion_repo or ConversacionRepository()
        self._mensajes = mensaje_repo or MensajeRepository()
        self._productos = producto_repo or ProductoBotRepository()
        self._entregas = entrega_repo or EntregaRepository()
        self._ventas = ventas or VentasService()

    def _client(self):
        if self._client_fijo is None:
            self._client_fijo = get_rocketfy_client()
        return self._client_fijo

    def _conversacion(self, conversacion_id: int) -> dict:
        conversacion = self._conversaciones.obtener_por_id(conversacion_id)
        if conversacion is None:
            raise ConversacionNoEncontradaError(f"No existe una conversación con id={conversacion_id}.")
        return conversacion

    # ------------------------------------------------------------------
    def sin_vincular(self, conversacion_id: int) -> List[Dict[str, Any]]:
        """Los pedidos de Rocketfy que todavía no son de ninguna conversación (de los avisos del webhook), para elegir uno."""
        self._conversacion(conversacion_id)
        filas = self._pedidos.sin_vincular(dias=DIAS_SIN_VINCULAR, limite=MAXIMO_SIN_VINCULAR)
        resultado = []
        for fila in filas:
            payload = fila.get("payload") or {}
            total = _dinero(payload.get("total"))
            resultado.append({
                "idRocketfy": int(fila["id_rocketfy"]),
                "estado": payload.get("status_name") or None,
                "transportadora": payload.get("shipping_company") or None,
                "total": f"{total:.2f}" if total is not None else None,
                "ultimoAviso": fila["ultimo_aviso"].isoformat() if fila.get("ultimo_aviso") else None,
            })
        return resultado

    # ------------------------------------------------------------------
    def registrar(self, conversacion_id: int, id_rocketfy: int, usuario: Optional[str] = None) -> Dict[str, Any]:
        conversacion = self._conversacion(conversacion_id)
        lead = self._leads.obtener_por_conversacion(conversacion_id)
        if lead is None:
            raise SinPedidoEnCursoError("Esta conversación no tiene una venta en curso a la que unir el pedido.")
        if lead.get("estado") in ESTADOS_SIN_PEDIDO_NUEVO:
            # Nunca dos pedidos para la misma venta (ADR-007).
            raise PedidoYaCerradoError(
                "Esta venta ya tiene un pedido (o la gestionas tú, o se canceló): no se une otro."
            )

        producto = self._productos.obtener_por_sku(lead["producto_sku"]) if lead.get("producto_sku") else None
        if es_de_cierre_manual(producto):
            raise PedidoExternoInvalidoError("Este producto es propio: su venta no va por Rocketfy (está en «Por gestionar»).")

        existente = self._pedidos.obtener_por_id_rocketfy(id_rocketfy)
        if existente is not None:
            raise PedidoExternoInvalidoError(
                f"El pedido {id_rocketfy} de Rocketfy ya está registrado en el sistema (pedido #{existente['id_local']})."
            )

        orden = self._consultar_en_rocketfy(id_rocketfy)
        telefono_pedido = _digitos(orden.get("phone"))
        telefonos_cliente = {t for t in (_digitos(conversacion.get("id_externo")), _digitos(lead.get("telefono"))) if t}
        if telefono_pedido and telefonos_cliente and telefono_pedido not in telefonos_cliente:
            raise PedidoExternoInvalidoError(
                f"El pedido {id_rocketfy} de Rocketfy es de otro cliente ({orden.get('name') or 'sin nombre'}, "
                f"teléfono {orden.get('phone')}). Revisa el número."
            )

        total = _dinero(orden.get("total"))
        lineas = (
            [{"sku": lead["producto_sku"], "nombre": lead.get("producto_nombre") or lead["producto_sku"], "cantidad": int(lead.get("cantidad") or 1)}]
            if lead.get("producto_sku") else []
        )
        payload = {
            "origen": ORIGEN_PANEL_ROCKETFY,
            "registrado_por": usuario,
            "nombre_cliente": orden.get("name") or lead.get("nombre_cliente") or "",
            "telefono": orden.get("phone") or lead.get("telefono") or "",
            "direccion": orden.get("address") or "",
            "canton": orden.get("city") or lead.get("canton") or "",
            "provincia": orden.get("province") or lead.get("provincia") or "",
            "total": f"{total:.2f}" if total is not None else (str(lead.get("total")) if lead.get("total") is not None else "0"),
            "lineas": lineas,
        }
        estado_local = "confirmado" if orden.get("confirmed_at") else "creado"
        status_id = self._pedidos.ultimo_status_avisado(id_rocketfy)

        id_local = self._guardar(id_rocketfy, estado_local, status_id, payload)

        # Desde aquí el pedido YA está guardado: lo que falle después se registra, no se responde error (se reintentaría y se
        # intentaría guardar otra vez).
        try:
            self._leads.actualizar_despacho(lead["id"], id_pedido_local=id_local, id_pedido_rocketfy=id_rocketfy)
        except Exception:  # noqa: BLE001
            logger.exception("Pedido de Rocketfy registrado pero no se pudo cerrar su venta", extra={"conversacion_id": conversacion_id})
        self._registrar_venta(lead["id"], conversacion, producto)
        self._dejar_nota(conversacion_id, id_rocketfy)

        return {
            "idLocal": id_local,
            "idRocketfy": id_rocketfy,
            "estado": estado_local,
            "total": payload["total"],
            "avisos": self._diferencias(lead, orden, total),
        }

    # ------------------------------------------------------------------
    def _consultar_en_rocketfy(self, id_rocketfy: int) -> dict:
        try:
            respuesta = self._client().consultar_pedido(id_rocketfy)
        except RocketfyBusinessError as exc:
            raise PedidoExternoInvalidoError(
                f"Rocketfy no encuentra el pedido {id_rocketfy} en tu cuenta ({exc.message}). Revisa el número."
            ) from exc
        except (RocketfyRequestError, RocketfyAuthError) as exc:
            raise RocketfyNoDisponibleError(f"No se pudo consultar a Rocketfy: {exc}. No se guardó nada; intenta otra vez.") from exc
        orden = (respuesta or {}).get("order") or {}
        if not orden:
            raise PedidoExternoInvalidoError(f"Rocketfy no devolvió los datos del pedido {id_rocketfy}. Revisa el número.")
        return orden

    def _guardar(self, id_rocketfy: int, estado_local: str, status_id: Optional[int], payload: dict) -> int:
        """`id_local` es la hora en segundos, como en los pedidos que crea Victoria; si choca con otro, se prueba el siguiente."""
        base = int(time.time())
        for desfase in range(20):
            if self._pedidos.insertar_externo(base + desfase, id_rocketfy, estado_local, status_id, payload):
                return base + desfase
            if self._pedidos.obtener_por_id_rocketfy(id_rocketfy) is not None:
                # Otro clic (o el dueño en otra pestaña) lo registró en este mismo momento.
                raise PedidoExternoInvalidoError(f"El pedido {id_rocketfy} de Rocketfy ya está registrado en el sistema.")
        raise PedidoExternoInvalidoError("No se pudo guardar el pedido en este momento. Intenta otra vez.")

    def _registrar_venta(self, lead_id: int, conversacion: dict, producto: Optional[dict]) -> None:
        """La «foto» de la venta para los reportes, como cuando el pedido lo crea Victoria. Best-effort: el pedido ya está."""
        if producto is None:
            return
        try:
            lead = self._leads.obtener_por_id(lead_id)
            entrega = self._entregas.obtener(lead["entrega_opcion_id"]) if lead.get("entrega_opcion_id") else None
            self._ventas.registrar_venta_rocketfy(lead, producto, conversacion, entrega, productos=self._productos_del_pedido(lead, producto))
        except Exception:  # noqa: BLE001
            logger.exception("No se pudo registrar la venta del lead %s (pedido hecho en el panel de Rocketfy)", lead_id)

    def _productos_del_pedido(self, lead: dict, principal: dict) -> Dict[str, dict]:
        """Las filas de todos los productos del pedido (un pedido con varias líneas, ADR-017), igual que al cerrar con Victoria."""
        filas = {principal["sku"]: principal}
        for linea in (lead.get("cotizacion") or {}).get("lineas") or []:
            for item in linea.get("items") or []:
                if item.get("sku") and item["sku"] not in filas:
                    fila = self._productos.obtener_por_sku(item["sku"])
                    if fila is not None:
                        filas[item["sku"]] = fila
        return filas

    def _dejar_nota(self, conversacion_id: int, id_rocketfy: int) -> None:
        """Nota interna en el chat (el cliente nunca la ve): el dueño la ve en el historial y, si le devuelve la conversación a
        Victoria, ella sabe que el pedido ya existe y no crea otro."""
        try:
            self._mensajes.crear(
                conversacion_id=conversacion_id,
                rol="sistema",
                contenido=(
                    f"[Aviso interno del sistema, no lo escribió el cliente: el dueño creó el pedido de este cliente a mano en el "
                    f"panel de Rocketfy (pedido {id_rocketfy}) y lo registró aquí. La venta ya está cerrada: no crees otro pedido.]"
                ),
                tipo="texto",
                wamid=None,
            )
        except Exception:  # noqa: BLE001
            logger.warning("No se pudo dejar la nota del pedido hecho a mano", exc_info=True, extra={"conversacion_id": conversacion_id})

    @staticmethod
    def _diferencias(lead: dict, orden: dict, total: Optional[Decimal]) -> List[str]:
        """Lo que no coincide entre lo acordado en el chat y lo que se cargó en Rocketfy: no frena nada, solo avisa."""
        avisos = []
        acordado = _dinero(lead.get("total"))
        if total is not None and acordado is not None and total != acordado:
            avisos.append(f"Rocketfy va a cobrar ${total:.2f}; en el chat se acordó ${acordado:.2f}.")
        if orden.get("city") and lead.get("canton") and _normalizar(orden["city"]) != _normalizar(lead["canton"]):
            avisos.append(f"La ciudad en Rocketfy es «{orden['city']}» y en el chat «{lead['canton']}».")
        return avisos
