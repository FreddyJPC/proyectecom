"""Acceso a datos de la conexión con Meta (ADR-016): el dataset guardado y el resumen de los eventos enviados. Todo SQL va con parámetros."""
from typing import Any, Dict, List, Optional

from src.config.database import get_connection

ESTADOS = ("pendiente", "enviando", "enviado", "fallido", "dudoso", "descartado")


class MetaRepository:
    @staticmethod
    def dataset_id() -> Optional[str]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("select meta_dataset_id from ajustes_negocio where id = 1")
                fila = cur.fetchone()
        valor = (fila[0] if fila else None) or None
        return valor.strip() if isinstance(valor, str) and valor.strip() else None

    @staticmethod
    def guardar_dataset_id(dataset_id: str) -> None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("update ajustes_negocio set meta_dataset_id = %s where id = 1", (dataset_id,))

    @staticmethod
    def cuenta_publicitaria() -> Optional[str]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("select meta_cuenta_publicitaria from ajustes_negocio where id = 1")
                fila = cur.fetchone()
        valor = fila[0] if fila else None
        return valor.strip() if isinstance(valor, str) and valor.strip() else None

    @staticmethod
    def guardar_cuenta_publicitaria(cuenta: Optional[str]) -> None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("update ajustes_negocio set meta_cuenta_publicitaria = %s where id = 1", (cuenta,))

    @staticmethod
    def resumen_eventos() -> Dict[str, int]:
        """Cuántos eventos hay en cada estado (todos los estados aparecen, aunque sea con 0)."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("select estado, count(*) from eventos_meta group by estado")
                contados = {estado: int(n) for estado, n in cur.fetchall()}
        return {estado: contados.get(estado, 0) for estado in ESTADOS}

    @staticmethod
    def ultimos_eventos(limite: int = 10) -> List[Dict[str, Any]]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "select id, venta_id, estado, motivo, valor, moneda, intentos, creado_en, enviado_en "
                    "from eventos_meta order by id desc limit %s",
                    (limite,),
                )
                columnas = [d[0] for d in cur.description]
                return [dict(zip(columnas, fila)) for fila in cur.fetchall()]
