from dataclasses import dataclass
from decimal import Decimal
from typing import List, Optional


@dataclass
class UltimoMensajeDTO:
    rol: str
    contenido: str
    creado_en: Optional[str]


@dataclass
class ConversacionResumenDTO:
    """Fase 3.2 (módulo de Conversaciones): una fila del listado -- ya
    trae resuelto el nombre/producto del lead y el último mensaje, para
    que el frontend no tenga que pedirlos aparte por conversación."""

    id: int
    canal: str                      # whatsapp | instagram | messenger
    id_externo: Optional[str]       # identificador del cliente en ese canal (WhatsApp: su teléfono)
    telefono: Optional[str]         # puede faltar en canales que no lo dan
    nombre: Optional[str]           # nombre del contacto (perfil del canal o el que dio al comprar)
    nombre_cliente: Optional[str]   # nombre que dio en el lead actual
    origen: str
    estado: str
    producto_interes: Optional[str]
    sin_revisar: bool
    ultimo_mensaje: Optional[UltimoMensajeDTO]
    creada_en: Optional[str]
    actualizada_en: Optional[str]


@dataclass
class TotalesPorFiltroRapidoDTO:
    escaladas: int
    escaladas_sin_revisar: int
    esperando_pago: int
    en_gestion: int = 0


@dataclass
class ListaConversacionesDTO:
    items: List[ConversacionResumenDTO]
    total: int
    page: int
    page_size: int
    totales_por_filtro_rapido: TotalesPorFiltroRapidoDTO


@dataclass
class LeadDTO:
    nombre_cliente: Optional[str]
    direccion: Optional[str]
    canton: Optional[str]
    provincia: Optional[str]
    producto_sku: Optional[str]
    producto_nombre: Optional[str]
    producto_variante: Optional[str]
    total: Optional[Decimal]
    metodo_pago: Optional[str]
    estado_pago: Optional[str]
    estado: Optional[str]
    id_pedido_local: Optional[int]
    id_pedido_rocketfy: Optional[int]


@dataclass
class VentanaGratuitaDTO:
    """La ventana gratuita de Meta para clientes que llegan por anuncio (informativa: no decide si se puede escribir).
    estado: sin_anuncio | pendiente | abierta | cerrada."""

    estado: str
    expira_en: Optional[str]
    responder_antes_de: Optional[str]


@dataclass
class ProductoDeAnuncioDTO:
    sku: str
    nombre: str


@dataclass
class AnuncioDTO:
    """El anuncio más reciente por el que llegó este cliente, con lo que Meta mandó de él."""

    id_anuncio: Optional[str]
    titulo: Optional[str]
    texto: Optional[str]
    url_anuncio: Optional[str]
    tipo_origen: Optional[str]
    tipo_media: Optional[str]
    imagen_url: Optional[str]
    miniatura_url: Optional[str]
    producto: Optional[ProductoDeAnuncioDTO]
    llegadas: int


@dataclass
class LlegadaPorAnuncioDTO:
    id_anuncio: Optional[str]
    titulo: Optional[str]
    creado_en: Optional[str]


@dataclass
class ConversacionDetalleDTO:
    id: int
    contacto_id: int
    canal: str
    id_externo: str
    telefono: Optional[str]
    nombre: Optional[str]
    origen: str
    estado: str
    id_anuncio: Optional[str]
    notas_internas: Optional[str]
    ventana_abierta: bool
    ventana_expira_en: Optional[str]
    creada_en: Optional[str]
    actualizada_en: Optional[str]
    ventana_gratuita: Optional[VentanaGratuitaDTO] = None
    anuncio: Optional[AnuncioDTO] = None
    llegadas_por_anuncio: Optional[List[LlegadaPorAnuncioDTO]] = None


@dataclass
class MensajeDTO:
    id: int
    rol: str
    contenido: str
    tipo: str
    creado_en: Optional[str]
    # Si el mensaje trae un archivo (foto, audio, PDF) y lo que se entendió de él (descripción o transcripción).
    tiene_archivo: bool = False
    analisis: Optional[str] = None


@dataclass
class DetalleCompletoDTO:
    conversacion: ConversacionDetalleDTO
    lead: Optional[LeadDTO]
    mensajes: List[MensajeDTO]
