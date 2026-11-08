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
from decimal import Decimal, InvalidOperation
from typing import List, Optional, Tuple

from src.config.parametros import parametros
from src.integrations.llm.contratos import HerramientaLLM, ResultadoHerramienta
from src.integrations.rocketfy import RocketfyBusinessError, get_rocketfy_client
from src.integrations.rocketfy.imagenes import url_de_imagen
from src.integrations.telegram import TelegramNotifier, get_telegram_notifier
from src.integrations.whatsapp import get_whatsapp_client
from src.routes.pedidos.dto import CrearPedidoInputDTO, LineaPedidoDTO
from src.routes.pedidos.exceptions import (
    PedidoEnEstadoAmbiguoError,
    PedidoIncompletoError,
    RecaudoMinimoNoAlcanzadoError,
    UbicacionNoResueltaError,
)
from src.routes.pedidos.services import PedidoService
from src.routes.entregas.logica import describir, elegir_opcion, opciones_aplicables, total_con_envio
from src.routes.entregas.repository import EntregaRepository
from src.routes.gestion.services import GestionService
from src.routes.gestion.tipos import TIPOS_QUE_PIDE_VICTORIA
from src.routes.imagenes.logica import galeria_para_enviar
from src.routes.imagenes.repository import ImagenRepository
from src.routes.ventas.exceptions import StockInsuficienteError, VentaYaRegistradaError
from src.routes.ventas.origen import controla_su_stock, es_de_cierre_manual
from src.routes.ventas.servicio import VentasService

from .ficha import formatear_ficha_producto
from .minimos import extraer_minimo_rocketfy
from .repository import ConversacionRepository, LeadRepository, MensajeRepository, MinimoObservadoRepository, ProductoBotRepository
from .stock import StockChecker

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


def _leer_cantidad(valor) -> Optional[int]:
    """Cantidad pedida por el LLM -> entero >= 1, o None si no es válida.
    Acepta 2, 2.0 y "2"; rechaza 0, negativos, fracciones y texto."""
    if valor is None:
        return 1
    if isinstance(valor, bool):
        return None
    try:
        numero = Decimal(str(valor).strip())
    except InvalidOperation:
        return None
    if numero != numero.to_integral_value() or numero < 1:
        return None
    return int(numero)


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


