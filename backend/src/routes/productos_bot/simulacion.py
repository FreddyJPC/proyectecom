"""
«Probar con Victoria» (Fase E del plan de gestión de productos): una
conversación de ensayo con el MISMO cerebro que habla con los clientes reales
(`VictoriaConversationService` + `HerramientasVictoria` + `PedidoService`), pero
sin tocar nada del mundo real.

Qué es real y qué es de mentira:
  REAL      el system prompt, la ficha del producto, el modelo de IA, las reglas
            de las herramientas (máximo de unidades, precio calculado por el
            sistema, recaudo mínimo de $10, validación de provincia/cantón…).
  ENSAYO    - Repositorios EN MEMORIA: no hay conversación, lead, mensaje ni
              pedido en la base. El estado de la prueba viaja de ida y vuelta
              con la app (ver `EstadoDeLaPrueba`): el servidor no guarda nada.
            - Rocketfy: un cliente que SOLO ANOTA lo que se habría enviado. El
              `PedidoService` real arma el payload verdadero y lo «manda» ahí.
            - Telegram: un grabador; el aviso de escalado queda a la vista pero
              no sale a ninguna parte.
            - WhatsApp: un grabador; la foto que Victoria enviaría queda a la
              vista, pero no se manda nada al cliente (que no existe). La
              herramienta de la foto SIEMPRE está disponible aquí, aunque en
              producción esté apagada (parámetro «Enviar fotos»): es la única diferencia
              deliberada con el cerebro real, para poder probarla antes de encenderla.
            - Stock: lo último guardado en la ficha (no se consulta Rocketfy).
            - Catálogo: el producto de la prueba es el único disponible, aunque
              esté en borrador (se le fuerza `activo=True` solo en la copia).
            - Producto PROPIO (ADR-012): el cierre manual se ensaya en memoria. Se ve la venta que se
              habría guardado y los avisos que habrían llegado al dueño; no se descuenta stock ni se guarda nada.
  NUNCA     se llama a WhatsApp, a Rocketfy, a Telegram ni a la base de datos.
            Un test lo vigila (tests/unit/routes/productos_bot/test_simulacion.py):
            falla si una compra simulada abre una conexión o hace una petición HTTP.

La única llamada de red real es la de la IA (Anthropic): sin ella no hay prueba.
"""
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from src.integrations.llm.contratos import LLMProvider
from src.routes.gestion.repository import ResultadoUpsert
from src.routes.gestion.services import ResultadoSolicitud
from src.routes.gestion.tipos import tipo as tipo_de_solicitud
from src.routes.pedidos.services import PedidoService
from src.routes.ventas.snapshot import armar_venta, ganancia_de
from src.routes.whatsapp.conversation_service import VictoriaConversationService
from src.routes.whatsapp.tools import HerramientasVictoria

logger = logging.getLogger(__name__)

# Teléfono ficticio con la forma de uno de WhatsApp (593 + 9 dígitos): así se
# ejercita la conversión a formato local que hace `cerrar_venta`.
TELEFONO_DE_PRUEBA = "593990000000"
ID_ANUNCIO_DE_PRUEBA = "anuncio-de-prueba"
ID_PEDIDO_SIMULADO_INICIAL = 9_000_001

# Campos del lead que viajan de ida y vuelta (y sus tipos al volver).
CAMPOS_TEXTO = (
    "nombre_cliente", "direccion", "canton", "provincia", "producto_sku", "producto_nombre", "producto_variante",
    "entrega_nombre", "entrega_tipo",
)
METODOS_DE_PAGO = ("contraentrega", "transferencia")
ESTADOS_DEL_LEAD = ("recopilando_datos", "esperando_pago", "despachado", "por_gestionar")
CAMPOS_DINERO = ("total", "subtotal", "costo_envio")
LARGO_MAXIMO_DE_UN_CAMPO = 500


