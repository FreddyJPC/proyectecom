"""
Acceso a la tabla `victoria_instrucciones_versiones` (migración 019). Solo SQL: las reglas del
texto viven en instrucciones.py y el flujo borrador → publicada en el servicio de la API.
"""
from typing import Any, Dict, List, Optional

from psycopg2.extras import Json

from src.config.database import get_connection

_COLUMNAS = "id, secciones, estado, nota, creado_por, creado_en, publicada_en"


def _fila(cur) -> Optional[Dict[str, Any]]:
    row = cur.fetchone()
    if row is None:
        return None
    return dict(zip([d[0] for d in cur.description], row))


class InstruccionesRepository:
    @staticmethod
    def publicada() -> Optional[Dict[str, Any]]:
        """La versión que usa Victoria con los clientes, o None si rige el texto original del código."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"select {_COLUMNAS} from victoria_instrucciones_versiones where estado = 'publicada'")
                return _fila(cur)

    @staticmethod
    def borrador() -> Optional[Dict[str, Any]]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"select {_COLUMNAS} from victoria_instrucciones_versiones where estado = 'borrador'")
                return _fila(cur)

    @staticmethod
    def obtener(id_version: int) -> Optional[Dict[str, Any]]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"select {_COLUMNAS} from victoria_instrucciones_versiones where id = %s", (id_version,))
                return _fila(cur)

    @staticmethod
    def versiones(limite: int = 20) -> List[Dict[str, Any]]:
        """Las últimas versiones (borrador, publicada y archivadas), de la más nueva a la más vieja."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"select {_COLUMNAS} from victoria_instrucciones_versiones order by id desc limit %s", (limite,)
                )
                columnas = [d[0] for d in cur.description]
                return [dict(zip(columnas, fila)) for fila in cur.fetchall()]

    @staticmethod
    def guardar_borrador(secciones: Dict[str, str], nota: Optional[str], usuario: Optional[str]) -> Dict[str, Any]:
        """Crea el borrador o, si ya había uno, lo reemplaza (a lo sumo hay uno: lo garantiza un índice único)."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("select id from victoria_instrucciones_versiones where estado = 'borrador' for update")
                existente = cur.fetchone()
                if existente:
                    cur.execute(
                        f"""
                        update victoria_instrucciones_versiones
                           set secciones = %s, nota = %s, creado_por = %s, creado_en = now()
                         where id = %s
                        returning {_COLUMNAS}
                        """,
                        (Json(secciones), nota, usuario, existente[0]),
                    )
                else:
                    cur.execute(
                        f"""
                        insert into victoria_instrucciones_versiones (secciones, estado, nota, creado_por)
                        values (%s, 'borrador', %s, %s)
                        returning {_COLUMNAS}
                        """,
                        (Json(secciones), nota, usuario),
                    )
                return _fila(cur)

    @staticmethod
    def descartar_borrador() -> bool:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("delete from victoria_instrucciones_versiones where estado = 'borrador'")
                return cur.rowcount > 0

    @staticmethod
    def publicar_borrador(nota: Optional[str]) -> Optional[Dict[str, Any]]:
        """El borrador pasa a ser la versión publicada y la que lo era hasta ahora queda archivada,
        todo en una sola transacción: nunca hay un momento sin versión o con dos. None si no hay borrador."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("select id, nota from victoria_instrucciones_versiones where estado = 'borrador' for update")
                borrador = cur.fetchone()
                if borrador is None:
                    return None
                cur.execute("update victoria_instrucciones_versiones set estado = 'archivada' where estado = 'publicada'")
                cur.execute(
                    f"""
                    update victoria_instrucciones_versiones
                       set estado = 'publicada', publicada_en = now(), nota = coalesce(%s, nota)
                     where id = %s
                    returning {_COLUMNAS}
                    """,
                    (nota, borrador[0]),
                )
                return _fila(cur)

    @staticmethod
    def volver_a_la_original() -> bool:
        """Deja de haber versión publicada: Victoria vuelve a usar el texto original del código.
        La versión que estaba publicada queda archivada (se puede volver a cargar)."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("update victoria_instrucciones_versiones set estado = 'archivada' where estado = 'publicada'")
                return cur.rowcount > 0
