"""
Las herramientas (tool use) que Victoria puede invocar durante la
conversación, en vez de devolver un JSON de estado en texto libre. Los
esquemas están en el formato neutral HerramientaLLM (Tarea 3) -- nunca en
el formato de wire de un proveedor específico.

Nota de diseño sobre ResultadoHerramienta.id_llamada: los métodos privados
_handle_* devuelven solo el texto (str) que Victoria necesita ver -- el
id de la llamada (LlamadaHerramienta.id) no existe todavía en su firma
(Tarea 4 del encargo), solo lo tiene quien orquesta el loop
(VictoriaConversationService, Tarea 6). `ejecutar()` es el punto público
que junta ambas cosas y arma el ResultadoHerramienta completo -- es lo
que Tarea 6 llama y lo que los tests de esta tarea ejercitan.

Nota de diseño sobre errores de Rocketfy en cerrar_venta: el encargo
describe el manejo de errores como "409 ambiguo" vs "422 regla de
negocio", pero PedidoService.crear_y_confirmar() no expone códigos HTTP
en esa capa -- lanza 5 excepciones tipadas propias. Como el principio del
encargo es que TODO fallo de Rocketfy escala igual a un humano sin
importar la categoría, acá se capturan las cinco en un único bloque y se
escala siempre con el mensaje de la excepción como motivo (ver
PROGRESS.md, Fase 3.2, para el detalle completo de esta decisión).
"""
import logging
import time
import unicodedata
from decimal import Decimal
from typing import Optional

from src.integrations.llm.contratos import HerramientaLLM, ResultadoHerramienta
from src.integrations.rocketfy import RocketfyBusinessError, get_rocketfy_client
from src.integrations.telegram import TelegramNotifier, get_telegram_notifier
from src.routes.pedidos.dto import CrearPedidoInputDTO, LineaPedidoDTO
from src.routes.pedidos.exceptions import (
    PedidoEnEstadoAmbiguoError,
    PedidoIncompletoError,
    RecaudoMinimoNoAlcanzadoError,
    UbicacionNoResueltaError,
)
from src.routes.pedidos.services import PedidoService

from .repository import ConversacionRepository, LeadRepository, ProductoBotRepository

logger = logging.getLogger(__name__)

_ERRORES_ROCKETFY_QUE_ESCALAN = (
    PedidoEnEstadoAmbiguoError,
    PedidoIncompletoError,
    UbicacionNoResueltaError,
    RecaudoMinimoNoAlcanzadoError,
    RocketfyBusinessError,
)

def _normalizar_texto(texto: str) -> str:
    sin_acentos = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return sin_acentos.strip().lower()


def _telefono_formato_rocketfy(telefono_whatsapp: str) -> str:
    """WhatsApp entrega el teléfono en formato internacional con código
    de país (593XXXXXXXXX, 12 dígitos) -- Rocketfy exige formato local
    ecuatoriano sin código de país (9-10 dígitos). Se descubrió probando
    un cierre de venta real contra la API real de Rocketfy (Fase 3.2):
    nunca antes un teléfono que viniera de WhatsApp había llegado a
    PedidoService, así que este desajuste no se había manifestado."""
    if telefono_whatsapp.startswith("593") and len(telefono_whatsapp) == 12:
        return telefono_whatsapp[3:]
    return telefono_whatsapp


_CAMPOS_REQUERIDOS_CIERRE = (
    "nombre_cliente",
    "direccion",
    "canton",
    "provincia",
    "producto_sku",
    "producto_nombre",
    "total",
    "metodo_pago",
)

