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


@dataclass
class CamposContenidoDTO:
    """Los campos de contenido que redacta la IA. Solo vienen los pedidos."""

    nombre: Optional[str] = None
    descripcion: Optional[str] = None
    variantes: Optional[str] = None
    preguntas_frecuentes: Optional[str] = None
    temas_no_responder: Optional[str] = None


@dataclass
class AlertaContenidoDTO:
    campo: Optional[str]  # camelCase; None = alerta general
    texto: str
    origen: str  # "ia" (la escribió el modelo) | "verificacion" (la detectó el código)


@dataclass
class UsoIADTO:
    tope: int
    usadas: int
    restantes: int


@dataclass
class BorradorContenidoDTO:
    """Un borrador de la IA. NO está guardado en ninguna parte: la persona lo
    acepta, lo edita o lo descarta, y recién entonces pasa a la ficha."""

    campos: CamposContenidoDTO
    fuentes: CamposContenidoDTO
    alertas: List[AlertaContenidoDTO]
    uso: UsoIADTO



@dataclass
class LlamadaHerramientaDTO:
    """Una herramienta que Victoria usó en un turno de la prueba."""

    nombre: str
    entrada: dict
    resultado: str


@dataclass
class PedidoSimuladoDTO:
    """El pedido que SE HABRÍA enviado a Rocketfy (no se envió nada)."""

    payload: dict
    confirmado: bool


@dataclass
class AvisoSimuladoDTO:
    canal: str
    texto: str


@dataclass
class TurnoSimuladoDTO:
    """Un turno de la prueba. `estado` es la venta en curso: la app lo guarda y
    lo reenvía en el siguiente turno (el servidor no guarda nada de la prueba)."""

    respuesta: str
    herramientas: List[LlamadaHerramientaDTO]
    estado: dict
    escalada: bool
    pedido: Optional[PedidoSimuladoDTO]
    avisos: List[AvisoSimuladoDTO]
    uso: UsoIADTO
