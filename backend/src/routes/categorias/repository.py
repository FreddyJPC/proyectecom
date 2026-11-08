"""Categorías de producto (tabla `categorias_producto`, migración 020): sirven para medir qué tipo de producto deja más."""
from typing import Any, Dict, List, Optional

import psycopg2.errors

from src.config.database import get_connection


class CategoriaYaExisteError(Exception):
    pass


class CategoriaRepository:
    @staticmethod
    def listar(incluir_inactivas: bool = False) -> List[Dict[str, Any]]:
        filtro = "" if incluir_inactivas else "where c.activo = true"
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    select c.id, c.nombre, c.activo,
                           (select count(*) from productos_bot p where p.categoria_id = c.id) as productos
                      from categorias_producto c {filtro}
                     order by lower(c.nombre)
                    """
                )
                cols = [d[0] for d in cur.description]
                return [dict(zip(cols, fila)) for fila in cur.fetchall()]

    @staticmethod
    def obtener(categoria_id: int) -> Optional[Dict[str, Any]]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("select id, nombre, activo from categorias_producto where id = %s", (categoria_id,))
                fila = cur.fetchone()
                return dict(zip([d[0] for d in cur.description], fila)) if fila else None

    @staticmethod
    def crear(nombre: str) -> Dict[str, Any]:
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "insert into categorias_producto (nombre) values (%s) returning id, nombre, activo", (nombre,)
                    )
                    fila = cur.fetchone()
                    return dict(zip([d[0] for d in cur.description], fila))
        except psycopg2.errors.UniqueViolation as exc:
            raise CategoriaYaExisteError(f"Ya existe una categoría llamada «{nombre}».") from exc

    @staticmethod
    def actualizar(categoria_id: int, nombre: Optional[str], activo: Optional[bool]) -> Optional[Dict[str, Any]]:
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        update categorias_producto set
                            nombre = coalesce(%s, nombre), activo = coalesce(%s, activo)
                        where id = %s returning id, nombre, activo
                        """,
                        (nombre, activo, categoria_id),
                    )
                    fila = cur.fetchone()
                    return dict(zip([d[0] for d in cur.description], fila)) if fila else None
        except psycopg2.errors.UniqueViolation as exc:
            raise CategoriaYaExisteError(f"Ya existe una categoría llamada «{nombre}».") from exc