# ----------------------------------------------------------------------
# Estado de la prueba (lo que la app guarda y reenvía en cada turno)
# ----------------------------------------------------------------------
def lead_inicial() -> Dict[str, Any]:
    return {
        "id": 1,
        "conversacion_id": 1,
        "telefono": TELEFONO_DE_PRUEBA,
        "nombre_cliente": None,
        "direccion": None,
        "canton": None,
        "provincia": None,
        "producto_sku": None,
        "producto_nombre": None,
        "producto_variante": None,
        "cantidad": 1,
        "total": None,
        "subtotal": None,
        "entrega_opcion_id": None,
        "entrega_nombre": None,
        "entrega_tipo": None,
        "costo_envio": Decimal("0.00"),
        "metodo_pago": None,
        "estado": "recopilando_datos",
        "id_pedido_local": None,
        "id_pedido_rocketfy": None,
    }


def lead_desde_estado(estado: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Reconstruye el lead a partir de lo que mandó la app. Solo se aceptan los
    campos conocidos, con su tipo: el resto se descarta en silencio."""
    lead = lead_inicial()
    estado = estado or {}
    for campo in CAMPOS_TEXTO:
        valor = estado.get(campo)
        if isinstance(valor, str) and valor.strip():
            lead[campo] = valor.strip()[:LARGO_MAXIMO_DE_UN_CAMPO]
    cantidad = estado.get("cantidad")
    if isinstance(cantidad, int) and not isinstance(cantidad, bool) and 1 <= cantidad <= 1000:
        lead["cantidad"] = cantidad
    for campo in CAMPOS_DINERO:
        if estado.get(campo) not in (None, ""):
            try:
                lead[campo] = Decimal(str(estado[campo])).quantize(Decimal("0.01"))
            except (InvalidOperation, ValueError):
                pass
    opcion = estado.get("entrega_opcion_id")
    if isinstance(opcion, int) and not isinstance(opcion, bool):
        lead["entrega_opcion_id"] = opcion
    if estado.get("metodo_pago") in METODOS_DE_PAGO:
        lead["metodo_pago"] = estado["metodo_pago"]
    if estado.get("estado") in ESTADOS_DEL_LEAD:
        lead["estado"] = estado["estado"]
    for campo in ("id_pedido_local", "id_pedido_rocketfy"):
        valor = estado.get(campo)
        if isinstance(valor, int) and not isinstance(valor, bool):
            lead[campo] = valor
    return lead


def estado_desde_lead(lead: Dict[str, Any]) -> Dict[str, Any]:
    """Lo contrario: el lead en el formato que viaja hacia la app (dinero como string)."""
    salida = {campo: lead.get(campo) for campo in CAMPOS_TEXTO}
    salida.update(
        cantidad=int(lead.get("cantidad") or 1),
        total=f"{Decimal(str(lead['total'])):.2f}" if lead.get("total") is not None else None,
        subtotal=f"{Decimal(str(lead['subtotal'])):.2f}" if lead.get("subtotal") is not None else None,
        costo_envio=f"{Decimal(str(lead.get('costo_envio') or 0)):.2f}",
        entrega_opcion_id=lead.get("entrega_opcion_id"),
        metodo_pago=lead.get("metodo_pago"),
        estado=lead.get("estado"),
        id_pedido_local=lead.get("id_pedido_local"),
        id_pedido_rocketfy=lead.get("id_pedido_rocketfy"),
    )
    return salida


# ----------------------------------------------------------------------
# Repositorios en memoria (misma interfaz que los reales, sin base de datos)
# ----------------------------------------------------------------------
class ConversacionesEnMemoria:
    def __init__(self, desde_anuncio: bool):
        self.id_anuncio = ID_ANUNCIO_DE_PRUEBA if desde_anuncio else None
        self.escalada = False
        self.esperando_pago = False
        self.en_gestion = False

    def obtener_por_id(self, conversacion_id: int) -> Dict[str, Any]:
        estado = "escalada" if self.escalada else "en_gestion" if self.en_gestion else "activa"
        return {
            "id": conversacion_id,
            "telefono": TELEFONO_DE_PRUEBA,
            "id_anuncio": self.id_anuncio,
            "origen": "fep" if self.id_anuncio else "directo",
            "estado": estado,
        }

    def marcar_escalada(self, conversacion_id: int) -> None:
        self.escalada = True

    def marcar_en_gestion(self, conversacion_id: int) -> None:
        self.en_gestion = True

    def marcar_esperando_pago(self, conversacion_id: int) -> None:
        self.esperando_pago = True


class LeadsEnMemoria:
    def __init__(self, lead: Dict[str, Any]):
        self.lead = lead

    def obtener_o_crear(self, conversacion_id: int, telefono: str) -> Dict[str, Any]:
        return dict(self.lead)

    def obtener_por_id(self, lead_id: int) -> Dict[str, Any]:
        return dict(self.lead)

    def obtener_por_conversacion(self, conversacion_id: int) -> Dict[str, Any]:
        return dict(self.lead)

    def actualizar_datos_cliente(self, lead_id, nombre_cliente=None, direccion=None, canton=None, provincia=None) -> None:
        # Mismo criterio que el UPDATE real (`coalesce`): lo que no llega no se borra.
        for campo, valor in (
            ("nombre_cliente", nombre_cliente),
            ("direccion", direccion),
            ("canton", canton),
            ("provincia", provincia),
        ):
            if valor is not None:
                self.lead[campo] = valor

    def actualizar_producto(self, lead_id, producto_sku, producto_nombre, total, variante=None, cantidad=1) -> None:
        # Igual que el UPDATE real: `total` es el subtotal y cambiar de producto borra la entrega elegida.
        self.lead.update(
            producto_sku=producto_sku, producto_nombre=producto_nombre, total=total, subtotal=total, cantidad=cantidad,
            entrega_opcion_id=None, entrega_nombre=None, entrega_tipo=None, costo_envio=Decimal("0.00"),
        )
        if variante is not None:
            self.lead["producto_variante"] = variante

    def actualizar_entrega(self, lead_id, opcion_id, nombre, tipo, costo_envio, total) -> None:
        self.lead.update(
            entrega_opcion_id=opcion_id, entrega_nombre=nombre, entrega_tipo=tipo,
            costo_envio=Decimal(str(costo_envio)), total=total,
        )

    def actualizar_metodo_pago(self, lead_id, metodo_pago, esperar_comprobante=True) -> None:
        self.lead["metodo_pago"] = metodo_pago
        if esperar_comprobante and metodo_pago == "transferencia":
            self.lead["estado"] = "esperando_pago"

    def actualizar_despacho(self, lead_id, id_pedido_local, id_pedido_rocketfy) -> None:
        self.lead.update(estado="despachado", id_pedido_local=id_pedido_local, id_pedido_rocketfy=id_pedido_rocketfy)


PREFIJO_DE_FOTO = "📷 Foto de "


class MensajesEnMemoria:
    """El historial que mandó la app más el mensaje nuevo del cliente como
    ÚLTIMA fila (así lo deja el webhook real antes de llamar a Victoria)."""

    def __init__(self, historial: List[Dict[str, str]], mensaje_nuevo: str):
        self.filas = [{"rol": h["rol"], "contenido": h["contenido"], "tipo": "texto"} for h in historial]
        self.filas.append({"rol": "cliente", "contenido": mensaje_nuevo, "tipo": "texto"})
        self.fotos_de_este_turno: List[str] = []

    def obtener_por_conversacion(self, conversacion_id: int) -> List[Dict[str, str]]:
        return list(self.filas)

    def crear(self, conversacion_id, rol, contenido, tipo="texto", wamid=None) -> Dict[str, str]:
        fila = {"rol": rol, "contenido": contenido, "tipo": tipo}
        self.filas.append(fila)
        if tipo == "imagen":
            self.fotos_de_este_turno.append(contenido)
        return fila

    def contar_fotos(self, conversacion_id: int, sku: str) -> int:
        # El historial que manda la app no trae el tipo: una foto se reconoce por su texto,
        # que lo escribe `tools.py` («📷 Foto de <nombre> (<sku>)»).
        return sum(
            1
            for f in self.filas
            if f["rol"] == "bot" and f"({sku})" in f["contenido"] and (f["tipo"] == "imagen" or f["contenido"].startswith(PREFIJO_DE_FOTO))
        )


class ProductosEnEnsayo:
    """El producto de la prueba como único producto disponible. Funciona aunque
    esté en borrador: la copia se marca activa SOLO aquí, nunca en la base."""

    def __init__(self, producto: Dict[str, Any]):
        self._producto = {**producto, "activo": True}

    def obtener_por_sku(self, sku: str) -> Optional[Dict[str, Any]]:
        return dict(self._producto) if sku == self._producto["sku"] else None

    def obtener_por_id_anuncio(self, id_anuncio: str) -> Optional[Dict[str, Any]]:
        return dict(self._producto) if id_anuncio == ID_ANUNCIO_DE_PRUEBA else None

    def listar_activos(self) -> List[Dict[str, Any]]:
        return [dict(self._producto)]


class EntregasEnEnsayo:
    """Las opciones de entrega del producto de la prueba, tal como están guardadas (se leen ANTES de la
    simulación, no durante)."""

    def __init__(self, entregas: Optional[List[Dict[str, Any]]]):
        self._entregas = [dict(e) for e in (entregas or [])]

    def listar(self, sku: str, solo_activas: bool = False) -> List[Dict[str, Any]]:
        return [dict(e) for e in self._entregas if not solo_activas or e.get("activo", True)]

    def obtener(self, opcion_id: int) -> Optional[Dict[str, Any]]:
        return next((dict(e) for e in self._entregas if e.get("id") == opcion_id), None)


class ImagenesEnEnsayo:
    """La galería del producto, tal como está guardada (se lee ANTES de la simulación, no durante)."""

    def __init__(self, imagenes: Optional[List[Dict[str, Any]]]):
        self._imagenes = [dict(i) for i in (imagenes or [])]

    def listar(self, sku: str) -> List[Dict[str, Any]]:
        return [dict(i) for i in self._imagenes]


class GestionEnEnsayo:
    """«Por gestionar» de mentira: anota lo que se le habría avisado al dueño y no guarda nada."""

    def __init__(self, telegram: "TelegramGrabador"):
        self._telegram = telegram
        self.solicitudes: List[Dict[str, Any]] = []
        self._pendiente: Optional[str] = None

    def solicitar(self, conversacion_id, lead_id, clave_tipo, detalle, telefono) -> ResultadoSolicitud:
        tipo = tipo_de_solicitud(clave_tipo)
        anterior = self._pendiente
        gana = anterior is None or tipo.prioridad > tipo_de_solicitud(anterior).prioridad
        final = tipo.clave if gana else anterior
        self._pendiente = final
        resultado = ResultadoUpsert(id=len(self.solicitudes) + 1, creada=anterior is None, tipo=final, tipo_anterior=anterior)
        if resultado.creada or resultado.cambio_de_tipo:
            etiqueta = tipo_de_solicitud(final).etiqueta
            self.solicitudes.append({"tipo": final, "etiqueta": etiqueta, "detalle": detalle or ""})
            self._telegram.notificar_gestion(etiqueta, conversacion_id, telefono, detalle or "")
        return ResultadoSolicitud(solicitud=resultado, traspasa=tipo.traspasa, etiqueta=tipo.etiqueta)

    def avisar_pedido_cerrado(self, datos: Dict[str, Any]) -> None:
        self._telegram.notificar_pedido_cerrado(datos)


class VentasEnEnsayo:
    """El cierre manual de mentira: arma la venta que SE HABRÍA guardado (con precio y costo congelados) y
    la deja a la vista, sin tocar la base, el stock ni nada."""

    def __init__(self, lead: Dict[str, Any], gestion: GestionEnEnsayo, conversaciones: ConversacionesEnMemoria):
        self._lead = lead
        self._gestion = gestion
        self._conversaciones = conversaciones
        self.venta: Optional[Dict[str, Any]] = None

    def registrar_venta_rocketfy(self, lead, producto, conversacion, entrega) -> None:
        pass  # el pedido de Rocketfy ya se ve en «pedido»; la foto de la venta no se guarda en la prueba

    def cerrar_manual(self, lead, producto, conversacion, entrega, controla_stock, detalle_solicitud) -> Dict[str, Any]:
        venta, lineas = armar_venta(lead, producto, conversacion, entrega, "por_gestionar", Decimal("0.00"))
        self.venta = {**venta, "lineas": lineas, "ganancia": ganancia_de(venta)}
        stock = producto.get("stock_ultimo")
        restante = stock - int(lead.get("cantidad") or 1) if controla_stock and stock is not None else None
        solicitud = ResultadoUpsert(id=1, creada=True, tipo="pedido_cerrado", tipo_anterior=None)
        self._lead["estado"] = "por_gestionar"
        self._conversaciones.en_gestion = True
        return {
            "venta_id": 0,
            "solicitud": solicitud,
            "stock_restante": restante,
            "pausado_por_agotado": restante is not None and restante <= 0,
        }


class StockEnEnsayo:
    """Lo último que se guardó del stock en la ficha. No se consulta Rocketfy."""

    def __init__(self, stock: Optional[int]):
        self._stock = stock

    def stock_de(self, sku: str, fresco: bool = False) -> Optional[int]:
        return self._stock


class MinimosEnEnsayo:
    def guardar(self, **datos) -> None:
        pass


class TelegramGrabador:
    """No avisa a nadie: deja a la vista el aviso que se habría enviado."""

    def __init__(self):
        self.avisos: List[Dict[str, str]] = []

    def notificar_escalado(self, conversacion_id: int, telefono: str, motivo: str) -> None:
        self.avisos.append({"canal": "telegram", "texto": f"Victoria escaló la conversación. Motivo: {motivo}"})

    def notificar_aviso(self, titulo: str, detalle: str) -> None:
        self.avisos.append({"canal": "telegram", "texto": f"{titulo}. {detalle}"})

    def notificar_gestion(self, etiqueta: str, conversacion_id: int, telefono: str, detalle: str = "") -> None:
        texto = f"Cierre previo: {etiqueta}" + (f". {detalle}" if detalle else "")
        self.avisos.append({"canal": "telegram", "texto": texto})

    def notificar_pedido_cerrado(self, datos: Dict[str, Any]) -> None:
        resumen = (
            f"Pedido cerrado, gestionar envío. {datos.get('producto')} · total ${datos.get('total')} · "
            f"entrega: {datos.get('entrega')} · pago: {datos.get('pago')} · {datos.get('cliente')}, {datos.get('direccion')}"
            + (f" · {datos['aviso']}" if datos.get("aviso") else "")
        )
        self.avisos.append({"canal": "telegram", "texto": resumen})


class WhatsAppGrabador:
    """No manda nada: anota la foto que se habría enviado al cliente."""

    def __init__(self):
        self.enviadas: List[Dict[str, str]] = []

    def enviar_imagen(self, telefono: str, url: str, descripcion: Optional[str] = None) -> dict:
        self.enviadas.append({"url": url, "descripcion": descripcion or ""})
        return {"messages": [{"id": "wamid.ensayo"}]}


class PedidosEnMemoria:
    """Mismo contrato que `PedidoRepository`, en un diccionario."""

    def __init__(self):
        self._filas: Dict[int, Dict[str, Any]] = {}

    def obtener(self, id_local: int) -> Optional[Dict[str, Any]]:
        fila = self._filas.get(id_local)
        return dict(fila) if fila else None

    def upsert_pendiente(self, id_local: int, payload_creacion: dict) -> None:
        ahora = datetime.now(timezone.utc)
        self._filas[id_local] = {
            "id_local": id_local,
            "id_rocketfy": None,
            "estado_local": "pendiente_creacion",
            "status_id_rocketfy": None,
            "payload_creacion": payload_creacion,
            "mensaje_error": None,
            "creado_en": ahora,
            "confirmado_en": None,
            "actualizado_en": ahora,
        }

    def marcar_creado(self, id_local: int, id_rocketfy: int, estado_local: str) -> None:
        self._filas[id_local].update(id_rocketfy=id_rocketfy, estado_local=estado_local)

    def marcar_error_creacion(self, id_local: int, mensaje: str) -> None:
        self._filas[id_local].update(estado_local="error", mensaje_error=mensaje)

    def marcar_confirmado(self, id_local: int) -> None:
        self._filas[id_local].update(
            estado_local="confirmado", confirmado_en=datetime.now(timezone.utc), mensaje_error=None
        )

    def marcar_error_confirmacion(self, id_local: int, mensaje: str) -> None:
        self._filas[id_local]["mensaje_error"] = mensaje


class RocketfyDeEnsayo:
    """Hace de cliente de Rocketfy, pero solo anota. Lo que recibe es el payload
    REAL que armó `PedidoService`: es la «vista previa» de lo que se enviaría."""

    def __init__(self):
        self.pedidos_creados: List[Dict[str, Any]] = []
        self.pedidos_confirmados: List[int] = []
        self._siguiente_id = ID_PEDIDO_SIMULADO_INICIAL

    def crear_pedido(self, payload: dict) -> dict:
        self.pedidos_creados.append(payload)
        id_simulado = self._siguiente_id
        self._siguiente_id += 1
        lineas = json.loads(payload["order_details"])
        return {"id": id_simulado, "products_stock": [{"sku": linea["sku"]} for linea in lineas]}

    def confirmar_pedido(self, order_id: Optional[int] = None, shopify_order_id: Optional[int] = None) -> dict:
        self.pedidos_confirmados.append(order_id)
        return {}


# ----------------------------------------------------------------------
# Ejecutor de herramientas con bitácora
# ----------------------------------------------------------------------
class HerramientasConBitacora(HerramientasVictoria):
    """Las herramientas reales de Victoria, anotando cada llamada para mostrarla
    en la app (qué herramienta usó, con qué datos y qué le respondió el sistema)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bitacora: List[Dict[str, Any]] = []

    def ejecutar(self, nombre, lead_id, conversacion_id, entrada, id_llamada):
        resultado = super().ejecutar(nombre, lead_id, conversacion_id, entrada, id_llamada)
        self.bitacora.append({"nombre": nombre, "entrada": dict(entrada or {}), "resultado": resultado.contenido})
        return resultado


# ----------------------------------------------------------------------
# Un turno
# ----------------------------------------------------------------------
@dataclass
class ResultadoDelTurno:
    respuesta: str
    herramientas: List[Dict[str, Any]]
    estado: Dict[str, Any]
    escalada: bool
    pedido: Optional[Dict[str, Any]]
    avisos: List[Dict[str, str]] = field(default_factory=list)
    fotos: List[Dict[str, str]] = field(default_factory=list)
    # ADR-012: la venta de un producto propio que SE HABRÍA guardado, y las solicitudes de gestión que se habrían abierto.
    venta_manual: Optional[Dict[str, Any]] = None
    solicitudes: List[Dict[str, Any]] = field(default_factory=list)


def simular_turno(
    producto: Dict[str, Any],
    mensaje: str,
    historial: List[Dict[str, str]],
    estado: Optional[Dict[str, Any]],
    desde_anuncio: bool,
    llm: LLMProvider,
    plantilla: Optional[str] = None,
    entregas: Optional[List[Dict[str, Any]]] = None,
    imagenes: Optional[List[Dict[str, Any]]] = None,
) -> ResultadoDelTurno:
    """Procesa UN mensaje del cliente de mentira y devuelve lo que Victoria
    respondió, qué herramientas usó y cómo quedó la venta. `producto` es la
    ficha tal como está guardada (misma forma que `productos_bot`)."""
    lead = lead_desde_estado(estado)
    conversaciones = ConversacionesEnMemoria(desde_anuncio)
    leads = LeadsEnMemoria(lead)
    mensajes = MensajesEnMemoria(historial, mensaje)
    productos = ProductosEnEnsayo(producto)
    rocketfy = RocketfyDeEnsayo()
    telegram = TelegramGrabador()
    whatsapp = WhatsAppGrabador()
    gestion = GestionEnEnsayo(telegram)
    ventas = VentasEnEnsayo(leads.lead, gestion, conversaciones)

    pedidos = PedidoService(client=rocketfy, repo=PedidosEnMemoria())
    herramientas = HerramientasConBitacora(
        lead_repo=leads,
        conversacion_repo=conversaciones,
        producto_repo=productos,
        pedido_service=pedidos,
        telegram_notifier=telegram,
        stock_checker=StockEnEnsayo(producto.get("stock_ultimo")),
        minimo_repo=MinimosEnEnsayo(),
        mensaje_repo=mensajes,
        whatsapp_client=whatsapp,
        enviar_fotos=True,
        entrega_repo=EntregasEnEnsayo(entregas),
        gestion_service=gestion,
        ventas_service=ventas,
        imagen_repo=ImagenesEnEnsayo(imagenes),
    )
    cerebro = VictoriaConversationService(
        llm_client=llm,
        lead_repo=leads,
        conversacion_repo=conversaciones,
        mensaje_repo=mensajes,
        producto_repo=productos,
        ejecutor_herramientas=herramientas,
        # None = las instrucciones que rigen hoy con los clientes; un texto = las del borrador
        # (que se prueba aquí antes de publicarlo).
        plantilla=plantilla,
        entrega_repo=EntregasEnEnsayo(entregas),
        # La simulación SIEMPRE ofrece la foto, aunque en producción esté apagada
        # (parámetro «Enviar fotos»): así se puede ver cómo la usa Victoria antes de encenderla.
        enviar_fotos=True,
    )
    respuesta = cerebro.procesar_turno(lead["conversacion_id"], mensaje)

    pedido = None
    if rocketfy.pedidos_creados:
        pedido = {
            "payload": rocketfy.pedidos_creados[-1],
            "confirmado": bool(rocketfy.pedidos_confirmados),
        }
    return ResultadoDelTurno(
        respuesta=respuesta,
        herramientas=herramientas.bitacora,
        estado=estado_desde_lead(leads.lead),
        escalada=conversaciones.escalada or conversaciones.en_gestion,
        pedido=pedido,
        avisos=telegram.avisos,
        venta_manual=_venta_para_mostrar(ventas.venta),
        solicitudes=gestion.solicitudes,
        fotos=[
            {"mensaje": mensaje_de_la_foto, "url": enviada["url"], "descripcion": enviada["descripcion"]}
            for mensaje_de_la_foto, enviada in zip(mensajes.fotos_de_este_turno, whatsapp.enviadas)
        ],
    )


def _venta_para_mostrar(venta: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """La venta del cierre manual con el dinero como string (nunca float) y sin los ids internos."""
    if venta is None:
        return None

    def dinero(valor):
        return f"{Decimal(str(valor)):.2f}" if valor is not None else None

    linea = venta["lineas"][0]
    return {
        "producto": linea["producto_nombre"],
        "variante": linea["variante"],
        "cantidad": linea["cantidad"],
        "subtotal": dinero(venta["subtotal"]),
        "costo_envio_cliente": dinero(venta["costo_envio_cliente"]),
        "total": dinero(venta["total"]),
        "costo_productos": dinero(venta["costo_productos"]),
        "costo_envio_negocio": dinero(venta["costo_envio_negocio"]),
        "ganancia": dinero(venta["ganancia"]),
        "entrega": venta["entrega_nombre"],
        "metodo_pago": venta["metodo_pago"],
        "canal": venta["canal"],
    }