HERRAMIENTAS_VICTORIA = [
    HerramientaLLM(
        nombre="guardar_datos_cliente",
        descripcion=(
            "Guarda o actualiza los datos de contacto y envío del cliente "
            "a medida que los va confirmando en la conversación. Llama esta "
            "herramienta cada vez que el cliente confirme un dato nuevo — "
            "no esperes a tener todos los datos para llamarla."
        ),
        parametros={
            "type": "object",
            "properties": {
                "nombre_cliente": {"type": "string"},
                "direccion": {"type": "string"},
                "canton": {"type": "string"},
                "provincia": {"type": "string"},
            },
        },
    ),
    HerramientaLLM(
        nombre="registrar_producto",
        descripcion=(
            "Registra qué producto quiere comprar el cliente, el total a "
            "cobrar, y la variante si el producto tiene (color, talla, etc. "
            "— revisa la sección de variantes en tu información del "
            "producto). Llámala en cuanto el cliente confirme el producto. "
            "Si el producto tiene variantes y el cliente aún no eligió, "
            "pregúntale UNA vez cuál prefiere — pero si no logras que lo "
            "confirme con claridad, registra el producto igual sin variante "
            "y sigue adelante. La variante nunca es motivo para escalar ni "
            "para detener el cierre de la venta. IMPORTANTE: producto_sku "
            "debe ser copiado EXACTO, carácter por carácter, del SKU que "
            "aparece en la información del producto de tu system prompt — "
            "nunca lo inventes, abrevies, ni le des un formato distinto."
        ),
        parametros={
            "type": "object",
            "properties": {
                "producto_sku": {"type": "string"},
                "producto_nombre": {"type": "string"},
                "variante": {
                    "type": "string",
                    "description": (
                        "Color, talla u otra variante elegida, si aplica. "
                        "Omitir si no aplica o el cliente no especificó."
                    ),
                },
                "total": {
                    "type": "number",
                    "description": "Precio total en dólares, hasta 2 decimales",
                },
            },
            "required": ["producto_sku", "producto_nombre", "total"],
        },
    ),
    HerramientaLLM(
        nombre="registrar_metodo_pago",
        descripcion="Registra cómo va a pagar el cliente.",
        parametros={
            "type": "object",
            "properties": {
                "metodo_pago": {
                    "type": "string",
                    "enum": ["contraentrega", "transferencia"],
                },
            },
            "required": ["metodo_pago"],
        },
    ),
    HerramientaLLM(
        nombre="cerrar_venta",
        descripcion=(
            "Cierra la venta y dispara el envío del pedido. Solo llama esta "
            "herramienta cuando tengas confirmados TODOS estos datos: "
            "nombre del cliente, dirección completa, cantón, provincia, "
            "producto y método de pago. Si el método de pago es "
            "transferencia, esta herramienta te va a decir que falta "
            "verificar el comprobante. No la llames si falta cualquier dato."
        ),
        parametros={"type": "object", "properties": {}},
    ),
    HerramientaLLM(
        nombre="escalar_a_humano",
        descripcion=(
            "Transfiere la conversación a un asesor humano y deja de "
            "responder automáticamente. Úsala cuando: el cliente pregunta "
            "algo que no está en tu información del producto, pide "
            "explícitamente hablar con una persona, no puedes interpretar "
            "con confianza lo que quiere, o cualquier situación ambigua. "
            "Nunca inventes información — si dudas, escala."
        ),
        parametros={
            "type": "object",
            "properties": {
                "motivo": {
                    "type": "string",
                    "description": "Breve explicación de por qué se escala.",
                },
            },
            "required": ["motivo"],
        },
    ),
]


