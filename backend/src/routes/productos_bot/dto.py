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
    precio_competencia: Optional[str] = None
    historial: List[HistorialDTO] = field(default_factory=list)


@dataclass
class NivelPrecioDTO:
    clave: str
    nombre: str
    precio: str
    ganancia: str
    margen_pct: str


@dataclass
class EvaluacionPrecioDTO:
    precio: str
    ganancia: str
    margen_pct: str
    bajo_piso: bool
    bajo_margen_minimo: bool


@dataclass
class RecomendacionPrecioDTO:
    """Respuesta de la calculadora de precio. Dinero como string con dos
    decimales y márgenes como string con un decimal (nunca float)."""

    ajustes_confirmados: bool
    costo: Optional[str]
    piso: str
    envio_estimado: str
    otros_costos_fijos: str
    otros_costos_pct: str
    margen_minimo_pct: str
    margen_objetivo_pct: str
    precio_sugerido: Optional[str]
    precio_competencia: Optional[str]
    niveles: List[NivelPrecioDTO]
    evaluacion: Optional[EvaluacionPrecioDTO]
    avisos: List[str]
