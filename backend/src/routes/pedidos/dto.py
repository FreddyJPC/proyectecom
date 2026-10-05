from dataclasses import dataclass
from decimal import Decimal
from typing import List, Optional


@dataclass
class LineaPedidoDTO:
    sku: str
    nombre: str
    cantidad: int


@dataclass
class CrearPedidoInputDTO:
    id_local: int
    nombre_cliente: str
    telefono: str
    direccion: str
    canton: str
    provincia: str
    total: Decimal
    lineas: List[LineaPedidoDTO]
    direccion_2: str = ""
    email: Optional[str] = None
    codigo_postal: Optional[str] = None
    no_contra_entrega: bool = False
    observaciones_transportista: str = ""
    tienda_id: Optional[int] = None
    ip: Optional[str] = None
    latitud: Optional[float] = None
    longitud: Optional[float] = None


@dataclass
class ModificarPedidoInputDTO:
    """Todos opcionales a propósito: /orders/modify solo aplica los campos
    enviados y conserva el resto (sección 8.1 del doc del proveedor). No
    incluye líneas de producto ni total: eso no se puede modificar, hay que
    rechazar y crear un pedido nuevo."""
    nombre_cliente: Optional[str] = None
    email: Optional[str] = None
    telefono: Optional[str] = None
    direccion: Optional[str] = None
    direccion_2: Optional[str] = None
    canton: Optional[str] = None
    provincia: Optional[str] = None
    codigo_postal: Optional[str] = None


@dataclass
class PedidoDTO:
    id_local: int
    id_rocketfy: Optional[int]
    estado_local: str
    status_id_rocketfy: Optional[int]
    mensaje_error: Optional[str]
    creado_en: Optional[str]
    confirmado_en: Optional[str]
    actualizado_en: Optional[str]


@dataclass
class PedidoResumenDTO:
    """Para el listado (Fase 2 - Etapa 2 del frontend): lo mínimo para
    identificar un pedido en una tabla, sin traer todo payload_creacion."""
    id_local: int
    id_rocketfy: Optional[int]
    estado_local: str
    status_id_rocketfy: Optional[int]
    nombre_cliente: str
    telefono: str
    canton: str
    provincia: str
    total: Decimal
    creado_en: Optional[str]
    actualizado_en: Optional[str]


@dataclass
class PedidoDetalleDTO:
    """Vista de detalle: todo lo que se guardó al crear el pedido más el
    estado actual. No incluye historial de eventos del webhook -- eso es
    de la Etapa 3 (Incidencias)."""
    id_local: int
    id_rocketfy: Optional[int]
    estado_local: str
    status_id_rocketfy: Optional[int]
    mensaje_error: Optional[str]
    nombre_cliente: str
    telefono: str
    direccion: str
    direccion_2: str
    canton: str
    provincia: str
    codigo_postal: Optional[str]
    total: Decimal
    no_contra_entrega: bool
    observaciones_transportista: str
    lineas: List[LineaPedidoDTO]
    creado_en: Optional[str]
    confirmado_en: Optional[str]
    actualizado_en: Optional[str]
