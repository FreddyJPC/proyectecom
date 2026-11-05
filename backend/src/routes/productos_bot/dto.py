from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class VerificacionDTO:
    bloqueos: List[str]
    avisos: List[str]


@dataclass
class HistorialDTO:
    accion: str
    usuario: Optional[str]
    cambios: Optional[dict]
    creado_en: Optional[str]


@dataclass
class ProductoBotResumenDTO:
    """Una fila de la lista "Mis productos". El dinero siempre viaja como
    string con dos decimales (nunca float)."""

    sku: str
    nombre: str
    estado: str
    precio: str
    costo_rocketfy: Optional[str]
    stock_ultimo: Optional[int]
    max_unidades_por_pedido: int
    imagen_url: Optional[str]
    publicado_en: Optional[str]
    actualizado_en: Optional[str]


@dataclass
class ProductoBotDetalleDTO:
    sku: str
    nombre: str
    estado: str
    precio: str
    costo_rocketfy: Optional[str]
    precio_sugerido_rocketfy: Optional[str]
    stock_ultimo: Optional[int]
    stock_actualizado_en: Optional[str]
    peso_kg: Optional[str]
    imagen_url: Optional[str]
    rocketfy_product_id: Optional[int]
    descripcion: str
    variantes: Optional[str]
    tiempo_entrega: str
    metodos_pago: List[str]
    preguntas_frecuentes: Optional[str]
    temas_no_responder: Optional[str]
    max_unidades_por_pedido: int
    notas_internas: Optional[str]
    publicado_en: Optional[str]
    publicado_por: Optional[str]
    creado_en: Optional[str]
    actualizado_en: Optional[str]
    verificacion: VerificacionDTO
    historial: List[HistorialDTO] = field(default_factory=list)
