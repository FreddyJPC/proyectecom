import logging
from typing import List, Optional

from src.integrations.rocketfy import RocketfyClient

from .dto import SkuMonitoreadoDTO, SkuMonitoreadoInputDTO
from .exceptions import SkuNoExisteEnRocketfyError
from .repository import SkuMonitoreadoRepository

logger = logging.getLogger(__name__)


class ProductosService:
    def __init__(self, client: RocketfyClient, repo: Optional[SkuMonitoreadoRepository] = None):
        self._client = client
        self._repo = repo or SkuMonitoreadoRepository()

    def agregar_sku_monitoreado(self, dto: SkuMonitoreadoInputDTO) -> None:
        contenido = self._client.listar_productos(q=dto.sku)
        objetivo = dto.sku.strip().upper()
        existe = any(
            str(p.get("sku", "")).strip().upper() == objetivo for p in contenido.get("data", [])
        )
        if not existe:
            raise SkuNoExisteEnRocketfyError(f"El SKU '{dto.sku}' no existe en el catálogo de Rocketfy.")
        self._repo.upsert(dto.sku, dto.umbral_stock_minimo)
        logger.info("SKU agregado a monitoreo: %s (umbral=%s)", dto.sku, dto.umbral_stock_minimo)

    def quitar_sku_monitoreado(self, sku: str) -> bool:
        return self._repo.desactivar(sku)

    def listar_monitoreados(self, solo_activos: bool = True) -> List[SkuMonitoreadoDTO]:
        filas = self._repo.listar(solo_activos=solo_activos)
        return [
            SkuMonitoreadoDTO(
                sku=f["sku"],
                umbral_stock_minimo=f["umbral_stock_minimo"],
                activo=f["activo"],
                ultimo_stock=f["stock"],
                ultimo_precio=str(f["price"]) if f["price"] is not None else None,
                ultimo_snapshot_en=f["capturado_en"].isoformat() if f["capturado_en"] else None,
            )
            for f in filas
        ]
