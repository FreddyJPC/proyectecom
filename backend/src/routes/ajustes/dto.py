from dataclasses import dataclass
from decimal import Decimal
from typing import Optional


@dataclass(frozen=True)
class AjustesNegocio:
    """Los números del negocio con los que se calcula el precio (Fase C).

    Los valores por defecto son los de PARTIDA de la propuesta del plan
    (docs/PLAN_GESTION_PRODUCTOS.md, decisión 1) y son lo mismo que trae la
    fila inicial de la migración 015. Mientras `confirmado` sea falso, el dueño
    todavía no los ha revisado: la app lo avisa y no los usa para bloquear.

    Los porcentajes están en porcentaje (25 = 25 %), no como fracción. El
    margen es ganancia / precio de venta (no recargo sobre el costo).
    """

    margen_minimo_pct: Decimal = Decimal("25.00")
    margen_objetivo_pct: Decimal = Decimal("35.00")
    envio_estimado: Decimal = Decimal("5.00")
    otros_costos_fijos: Decimal = Decimal("0.00")
    otros_costos_pct: Decimal = Decimal("0.00")
    redondeo: str = "terminado_99"
    # Borradores de IA permitidos por día (propuesta del plan: 20). Cada uno cuesta plata.
    tope_redacciones_dia: int = 20
    confirmado: bool = False
    actualizado_por: Optional[str] = None
    actualizado_en: Optional[str] = None


@dataclass
class CalibracionEnvioDTO:
    """Lo que sugieren los rechazos de Rocketfy por importe mínimo sobre el
    costo real de envío. Dinero como string con dos decimales."""

    observaciones: int
    minimo: str
    mediana: str
    maximo: str


@dataclass
class AjustesRespuestaDTO:
    margen_minimo_pct: str
    margen_objetivo_pct: str
    envio_estimado: str
    otros_costos_fijos: str
    otros_costos_pct: str
    redondeo: str
    tope_redacciones_dia: int
    confirmado: bool
    actualizado_por: Optional[str]
    actualizado_en: Optional[str]
    calibracion_envio: Optional[CalibracionEnvioDTO]
