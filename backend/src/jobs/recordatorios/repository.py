"""Acceso a datos de los recordatorios: los chats que esperan al dueño y el registro de cada aviso. Todo SQL va con parámetros."""
from typing import Any, Dict, List

from src.config.database import get_connection

# Los estados en que una persona está a cargo (ver routes/gestion/tipos.py): Victoria ya no responde y el cliente espera.
_ESTADOS_EN_MANOS_DEL_DUENO = ("escalada", "en_gestion")


class RecordatoriosRepository:
    @staticmethod
    def pendientes() -> List[Dict[str, Any]]:
        """Chats en manos del dueño que NO ha abierto desde que quedaron así, con el último mensaje del cliente."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select c.id, c.canal, c.id_externo, c.estado, c.pendiente_desde, c.recordatorios_enviados,
                           c.ultimo_recordatorio_en, ct.telefono, ct.nombre,
                           (select contenido from mensajes
                             where conversacion_id = c.id and rol = 'cliente' order by creado_en desc, id desc limit 1) as ultimo_mensaje
                    from conversaciones c
                    join contactos ct on ct.id = c.contacto_id
                    where c.estado = any(%s) and c.vista_en is null and c.pendiente_desde is not null
                    order by c.pendiente_desde
                    """,
                    (list(_ESTADOS_EN_MANOS_DEL_DUENO),),
                )
                columnas = [d[0] for d in cur.description]
                return [dict(zip(columnas, fila)) for fila in cur.fetchall()]

    @staticmethod
    def registrar_envio(conversacion_id: int) -> None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "update conversaciones set recordatorios_enviados = recordatorios_enviados + 1, ultimo_recordatorio_en = now() "
                    "where id = %s",
                    (conversacion_id,),
                )
