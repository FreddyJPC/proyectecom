from typing import Optional

from .repository import IncidenciasRepository


class IncidenciasService:
    def __init__(self, repo: Optional[IncidenciasRepository] = None):
        self._repo = repo or IncidenciasRepository()

    def listar_eventos(self, solo_incidencias: bool = True, page: int = 1, page_size: int = 20) -> dict:
        offset = (page - 1) * page_size
        return {
            "items": self._repo.listar_eventos_webhook(solo_incidencias, page_size, offset),
            "total": self._repo.contar_eventos_webhook(solo_incidencias),
            "page": page,
            "page_size": page_size,
        }

    def listar_alertas(self, sku: Optional[str] = None, page: int = 1, page_size: int = 20) -> dict:
        offset = (page - 1) * page_size
        return {
            "items": self._repo.listar_alertas_stock(sku, page_size, offset),
            "total": self._repo.contar_alertas_stock(sku),
            "page": page,
            "page_size": page_size,
        }
