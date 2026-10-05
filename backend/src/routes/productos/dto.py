from dataclasses import dataclass
from typing import Optional


@dataclass
class SkuMonitoreadoInputDTO:
    sku: str
    umbral_stock_minimo: int = 5


@dataclass
class SkuMonitoreadoDTO:
    sku: str
    umbral_stock_minimo: int
    activo: bool
    ultimo_stock: Optional[int] = None
    ultimo_precio: Optional[str] = None
    ultimo_snapshot_en: Optional[str] = None
