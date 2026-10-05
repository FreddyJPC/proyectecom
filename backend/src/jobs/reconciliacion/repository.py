from typing import List

from src.config.database import get_connection
from src.integrations.rocketfy.constants import ESTADOS_TERMINALES
from src.jobs._locks import acquire_lock, release_lock


class ReconciliacionRepository:
    @staticmethod
    def acquire_lock(job_name: str) -> bool:
        return acquire_lock(job_name)

    @staticmethod
    def release_lock(job_name: str) -> None:
        release_lock(job_name)

    @staticmethod
    def obtener_ids_en_curso() -> List[int]:
        """Pedidos con id_rocketfy asignado cuyo último status_id conocido
        no es terminal — el rango [min, max] de estos ids es lo que se
        consulta en bulk/getInfo."""
        estados = tuple(int(e) for e in ESTADOS_TERMINALES)
        placeholders = ",".join(["%s"] * len(estados))
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    select id_rocketfy from pedidos
                    where id_rocketfy is not null
                      and (status_id_rocketfy is null or status_id_rocketfy not in ({placeholders}))
                    order by id_rocketfy
                    """,
                    estados,
                )
                return [row[0] for row in cur.fetchall()]

    @staticmethod
    def actualizar_status(id_rocketfy: int, status_id: int) -> None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "update pedidos set status_id_rocketfy = %s, actualizado_en = now() where id_rocketfy = %s",
                    (status_id, id_rocketfy),
                )
