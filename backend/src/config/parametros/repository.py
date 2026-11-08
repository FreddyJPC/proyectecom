"""
Acceso a las tablas `parametros_sistema` y `parametros_historial` (migración 018).
Solo SQL: la validación y las reglas de prioridad viven en servicio.py y catalogo.py.
"""
from typing import Any, Dict, List, Optional

from src.config.database import get_connection


class ParametrosRepository:
    @staticmethod
    def listar() -> Dict[str, Dict[str, Any]]:
        """Todos los valores guardados desde la app, por clave. La tabla es pequeña
        (a lo sumo una fila por parámetro del catálogo): una sola consulta basta."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("select clave, valor, actualizado_por, actualizado_en from parametros_sistema")
                return {
                    clave: {"valor": valor, "actualizado_por": por, "actualizado_en": en}
                    for clave, valor, por, en in cur.fetchall()
                }

    @staticmethod
    def guardar(clave: str, valor: str, usuario: Optional[str]) -> bool:
        """Guarda el valor y anota el cambio en el historial, en una sola transacción.
        Devuelve False (sin escribir nada) si ya valía eso."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("select valor from parametros_sistema where clave = %s for update", (clave,))
                fila = cur.fetchone()
                anterior = fila[0] if fila else None
                if anterior == valor:
                    return False
                cur.execute(
                    """
                    insert into parametros_sistema (clave, valor, actualizado_por, actualizado_en)
                    values (%s, %s, %s, now())
                    on conflict (clave) do update
                       set valor = excluded.valor,
                           actualizado_por = excluded.actualizado_por,
                           actualizado_en = now()
                    """,
                    (clave, valor, usuario),
                )
                cur.execute(
                    "insert into parametros_historial (clave, valor_anterior, valor_nuevo, usuario) values (%s, %s, %s, %s)",
                    (clave, anterior, valor, usuario),
                )
                return True

    @staticmethod
    def restaurar(clave: str, usuario: Optional[str]) -> bool:
        """Borra el valor guardado (vuelve al de la variable del servidor o al del código)
        y lo anota en el historial. Devuelve False si no había nada guardado."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("delete from parametros_sistema where clave = %s returning valor", (clave,))
                fila = cur.fetchone()
                if fila is None:
                    return False
                cur.execute(
                    "insert into parametros_historial (clave, valor_anterior, valor_nuevo, usuario) values (%s, %s, null, %s)",
                    (clave, fila[0], usuario),
                )
                return True

    @staticmethod
    def historial(limite: int = 50) -> List[Dict[str, Any]]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select clave, valor_anterior, valor_nuevo, usuario, creado_en
                      from parametros_historial
                     order by creado_en desc, id desc
                     limit %s
                    """,
                    (limite,),
                )
                columnas = [d[0] for d in cur.description]
                return [dict(zip(columnas, fila)) for fila in cur.fetchall()]