# Estados de un lead que ya cerró su venta: no se cierra de nuevo.
ESTADOS_DE_LEAD_CERRADO = ("despachado", "por_gestionar")

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
            "Registra qué producto quiere comprar el cliente, cuántas "
            "unidades, y la variante si el producto tiene (color, talla, "
            "etc. — revisa la sección de variantes en tu información del "
            "producto). Llámala en cuanto el cliente confirme el producto. "
            "Si el producto tiene variantes y el cliente aún no eligió, "
            "pregúntale UNA vez cuál prefiere — pero si no logras que lo "
            "confirme con claridad, registra el producto igual sin variante "
            "y sigue adelante. La variante nunca es motivo para escalar ni "
            "para detener el cierre de la venta. IMPORTANTE: producto_sku "
            "debe ser copiado EXACTO, carácter por carácter, del SKU que "
            "aparece en la información del producto de tu system prompt — "
            "nunca lo inventes, abrevies, ni le des un formato distinto. "
            "El TOTAL a cobrar lo calcula el sistema (precio del catálogo x "
            "cantidad) y te lo devuelve: no lo envíes ni lo calcules tú."
        ),
        parametros={
            "type": "object",
            "properties": {
                "producto_sku": {"type": "string"},
                "producto_nombre": {"type": "string"},
                "cantidad": {
                    "type": "integer",
                    "minimum": 1,
                    "description": (
                        "Unidades que quiere el cliente. Omitir si es una sola. "
                        "El sistema valida el máximo permitido por pedido."
                    ),
                },
                "variante": {
                    "type": "string",
                    "description": (
                        "Color, talla u otra variante elegida, si aplica. "
                        "Omitir si no aplica o el cliente no especificó."
                    ),
                },
            },
            "required": ["producto_sku", "producto_nombre"],
        },
    ),
    HerramientaLLM(
        nombre="ver_ficha_producto",
        descripcion=(
            "Devuelve la información completa de un producto del catálogo "
            "(descripción, precio, variantes, entrega, métodos de pago, "
            "preguntas frecuentes, unidades máximas por pedido). Úsala "
            "cuando el cliente pregunte por un producto de la lista del que "
            "todavía no ves los detalles, ANTES de responderle: nunca "
            "inventes datos que no estén en la ficha."
        ),
        parametros={
            "type": "object",
            "properties": {
                "producto_sku": {
                    "type": "string",
                    "description": "SKU exacto del producto, tal como aparece en la lista.",
                },
            },
            "required": ["producto_sku"],
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
            "producto, entrega (si el envío no va incluido) y método de pago. En un producto de Rocketfy, si el "
            "método de pago es transferencia, esta herramienta te va a decir que falta "
            "verificar el comprobante. En un producto de cierre manual, le pasa el pedido al dueño, que "
            "coordina el pago y la entrega. No la llames si falta cualquier dato."
        ),
        parametros={"type": "object", "properties": {}},
    ),
    HerramientaLLM(
        nombre="registrar_entrega",
        descripcion=(
            "Solo para productos cuyo envío NO está incluido en el precio (lo dice su ficha). Sin parámetros "
            "te devuelve las opciones de entrega que le aplican al cliente según su cantón y provincia, con "
            "su costo: ofrécele esas y NO otras. Cuando el cliente elija una, vuelve a llamarla con `opcion` "
            "(el número de la lista o el nombre) y te devuelve el TOTAL final con el envío, que es el único "
            "monto que puedes decirle. Necesitas haber guardado antes su cantón y provincia."
        ),
        parametros={
            "type": "object",
            "properties": {
                "opcion": {
                    "type": "string",
                    "description": "Número de la opción o su nombre, tal como te los dio esta herramienta. Omitir para ver las opciones.",
                },
            },
        },
    ),
    HerramientaLLM(
        nombre="solicitar_gestion",
        descripcion=(
            "Solo para productos de CIERRE MANUAL (lo dice su ficha). Avisa al dueño de que el cliente mostró "
            "una intención de compra. tipo: quiere_comprar (dijo que lo quiere), quiere_pagar (pregunta cómo "
            "pagar o quiere pagar ya), pide_envio (pide envío o retiro), quiere_ver_producto (quiere verlo en "
            "persona o probarlo), quiere_negociar (pide rebaja o condiciones especiales) u otro. Con "
            "quiere_comprar, quiere_pagar y pide_envio SIGUES tomando los datos del cliente; con "
            "quiere_ver_producto, quiere_negociar y otro la conversación pasa al dueño y debes despedirte. "
            "Llámala UNA vez por intención; no la repitas por lo mismo."
        ),
        parametros={
            "type": "object",
            "properties": {
                "tipo": {"type": "string", "enum": list(TIPOS_QUE_PIDE_VICTORIA)},
                "detalle": {
                    "type": "string",
                    "description": "Una frase con lo que pidió el cliente, para que el dueño sepa qué hacer.",
                },
            },
            "required": ["tipo"],
        },
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

# Fase G2: no va en HERRAMIENTAS_VICTORIA porque se puede apagar (parámetro «Enviar fotos»,
# `bot.enviar_fotos`): ver `herramientas_de_victoria()`.
HERRAMIENTA_FOTO = HerramientaLLM(
    nombre="enviar_foto_producto",
    descripcion=(
        "Envía al cliente, por este mismo WhatsApp, las fotos del producto (unas pocas a la vez). Úsala "
        "SOLO cuando el cliente pida ver fotos o imágenes, o dude de cómo luce el "
        "producto. No la uses para otra cosa. Si el cliente pide más, vuelve a llamarla: manda las "
        "siguientes sin repetir, y cuando ya no quedan el sistema te lo dirá. producto_sku debe ser el SKU "
        "exacto del producto que aparece en tu información. Si el producto no tiene fotos, no prometas "
        "una: dile con naturalidad que por el momento no hay imágenes y descríbelo con lo que dice su ficha."
    ),
    parametros={
        "type": "object",
        "properties": {
            "producto_sku": {
                "type": "string",
                "description": "SKU exacto del producto, tal como aparece en tu información.",
            },
        },
        "required": ["producto_sku"],
    },
)


def herramientas_de_victoria(enviar_fotos: bool) -> List[HerramientaLLM]:
    """Las herramientas que se le ofrecen al modelo en cada turno."""
    return [*HERRAMIENTAS_VICTORIA, HERRAMIENTA_FOTO] if enviar_fotos else list(HERRAMIENTAS_VICTORIA)


class HerramientasVictoria:
    def __init__(
        self,
        lead_repo: Optional[LeadRepository] = None,
        conversacion_repo: Optional[ConversacionRepository] = None,
        producto_repo: Optional[ProductoBotRepository] = None,
        pedido_service: Optional[PedidoService] = None,
        telegram_notifier: Optional[TelegramNotifier] = None,
        stock_checker: Optional[StockChecker] = None,
        minimo_repo: Optional[MinimoObservadoRepository] = None,
        mensaje_repo: Optional[MensajeRepository] = None,
        whatsapp_client=None,
        enviar_fotos: Optional[bool] = None,
        entrega_repo: Optional[EntregaRepository] = None,
        gestion_service: Optional[GestionService] = None,
        ventas_service: Optional[VentasService] = None,
        imagen_repo: Optional[ImagenRepository] = None,
    ):
        self._leads = lead_repo or LeadRepository()
        self._conversaciones = conversacion_repo or ConversacionRepository()
        self._productos = producto_repo or ProductoBotRepository()
        self._pedidos = pedido_service or PedidoService(client=get_rocketfy_client())
        self._telegram = telegram_notifier or get_telegram_notifier()
        self._stock = stock_checker or StockChecker()
        self._minimos = minimo_repo or MinimoObservadoRepository()
        self._mensajes = mensaje_repo or MensajeRepository()
        # ADR-012: envío por producto, avisos de gestión al dueño y registro de ventas (cierre manual).
        self._entregas = entrega_repo or EntregaRepository()
        self._gestion = gestion_service or GestionService(telegram=self._telegram)
        self._ventas = ventas_service or VentasService()
        self._imagenes = imagen_repo or ImagenRepository()
        # Perezoso: el cliente de WhatsApp solo se arma si de verdad se envía una foto.
        self._whatsapp = whatsapp_client
        # None = lo decide el parámetro «Enviar fotos» en cada llamada (se cambia desde la
        # app, sin reiniciar); True/False lo fija a la fuerza («Probar con Victoria» y los tests).
        self._enviar_fotos_fijo = enviar_fotos
        self._manejadores = {
            "guardar_datos_cliente": self._handle_guardar_datos_cliente,
            "ver_ficha_producto": self._handle_ver_ficha_producto,
            "registrar_producto": self._handle_registrar_producto,
            "registrar_metodo_pago": self._handle_registrar_metodo_pago,
            "registrar_entrega": self._handle_registrar_entrega,
            "solicitar_gestion": self._handle_solicitar_gestion,
            "cerrar_venta": self._handle_cerrar_venta,
            "escalar_a_humano": self._handle_escalar_a_humano,
            "enviar_foto_producto": self._handle_enviar_foto_producto,
        }

    def _fotos_activas(self) -> bool:
        return self._enviar_fotos_fijo if self._enviar_fotos_fijo is not None else parametros.valor("bot.enviar_fotos")

    def ejecutar(self, nombre: str, lead_id: int, conversacion_id: int, entrada: dict, id_llamada: str) -> ResultadoHerramienta:
        manejador = self._manejadores.get(nombre)
        if nombre == "enviar_foto_producto" and not self._fotos_activas():
            manejador = None  # apagada: no se le ofrece a la IA, y si la pide igual, es una herramienta que no existe
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
        if entrada.get("canton") or entrada.get("provincia"):
            aviso = self._revalidar_entrega_elegida(lead_id)
            if aviso:
                return f"Datos guardados correctamente. {aviso}"
        return "Datos guardados correctamente."

    def _revalidar_entrega_elegida(self, lead_id: int) -> str:
        """Si el cliente ya había elegido una opción de entrega y cambia su destino, la opción puede dejar
        de aplicar (p. ej. «Envío en Cuenca» y ahora vive en Quito): se borra y se avisa a Victoria."""
        lead = self._leads.obtener_por_id(lead_id)
        if not lead or lead.get("entrega_opcion_id") is None:
            return ""
        opciones = self._entregas.listar(lead["producto_sku"], solo_activas=True) if lead.get("producto_sku") else []
        aplicables = opciones_aplicables(opciones, lead.get("canton"), lead.get("provincia"))
        if any(o["id"] == lead["entrega_opcion_id"] for o in aplicables):
            return ""
        subtotal = lead.get("subtotal") if lead.get("subtotal") is not None else lead.get("total")
        self._leads.actualizar_entrega(lead_id, None, None, None, Decimal("0.00"), subtotal)
        return (
            "La entrega que había elegido ya no aplica al nuevo destino: vuelve a ofrecerle las opciones con "
            "registrar_entrega y avísale que el total puede cambiar."
        )

    def _handle_ver_ficha_producto(self, lead_id: int, conversacion_id: int, entrada: dict) -> str:
        """Ficha completa de un producto, en el mismo turno (hueco H7 del plan
        de gestión de productos): con varios productos, el contexto del system
        prompt solo trae nombre, SKU y precio hasta que se registra uno."""
        consulta = (entrada.get("producto_sku") or "").strip()
        producto = self._productos.obtener_por_sku(consulta) if consulta else None
        if producto is None and consulta:
            producto = self._buscar_producto_activo_por_nombre(consulta)
        if not self._esta_activo(producto):
            return f"No encontré ese producto entre los disponibles. {self._texto_catalogo_disponible()}"
        return formatear_ficha_producto(producto, self._entregas.listar(producto["sku"], solo_activas=True))

    def _handle_enviar_foto_producto(self, lead_id: int, conversacion_id: int, entrada: dict) -> str:
        """Fase G2 + ADR-012. Solo se envían fotos de un producto ACTIVO del catálogo (las URLs salen de la
        base, nunca de lo que escriba el modelo), en tandas de «Fotos por envío» (parámetro
        `bot.max_fotos_por_envio`) y sin repetir las que ya se mandaron en esta conversación. La galería
        son las fotos que el dueño subió a la ficha o, si no subió ninguna, la de Rocketfy. Cualquier fallo
        se le explica a Victoria y no escala: no tener fotos no es motivo para pasar a una persona."""
        consulta = (entrada.get("producto_sku") or "").strip()
        producto = self._productos.obtener_por_sku(consulta) if consulta else None
        if producto is None and consulta:
            producto = self._buscar_producto_activo_por_nombre(consulta)
        if not self._esta_activo(producto):
            return f"No encontré ese producto entre los disponibles. {self._texto_catalogo_disponible()}"

        # La base puede traer todavía la ruta relativa de Rocketfy (`/storage/...`): se completa.
        galeria = galeria_para_enviar(
            self._imagenes.listar(producto["sku"]), url_de_imagen(producto.get("imagen_url"))
        )
        if not galeria:
            # Meta solo descarga enlaces https públicos.
            return (
                "Este producto todavía no tiene fotos para enviar. Dile al cliente con naturalidad que por el momento "
                "no hay imágenes disponibles, descríbele el producto con la información de su ficha y no le prometas fotos."
            )
        ya_enviadas = self._mensajes.contar_fotos(conversacion_id, producto["sku"])
        pendientes = galeria[ya_enviadas:]
        if not pendientes:
            if len(galeria) == 1:
                return "Ya le enviaste la foto de este producto a este cliente: no la repitas. Descríbeselo con su ficha."
            return (
                f"Ya le enviaste las {len(galeria)} fotos de este producto a este cliente: no las repitas. "
                "Descríbeselo con su ficha."
            )

        lead = self._leads.obtener_por_id(lead_id)
        tanda = pendientes[: parametros.valor("bot.max_fotos_por_envio")]
        enviadas = 0
        for posicion, url in enumerate(tanda):
            try:
                self._cliente_whatsapp().enviar_imagen(
                    telefono=lead["telefono"], url=url, descripcion=producto["nombre"] if ya_enviadas + posicion == 0 else None
                )
            except Exception:
                logger.warning(
                    "No se pudo enviar la foto %s de '%s'", ya_enviadas + posicion + 1, producto["sku"],
                    exc_info=True, extra={"lead_id": lead_id, "conversacion_id": conversacion_id},
                )
                break
            self._mensajes.crear(
                conversacion_id=conversacion_id,
                rol="bot",
                contenido=f"📷 Foto de {producto['nombre']} ({producto['sku']})",
                tipo="imagen",
                wamid=None,
            )
            enviadas += 1
        if enviadas == 0:
            return (
                "No se pudieron enviar las fotos en este momento. Díselo con naturalidad al cliente y descríbele el "
                "producto con la información de su ficha."
            )
        quedan = len(galeria) - ya_enviadas - enviadas
        resto = f" Quedan {quedan} más: si el cliente quiere ver más, vuelve a usar esta herramienta." if quedan > 0 else ""
        parcial = " (solo se pudieron enviar algunas)" if enviadas < len(tanda) else ""
        unidad = "la foto" if enviadas == 1 else f"{enviadas} fotos"
        return f"Ya le enviaste {unidad}{parcial}. Puedes decirle que se las mandaste.{resto}"

    def _cliente_whatsapp(self):
        if self._whatsapp is None:
            self._whatsapp = get_whatsapp_client()
        return self._whatsapp

    def _handle_registrar_producto(self, lead_id: int, conversacion_id: int, entrada: dict) -> str:
        # El LLM no siempre copia el SKU exacto tal como aparece en el
        # catálogo (probado en la práctica: a veces lo inventa, a veces
        # manda el nombre en el campo sku, a veces un placeholder tipo
        # "N/A") -- se intenta primero el match exacto por SKU y, si
        # falla, un fuzzy-match por nombre (sin distinguir tildes/mayúsculas)
        # contra productos_bot antes de guardar nada. Nunca debe llegar un
        # SKU inventado hasta cerrar_venta, que se lo pasa tal cual a
        # Rocketfy.
        #
        # Fase A del plan de gestión de productos: además (1) un producto
        # PAUSADO no se registra (H6), (2) la cantidad no puede pasar del
        # máximo del producto (H2), (3) no se vende más de lo que hay en
        # Rocketfy (H3) y (4) el TOTAL lo calcula el sistema con el precio del
        # catálogo, nunca el LLM (H1).
        sku = entrada["producto_sku"]
        nombre = entrada["producto_nombre"]
        contexto = {"lead_id": lead_id, "conversacion_id": conversacion_id}

        producto_real = self._productos.obtener_por_sku(sku)
        if producto_real is not None and not self._esta_activo(producto_real):
            logger.warning(
                "registrar_producto: el producto '%s' está pausado -- no se registra", producto_real["sku"], extra=contexto
            )
            return (
                f"Ese producto ya no está disponible. {self._texto_catalogo_disponible()} "
                "Pregúntale al cliente si le interesa alguno de estos, o usa escalar_a_humano."
            )

        if producto_real is None:
            producto_real = self._buscar_producto_activo_por_nombre(nombre)
            if producto_real is not None:
                logger.warning(
                    "producto_sku del LLM ('%s') no coincide con ningún producto real -- corregido a '%s' por nombre",
                    sku, producto_real["sku"],
                    extra=contexto,
                )

        if producto_real is None:
            # Resiliencia: si tampoco el fuzzy-match por nombre encuentra
            # nada, no se adivina ni se guarda cualquier cosa -- se le
            # devuelve a Victoria la lista real de productos disponibles
            # para que le pregunte de nuevo al cliente en el mismo turno.
            logger.warning(
                "registrar_producto no encontró ningún producto real para sku=%r nombre=%r -- no se guarda nada",
                sku, nombre,
                extra=contexto,
            )
            return (
                f"No encontré ese producto en el catálogo. {self._texto_catalogo_disponible()} "
                "Pregúntale al cliente cuál de estos quiere antes de registrar de nuevo."
            )

        cantidad = _leer_cantidad(entrada.get("cantidad"))
        if cantidad is None:
            return (
                "La cantidad debe ser un número entero de 1 en adelante. "
                "Confírmala con el cliente y vuelve a registrar el producto."
            )
        maximo = int(producto_real.get("max_unidades_por_pedido") or 1)
        if cantidad > maximo:
            return self._mensaje_maximo_unidades(maximo)

        stock = self._stock_disponible(producto_real)
        if stock is not None and stock < cantidad:
            return self._respuesta_sin_stock(lead_id, conversacion_id, producto_real, cantidad, stock)

        total = self._calcular_total(producto_real, cantidad)
        self._avisar_si_el_llm_envio_otro_total(entrada, total, contexto)

        self._leads.actualizar_producto(
            lead_id,
            producto_sku=producto_real["sku"],
            producto_nombre=producto_real["nombre"],
            total=total,
            variante=entrada.get("variante"),
            cantidad=cantidad,
        )
        if not producto_real.get("envio_incluido", True):
            return (
                f"Producto registrado: {cantidad} x {producto_real['nombre']}. Subtotal: ${total}, SIN el envío: "
                "este producto cobra el envío aparte. Cuando tengas el cantón y la provincia del cliente, usa "
                "registrar_entrega para ofrecerle las opciones; el total final te lo devuelve esa herramienta."
            )
        return (
            f"Producto registrado: {cantidad} x {producto_real['nombre']}. "
            f"Total a cobrar: ${total}. Ese es el monto exacto que debes comunicarle al cliente; no lo cambies."
        )

    def _stock_disponible(self, producto: dict, fresco: bool = False) -> Optional[int]:
        """Unidades que hay de un producto, o None si no se sabe / no se controla. Un producto propio con
        control de stock lo lleva la propia app (la base); el de Rocketfy se le pregunta a Rocketfy."""
        if es_de_cierre_manual(producto):
            if not controla_su_stock(producto):
                return None
            if fresco:
                producto = self._productos.obtener_por_sku(producto["sku"]) or producto
            return producto.get("stock_ultimo")
        return self._stock.stock_de(producto["sku"], fresco=fresco)

    @staticmethod
    def _esta_activo(producto: Optional[dict]) -> bool:
        return producto is not None and bool(producto.get("activo", True))

    @staticmethod
    def _calcular_total(producto: dict, cantidad: int) -> Decimal:
        """Precio del catálogo x cantidad, siempre Decimal con 2 cifras (el
        dinero nunca es float)."""
        return (Decimal(str(producto["precio"])) * cantidad).quantize(Decimal("0.01"))

    @staticmethod
    def _avisar_si_el_llm_envio_otro_total(entrada: dict, total_calculado: Decimal, contexto: dict) -> None:
        if "total" not in entrada:
            return
        try:
            enviado = Decimal(str(entrada["total"])).quantize(Decimal("0.01"))
        except InvalidOperation:
            enviado = None
        if enviado != total_calculado:
            logger.warning(
                "El LLM envió total=%r pero el sistema calculó %s -- se usa el del sistema",
                entrada["total"], total_calculado,
                extra=contexto,
            )

    def _texto_catalogo_disponible(self) -> str:
        activos = self._productos.listar_activos()
        if not activos:
            return "Por ahora no hay productos disponibles en el catálogo; usa escalar_a_humano."
        lista = ", ".join(f"{p['nombre']} ({p['sku']}): ${p['precio']}" for p in activos)
        return f"Los productos disponibles ahora son: {lista}."

    @staticmethod
    def _mensaje_maximo_unidades(maximo: int) -> str:
        unidades = "unidad" if maximo == 1 else "unidades"
        return (
            f"De este producto solo se puede pedir hasta {maximo} {unidades} por pedido. "
            f"Explícaselo al cliente con naturalidad y ofrécele registrar {maximo}; "
            "si necesita más, usa escalar_a_humano."
        )

    def _respuesta_sin_stock(self, lead_id: int, conversacion_id: int, producto: dict, cantidad: int, stock: int) -> str:
        logger.warning(
            "Venta frenada por falta de stock: sku=%s pedido=%s disponible=%s",
            producto["sku"], cantidad, stock,
            extra={"lead_id": lead_id, "conversacion_id": conversacion_id},
        )
        if stock <= 0:
            # Producto activo pero agotado: además de frenar la venta, una
            # persona debe enterarse (aviso por Telegram) para ofrecer
            # alternativas y pausar el producto.
            self._handle_escalar_a_humano(
                lead_id,
                conversacion_id,
                {
                    "motivo": (
                        f"Producto sin stock{'' if es_de_cierre_manual(producto) else ' en Rocketfy'}: "
                        f"{producto['nombre']} ({producto['sku']}). "
                        f"El cliente quería {cantidad}. Conviene pausar el producto."
                    )
                },
            )
            return (
                "Ese producto está agotado por el momento. Ya se avisó a un asesor humano que va a "
                "contactar al cliente; despídete cordialmente sin prometer fechas de reposición."
            )
        unidades = "unidad" if stock == 1 else "unidades"
        return (
            f"Solo quedan {stock} {unidades} de ese producto. Díselo al cliente y ofrécele registrar "
            f"hasta {stock}; no prometas reposición ni fechas."
        )

    def _buscar_producto_activo_por_nombre(self, nombre: str) -> Optional[dict]:
        nombre_normalizado = _normalizar_texto(nombre)
        for producto in self._productos.listar_activos():
            if _normalizar_texto(producto["nombre"]) == nombre_normalizado:
                return producto
        return None

    def _handle_registrar_metodo_pago(self, lead_id: int, conversacion_id: int, entrada: dict) -> str:
        lead = self._leads.obtener_por_id(lead_id)
        producto = self._productos.obtener_por_sku(lead["producto_sku"]) if lead and lead.get("producto_sku") else None
        if es_de_cierre_manual(producto):
            # El dueño verifica el pago a mano: ni el lead ni la conversación quedan «esperando_pago»
            # (ese estado es el de la regla de Rocketfy que le pide el comprobante a Victoria).
            self._leads.actualizar_metodo_pago(lead_id, metodo_pago=entrada["metodo_pago"], esperar_comprobante=False)
            return "Método de pago registrado."
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

        if lead.get("estado") in ESTADOS_DE_LEAD_CERRADO:
            # Nunca se cierra dos veces: un segundo cierre duplicaría un pedido real (Rocketfy) o un aviso al dueño.
            return "Este pedido ya quedó registrado: no lo cierres otra vez. Despídete cordialmente."

        producto = self._productos.obtener_por_sku(lead["producto_sku"])
        manual = es_de_cierre_manual(producto)

        # En Rocketfy la transferencia obliga a esperar el comprobante; en un producto propio la verificación
        # del pago la hace el dueño, así que no frena el cierre (ADR-012).
        if not manual and lead["metodo_pago"] == "transferencia":
            return (
                "Este pedido es por transferencia. Pide al cliente la foto del comprobante "
                "antes de continuar. No se puede cerrar todavía."
            )

        if producto is not None and not producto.get("envio_incluido", True) and lead.get("entrega_opcion_id") is None:
            return (
                "Falta elegir la entrega: este producto cobra el envío aparte. Usa registrar_entrega para ofrecerle "
                "al cliente las opciones y su total final, y luego vuelve a intentar cerrar."
            )

        cantidad = int(lead.get("cantidad") or 1)

        # Última revisión ANTES de crear un pedido real en Rocketfy: el
        # producto sigue activo, la cantidad sigue permitida, el precio no
        # cambió desde que se cotizó y hay stock fresco. Cualquier falla
        # frena el cierre y pasa la conversación a una persona.
        problema = self._revisar_antes_de_cerrar(lead, producto, cantidad)
        if problema is not None:
            motivo, mensaje = problema
            logger.warning(
                "cerrar_venta frenado: %s", motivo, extra={"lead_id": lead_id, "conversacion_id": conversacion_id}
            )
            self._handle_escalar_a_humano(lead_id, conversacion_id, {"motivo": motivo})
            return mensaje

        if manual:
            return self._cerrar_venta_manual(lead, producto, conversacion_id, cantidad)

        tiempo_entrega = producto["tiempo_entrega"]

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
            lineas=[LineaPedidoDTO(sku=lead["producto_sku"], nombre=nombre_linea, cantidad=cantidad)],
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
            self._guardar_minimo_observado(exc, lead, cantidad)
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
        self._registrar_venta_de_rocketfy(lead_id, conversacion_id, producto)
        return f"¡Pedido confirmado! Llega en {tiempo_entrega}. Comunícaselo al cliente y agradécele."

    def _registrar_venta_de_rocketfy(self, lead_id: int, conversacion_id: int, producto: dict) -> None:
        """Deja la «foto» de la venta (precio y costo congelados) para los reportes. El pedido real YA se creó:
        si esto falla, solo se registra el error."""
        try:
            lead = self._leads.obtener_por_id(lead_id)
            conversacion = self._conversaciones.obtener_por_id(conversacion_id)
            entrega = self._entregas.obtener(lead["entrega_opcion_id"]) if lead.get("entrega_opcion_id") else None
            self._ventas.registrar_venta_rocketfy(lead, producto, conversacion, entrega)
        except Exception:
            logger.exception("No se pudo registrar la venta del lead %s para los reportes", lead_id)

    def _cerrar_venta_manual(self, lead: dict, producto: dict, conversacion_id: int, cantidad: int) -> str:
        """Cierre de un producto PROPIO (ADR-012): no se crea ningún pedido en Rocketfy. Se guarda la venta,
        se descuenta el stock (si lo controla), se pasa la conversación al dueño y se le avisa. Todo en una
        sola transacción (ver `VentasRepository.cerrar_manual`)."""
        lead_id = lead["id"]
        conversacion = self._conversaciones.obtener_por_id(conversacion_id)
        entrega = self._entregas.obtener(lead["entrega_opcion_id"]) if lead.get("entrega_opcion_id") else None
        try:
            resultado = self._ventas.cerrar_manual(
                lead, producto, conversacion, entrega, controla_su_stock(producto), self._detalle_del_pedido(lead, cantidad)
            )
        except StockInsuficienteError as exc:
            return self._respuesta_sin_stock(lead_id, conversacion_id, producto, cantidad, exc.disponible or 0)
        except VentaYaRegistradaError:
            return "Este pedido ya quedó registrado: no lo cierres otra vez. Despídete cordialmente."
        except Exception:
            logger.exception(
                "No se pudo registrar el pedido de un producto propio", extra={"lead_id": lead_id, "conversacion_id": conversacion_id}
            )
            self._handle_escalar_a_humano(
                lead_id, conversacion_id, {"motivo": "No se pudo registrar el pedido de un producto propio (error técnico)."}
            )
            return (
                "Hubo un problema técnico registrando el pedido. Ya se avisó al dueño, que va a contactar al "
                "cliente: dile que en breve le confirman y despídete cordialmente."
            )

        self._avisar_pedido_cerrado(lead, producto, conversacion_id, cantidad, entrega, resultado)
        return (
            f"¡Pedido registrado! El dueño ya recibió todos los datos y se pondrá en contacto con el cliente para "
            f"coordinar el pago y la entrega (tiempo estimado: {producto['tiempo_entrega']}). Dile al cliente que su "
            "pedido quedó registrado y que lo van a contactar muy pronto; no confirmes el pago ni prometas fechas. "
            "Este es tu último mensaje: despídete cordialmente."
        )

    @staticmethod
    def _detalle_del_pedido(lead: dict, cantidad: int) -> str:
        producto = f"{cantidad} x {lead['producto_nombre']}"
        if lead.get("producto_variante"):
            producto += f" ({lead['producto_variante']})"
        entrega = lead.get("entrega_nombre") or "envío incluido en el precio"
        return f"{producto} · total ${Decimal(str(lead['total'])):.2f} · entrega: {entrega} · pago: {lead['metodo_pago']}"

    def _avisar_pedido_cerrado(self, lead, producto, conversacion_id, cantidad, entrega, resultado) -> None:
        """El timbre (Telegram) de un pedido cerrado. El registro ya está guardado en la base; esto es best-effort."""
        try:
            nombre = lead["producto_nombre"] + (f" ({lead['producto_variante']})" if lead.get("producto_variante") else "")
            datos = {
                "cliente": lead["nombre_cliente"],
                "telefono": lead["telefono"],
                "direccion": f"{lead['direccion']}, {lead['canton']}, {lead['provincia']}",
                "producto": f"{cantidad} x {nombre}",
                "entrega": lead.get("entrega_nombre") or "Envío incluido en el precio",
                "total": f"{Decimal(str(lead['total'])):.2f}",
                "pago": lead["metodo_pago"],
                "conversacion_id": conversacion_id,
                "aviso": (
                    "Pago por transferencia: pasa tú los datos de la cuenta y verifica el comprobante."
                    if lead["metodo_pago"] == "transferencia"
                    else None
                ),
            }
            self._gestion.avisar_pedido_cerrado(datos)
            if resultado.get("pausado_por_agotado"):
                self._telegram.notificar_aviso(
                    "🟠 Producto agotado: se pausó solo",
                    f"{producto['nombre']} ({producto['sku']}) se quedó sin unidades con esta venta. Victoria ya no "
                    "lo ofrece. Cuando repongas stock, actualízalo y reanúdalo en Catálogo → Mis productos.",
                )
            elif resultado.get("stock_restante") is not None and resultado["stock_restante"] <= parametros.valor("stock.umbral_bajo"):
                self._telegram.notificar_aviso(
                    "🟡 Quedan pocas unidades",
                    f"{producto['nombre']} ({producto['sku']}): quedan {resultado['stock_restante']}.",
                )
        except Exception:
            logger.exception("No se pudo avisar por Telegram el pedido cerrado (ya quedó guardado en «Por gestionar»)")

    def _revisar_antes_de_cerrar(
        self, lead: dict, producto: Optional[dict], cantidad: int
    ) -> Optional[Tuple[str, str]]:
        """Devuelve None si todo está bien, o (motivo para la persona,
        mensaje para Victoria) si el cierre debe frenarse."""
        sku = lead["producto_sku"]
        aviso_a_victoria = (
            "No se pudo cerrar la venta por un inconveniente con {que}. Ya se avisó a un asesor "
            "humano que va a contactar al cliente; despídete cordialmente."
        )

        if not self._esta_activo(producto):
            return (
                f"El producto {lead['producto_nombre']} ({sku}) ya no está disponible (pausado o eliminado) "
                "y el cliente quería cerrar la compra.",
                aviso_a_victoria.format(que="la disponibilidad del producto"),
            )

        maximo = int(producto.get("max_unidades_por_pedido") or 1)
        if cantidad > maximo:
            return (
                f"El cliente pidió {cantidad} unidades de {sku} pero el máximo por pedido es {maximo}.",
                aviso_a_victoria.format(que="las unidades del pedido"),
            )

        # El precio cotizado es el del producto (subtotal); el envío se verifica aparte.
        precio_actual = producto.get("precio")
        cotizado = Decimal(str(lead["subtotal"] if lead.get("subtotal") is not None else lead["total"])).quantize(Decimal("0.01"))
        if precio_actual is None or self._calcular_total(producto, cantidad) != cotizado:
            actual = self._calcular_total(producto, cantidad) if precio_actual is not None else "desconocido"
            return (
                f"El precio de {sku} no coincide con lo cotizado al cliente (cotizado ${cotizado}, "
                f"actual ${actual} por {cantidad} unidad(es)). Pudo cambiar durante la conversación.",
                aviso_a_victoria.format(que="el precio"),
            )

        problema_de_entrega = self._problema_de_entrega(lead, producto)
        if problema_de_entrega is not None:
            return problema_de_entrega, aviso_a_victoria.format(que="la entrega")

        stock = self._stock_disponible(producto, fresco=True)
        if stock is not None and stock < cantidad:
            donde = "" if es_de_cierre_manual(producto) else " en Rocketfy"
            return (
                f"Sin stock suficiente{donde} al cerrar: {sku}, pedido {cantidad}, disponible {stock}.",
                aviso_a_victoria.format(que="el stock"),
            )

        return None

    def _problema_de_entrega(self, lead: dict, producto: dict) -> Optional[str]:
        """Si el envío se cobra aparte, la opción que eligió el cliente tiene que seguir existiendo, aplicar a su
        destino y costar lo mismo que se le dijo."""
        if producto.get("envio_incluido", True):
            return None
        opcion = self._entregas.obtener(lead["entrega_opcion_id"]) if lead.get("entrega_opcion_id") is not None else None
        if opcion is None or not opcion.get("activo", True):
            return f"La opción de entrega «{lead.get('entrega_nombre')}» de {lead['producto_sku']} ya no existe."
        if opcion["id"] not in {o["id"] for o in opciones_aplicables([opcion], lead.get("canton"), lead.get("provincia"))}:
            return f"La entrega «{opcion['nombre']}» ya no aplica al destino del cliente ({lead.get('canton')})."
        if Decimal(str(opcion["costo_cliente"])).quantize(Decimal("0.01")) != Decimal(str(lead.get("costo_envio") or 0)).quantize(Decimal("0.01")):
            return f"El costo de «{opcion['nombre']}» cambió desde que se le cotizó al cliente."
        return None

    # ------------------------------------------------------------------
    # Envío y gestión (ADR-012)
    # ------------------------------------------------------------------
    def _handle_registrar_entrega(self, lead_id: int, conversacion_id: int, entrada: dict) -> str:
        lead = self._leads.obtener_por_id(lead_id)
        if not lead.get("producto_sku"):
            return "Primero registra el producto con registrar_producto; la entrega se elige después."
        producto = self._productos.obtener_por_sku(lead["producto_sku"])
        if not self._esta_activo(producto):
            return f"Ese producto ya no está disponible. {self._texto_catalogo_disponible()}"
        if producto.get("envio_incluido", True):
            return (
                f"Este producto incluye el envío en el precio: no hay nada que elegir. "
                f"El total a cobrar es ${Decimal(str(lead['total'])):.2f}."
            )
        if not (lead.get("canton") or lead.get("provincia")):
            return (
                "Necesito el cantón y la provincia del cliente para saber qué entrega le aplica. Pídeselos, "
                "guárdalos con guardar_datos_cliente y vuelve a llamar esta herramienta."
            )

        opciones = self._entregas.listar(producto["sku"], solo_activas=True)
        aplicables = opciones_aplicables(opciones, lead.get("canton"), lead.get("provincia"))
        if not aplicables:
            destino = ", ".join(x for x in (lead.get("canton"), lead.get("provincia")) if x)
            self._pedir_gestion(
                lead, conversacion_id, "sin_cobertura",
                f"{producto['nombre']} ({producto['sku']}) no tiene una entrega que aplique a {destino}.",
            )
            self._conversaciones.marcar_en_gestion(conversacion_id)
            return (
                f"Este producto no tiene una entrega disponible para {destino}. Ya se avisó al dueño, que verá si "
                "puede atender ese destino. No prometas nada: dile al cliente con naturalidad que lo van a "
                "contactar y despídete. Este es tu último mensaje."
            )

        subtotal = Decimal(str(lead["subtotal"] if lead.get("subtotal") is not None else lead["total"]))
        texto = (entrada.get("opcion") or "").strip()
        if not texto:
            lista = "\n".join(describir(o, con_numero=i) for i, o in enumerate(aplicables, start=1))
            return (
                f"Opciones de entrega para {lead.get('canton') or lead.get('provincia')} (subtotal de los productos: "
                f"${subtotal:.2f}):\n{lista}\nOfrécele estas y NO otras. Cuando el cliente elija, llama otra vez "
                "esta herramienta con `opcion` (el número o el nombre) y te doy el total final."
            )

        elegida = elegir_opcion(aplicables, texto)
        if elegida is None:
            lista = "\n".join(describir(o, con_numero=i) for i, o in enumerate(aplicables, start=1))
            return f"No reconocí esa opción. Las disponibles son:\n{lista}\nPregúntale al cliente cuál prefiere."

        total = total_con_envio(subtotal, elegida)
        self._leads.actualizar_entrega(lead_id, elegida["id"], elegida["nombre"], elegida["tipo"], elegida["costo_cliente"], total)
        return (
            f"Entrega registrada: {describir(elegida)}. Total a cobrar: ${total} (productos ${subtotal:.2f} + envío "
            f"${Decimal(str(elegida['costo_cliente'])):.2f}). Ese es el monto exacto que debes comunicarle al cliente; no lo cambies."
        )

    def _handle_solicitar_gestion(self, lead_id: int, conversacion_id: int, entrada: dict) -> str:
        lead = self._leads.obtener_por_id(lead_id)
        producto = self._productos.obtener_por_sku(lead["producto_sku"]) if lead.get("producto_sku") else None
        if producto is not None and not es_de_cierre_manual(producto):
            return (
                "Este producto se cierra solo, sin que intervenga el dueño: no necesitas solicitar_gestion. "
                "Sigue con el proceso normal de venta (si necesitas a una persona, usa escalar_a_humano)."
            )
        clave = entrada.get("tipo") if entrada.get("tipo") in TIPOS_QUE_PIDE_VICTORIA else "otro"
        resultado = self._pedir_gestion(lead, conversacion_id, clave, entrada.get("detalle"))
        if resultado.traspasa:
            self._conversaciones.marcar_en_gestion(conversacion_id)
            return (
                "Listo: ya se avisó al dueño y la conversación pasa a él. Despídete con naturalidad diciéndole al "
                "cliente que el dueño lo va a contactar muy pronto; no prometas fechas ni resuelvas tú lo que pidió. "
                "Este es tu último mensaje."
            )
        return (
            "Aviso registrado: el dueño ya sabe que el cliente quiere comprar. Tú sigue tomando los datos del pedido "
            "(nombre, dirección, cantón, provincia, producto, entrega y forma de pago) y al final usa cerrar_venta. "
            "No vuelvas a llamar solicitar_gestion por lo mismo."
        )

    def _pedir_gestion(self, lead: dict, conversacion_id: int, clave: str, detalle: Optional[str]):
        return self._gestion.solicitar(conversacion_id, lead["id"], clave, detalle, lead.get("telefono") or "")

    def _guardar_minimo_observado(self, exc: Exception, lead: dict, cantidad: int) -> None:
        """Si Rocketfy rechazó la confirmación por importe insuficiente, guarda
        el monto que exigió (valor de productos + envío de ese destino): es la
        única pista del costo real de envío. Solo con errores que vienen de
        Rocketfy -- el error LOCAL del recaudo de $10 también menciona un
        "mínimo" y un monto, y no es una observación de Rocketfy. Nunca debe
        romper el camino de escalado."""
        if not isinstance(exc, RocketfyBusinessError):
            return
        minimo = extraer_minimo_rocketfy(exc.message)
        if minimo is None:
            return
        try:
            self._minimos.guardar(
                sku=lead.get("producto_sku"),
                canton=lead.get("canton"),
                provincia=lead.get("provincia"),
                cantidad=cantidad,
                minimo=minimo,
                mensaje=exc.message[:500],
            )
        except Exception:
            logger.exception("No se pudo guardar el mínimo observado de Rocketfy (no afecta el escalado)")

    def _handle_escalar_a_humano(self, lead_id: int, conversacion_id: int, entrada: dict) -> str:
        self._conversaciones.marcar_escalada(conversacion_id)
        lead = self._leads.obtener_por_id(lead_id)
        telefono = lead["telefono"] if lead else ""
        self._telegram.notificar_escalado(conversacion_id, telefono, entrada.get("motivo", "sin especificar"))
        return (
            "Escalado correctamente. Este es tu último mensaje — despídete cordialmente "
            "informando que un asesor la va a contactar en breve."
        )
