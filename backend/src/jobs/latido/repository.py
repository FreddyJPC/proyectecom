from typing import Tuple

from src.config.database import get_connection


class LatidoRepository:
    @staticmethod
    def registrar_latido() -> Tuple[object, int]:
        """Escribe el latido y hace una lectura de una tabla real, ambas en
        la misma conexión. Devuelve (momento del latido, contador).

        El upsert (insert ... on conflict do update) es a propósito: si por
        algún motivo la fila id=1 no existiera, se recrea en vez de fallar
        en silencio con un update que no toca nada."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into latido (id) values (1)
                    on conflict (id) do update
                        set ultimo_latido = now(), contador = latido.contador + 1
                    returning ultimo_latido, contador
                    """
                )
                ultimo_latido, contador = cur.fetchone()
                # Lectura de una tabla de negocio: es una consulta de
                # "usuario" de verdad, no solo una escritura en una tabla
                # técnica. Es un count sobre una tabla chica.
                cur.execute("select count(*) from pedidos")
                cur.fetchone()
                return ultimo_latido, contador