class HerramientasVictoria:
    def __init__(
        self,
        lead_repo: Optional[LeadRepository] = None,
        conversacion_repo: Optional[ConversacionRepository] = None,
        producto_repo: Optional[ProductoBotRepository] = None,
        pedido_service: Optional[PedidoService] = None,
        telegram_notifier: Optional[TelegramNotifier] = None,
    ):
        self._leads = lead_repo or LeadRepository()
        self._conversaciones = conversacion_repo or ConversacionRepository()
        self._productos = producto_repo or ProductoBotRepository()
        self._pedidos = pedido_service or PedidoService(client=get_rocketfy_client())
        self._telegram = telegram_notifier or get_telegram_notifier()
        self._manejadores = {
            "guardar_datos_cliente": self._handle_guardar_datos_cliente,
            "registrar_producto": self._handle_registrar_producto,
            "registrar_metodo_pago": self._handle_registrar_metodo_pago,
            "cerrar_venta": self._handle_cerrar_venta,
            "escalar_a_humano": self._handle_escalar_a_humano,
        }

    def ejecutar(self, nombre: str, lead_id: int, conversacion_id: int, entrada: dict, id_llamada: str) -> ResultadoHerramienta:
        manejador = self._manejadores.get(nombre)
        if manejador is None:
            contenido = f"Herramienta desconocida: {nombre}."
        else:
            contenido = manejador(lead_id, conversacion_id, entrada)
        return ResultadoHerramienta(id_llamada=id_llamada, contenido=contenido)

    def _handle_guardar_datos_cliente(self, lead_id: int, conversacion_id: int, entrada: dict) -> str:
        self._leads.actualizar_datos_cliente(
            lead_id,
            nombre_cliente=entrada.get("nombre_cliente"),
            direccion=entrada.get("direccion"),
            canton=entrada.get("canton"),
            provincia=entrada.get("provincia"),
        )
        return "Datos guardados correctamente."

    def _handle_registrar_producto(self, lead_id: int, conversacion_id: int, entrada: dict) -> str:
        # El LLM no siempre copia el SKU exacto tal como aparece en el
        # catálogo (probado en la práctica: a veces lo inventa, a veces
        # manda el nombre en el campo sku, a veces un placeholder tipo
        # "N/A") -- se intenta primero el match exacto por SKU y, si
        # falla, un fuzzy-match por nombre (sin distinguir tildes/mayúsculas)
        # contra productos_bot antes de guardar nada. Nunca debe llegar un
        # SKU inventado hasta cerrar_venta, que se lo pasa tal cual a
        # Rocketfy.
        sku = entrada["producto_sku"]
        nombre = entrada["producto_nombre"]

        producto_real = self._productos.obtener_por_sku(sku)
        if producto_real is None:
            producto_real = self._buscar_producto_activo_por_nombre(nombre)
            if producto_real is not None:
                logger.warning(
                    "producto_sku del LLM ('%s') no coincide con ningún producto real -- corregido a '%s' por nombre",
                    sku, producto_real["sku"],
                    extra={"lead_id": lead_id, "conversacion_id": conversacion_id},
                )

        if producto_real is None:
            # Resiliencia: si tampoco el fuzzy-match por nombre encuentra
            # nada, no se adivina ni se guarda cualquier cosa -- se le
            # devuelve a Victoria la lista real de productos disponibles
            # para que le pregunte de nuevo al cliente en el mismo turno.
            logger.warning(
                "registrar_producto no encontró ningún producto real para sku=%r nombre=%r -- no se guarda nada",
                sku, nombre,
                extra={"lead_id": lead_id, "conversacion_id": conversacion_id},
            )
            activos = self._productos.listar_activos()
            lista = ", ".join(f"{p['nombre']} ({p['sku']}): ${p['precio']}" for p in activos)
            return (
                "No encontré ese producto en el catálogo. Los productos disponibles ahora son: "
                f"{lista}. Pregúntale al cliente cuál de estos quiere antes de registrar de nuevo."
            )

        self._leads.actualizar_producto(
            lead_id,
            producto_sku=producto_real["sku"],
            producto_nombre=producto_real["nombre"],
            total=Decimal(str(entrada["total"])),
            variante=entrada.get("variante"),
        )
        return "Producto registrado."

    def _buscar_producto_activo_por_nombre(self, nombre: str) -> Optional[dict]:
        nombre_normalizado = _normalizar_texto(nombre)
        for producto in self._productos.listar_activos():
            if _normalizar_texto(producto["nombre"]) == nombre_normalizado:
                return producto
        return None

    def _handle_registrar_metodo_pago(self, lead_id: int, conversacion_id: int, entrada: dict) -> str:
        self._leads.actualizar_metodo_pago(lead_id, metodo_pago=entrada["metodo_pago"])
        if entrada["metodo_pago"] == "transferencia":
            # Espejo a nivel conversación -- el módulo de Conversaciones
            # del dashboard filtra/cuenta "esperando_pago" sobre
            # conversaciones.estado, no sobre leads.estado.
            self._conversaciones.marcar_esperando_pago(conversacion_id)
        return "Método de pago registrado."

    def _handle_cerrar_venta(self, lead_id: int, conversacion_id: int, entrada: dict) -> str:
        lead = self._leads.obtener_por_id(lead_id)
        faltantes = [campo for campo in _CAMPOS_REQUERIDOS_CIERRE if not lead.get(campo)]
        if faltantes:
            return f"Faltan datos: {', '.join(faltantes)}. Pide esos datos al cliente antes de intentar cerrar de nuevo."

        if lead["metodo_pago"] == "transferencia":
            return (
                "Este pedido es por transferencia. Pide al cliente la foto del comprobante "
                "antes de continuar. No se puede cerrar todavía."
            )

        producto = self._productos.obtener_por_sku(lead["producto_sku"])
        tiempo_entrega = producto["tiempo_entrega"] if producto else "los próximos días"

        # CrearPedidoInputDTO.lineas no tiene campo propio para variante
        # (solo sku/nombre/cantidad) -- para que la variante llegue de
        # verdad al repartidor (y no se quede solo en nuestra tabla), se
        # incluye como sufijo del nombre de la línea, sin tocar el
        # contrato de Rocketfy.
        nombre_linea = lead["producto_nombre"]
        if lead.get("producto_variante"):
            nombre_linea = f"{lead['producto_nombre']} - {lead['producto_variante']}"

        dto = CrearPedidoInputDTO(
            id_local=int(time.time()),
            nombre_cliente=lead["nombre_cliente"],
            telefono=_telefono_formato_rocketfy(lead["telefono"]),
            direccion=lead["direccion"],
            canton=lead["canton"],
            provincia=lead["provincia"],
            total=lead["total"],
            lineas=[LineaPedidoDTO(sku=lead["producto_sku"], nombre=nombre_linea, cantidad=1)],
            no_contra_entrega=False,
        )

        try:
            resultado = self._pedidos.crear_y_confirmar(dto)
        except _ERRORES_ROCKETFY_QUE_ESCALAN as exc:
            # Cerrar una venta real es el punto de máximo riesgo: el
            # manejo de este fallo es código determinista, nunca se deja
            # que Victoria decida cómo reaccionar.
            logger.warning(
                "Fallo confirmando pedido en Rocketfy, se escala a humano: %s", exc,
                extra={"lead_id": lead_id, "conversacion_id": conversacion_id},
            )
            self._handle_escalar_a_humano(
                lead_id, conversacion_id, {"motivo": f"Rocketfy no pudo confirmar el pedido: {exc}"}
            )
            return (
                "Hubo un problema técnico confirmando el pedido con nuestro proveedor de envíos. "
                "Ya se avisó a un asesor humano — dile al cliente que en breve le confirman."
            )

        self._leads.actualizar_despacho(
            lead_id, id_pedido_local=resultado.id_local, id_pedido_rocketfy=resultado.id_rocketfy
        )
        return f"¡Pedido confirmado! Llega en {tiempo_entrega}. Comunícaselo al cliente y agradécele."

    def _handle_escalar_a_humano(self, lead_id: int, conversacion_id: int, entrada: dict) -> str:
        self._conversaciones.marcar_escalada(conversacion_id)
        lead = self._leads.obtener_por_id(lead_id)
        telefono = lead["telefono"] if lead else ""
        self._telegram.notificar_escalado(conversacion_id, telefono, entrada.get("motivo", "sin especificar"))
        return (
            "Escalado correctamente. Este es tu último mensaje — despídete cordialmente "
            "informando que un asesor la va a contactar en breve."
        )
