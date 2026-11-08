"""Acceso a datos de la galería (tabla `imagenes_producto`, migración 021)."""
from typing import Any, Dict, List, Optional

import psycopg2.errors

from src.config.database import get_connection

_COLUMNAS = "id, producto_sku, url, storage_path, orden, creado_en, creado_por"


class ImagenYaRegistradaError(Exception):
    pass


class ImagenRepository:
    @staticmethod
    def listar(sku: str) -> List[Dict[str, Any]]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"select {_COLUMNAS} from imagenes_producto where producto_sku = %s order by orden, id", (sku,))
                cols = [d[0] for d in cur.description]
                return [dict(zip(cols, fila)) for fila in cur.fetchall()]

    @staticmethod
    def agregar(sku: str, url: str, storage_path: str, usuario: Optional[str]) -> Dict[str, Any]:
        """Agrega la foto al final de la galería."""
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        insert into imagenes_producto (producto_sku, url, storage_path, orden, creado_por)
                        values (%s, %s, %s, coalesce((select max(orden) + 1 from imagenes_producto where producto_sku = %s), 0), %s)
                        returning {_COLUMNAS}
                        """,
                        (sku, url, storage_path, sku, usuario),
                    )
                    fila = cur.fetchone()
                    return dict(zip([d[0] for d in cur.description], fila))
        except psycopg2.errors.UniqueViolation as exc:
            raise ImagenYaRegistradaError("Esa foto ya está registrada.") from exc

    @staticmethod
    def quitar(sku: str, imagen_id: int) -> Optional[Dict[str, Any]]:
        """Borra la foto de la galería y devuelve su fila (para que la app borre también el archivo)."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"delete from imagenes_producto where id = %s and producto_sku = %s returning {_COLUMNAS}",
                    (imagen_id, sku),
                )
                fila = cur.fetchone()
                return dict(zip([d[0] for d in cur.description], fila)) if fila else None

    @staticmethod
    def reordenar(sku: str, ids_en_orden: List[int]) -> List[Dict[str, Any]]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                for orden, imagen_id in enumerate(ids_en_orden):
                    cur.execute(
                        "update imagenes_producto set orden = %s where id = %s and producto_sku = %s",
                        (orden, imagen_id, sku),
                    )
        return ImagenRepository.listar(sku)
