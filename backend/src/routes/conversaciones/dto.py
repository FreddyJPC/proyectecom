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
    telefono: str
    nombre_cliente: Optional[str]
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
class ConversacionDetalleDTO:
    id: int
    telefono: str
    origen: str
    estado: str
    id_anuncio: Optional[str]
    notas_internas: Optional[str]
    ventana_abierta: bool
    ventana_expira_en: Optional[str]
    creada_en: Optional[str]
    actualizada_en: Optional[str]


@dataclass
class MensajeDTO:
    id: int
    rol: str
    contenido: str
    tipo: str
    creado_en: Optional[str]


@dataclass
class DetalleCompletoDTO:
    conversacion: ConversacionDetalleDTO
    lead: Optional[LeadDTO]
    mensajes: List[MensajeDTO]
