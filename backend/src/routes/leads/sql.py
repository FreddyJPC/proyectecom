"""
SQL de leads a nivel de CURSOR: lo que otros módulos (ventas, el bot) necesitan ejecutar DENTRO de su propia transacción.

Por qué existe: la temperatura de un lead cambia en varios sitios (se despacha un pedido, el dueño cierra o cancela una venta,
Victoria clasifica, el enfriamiento automático, el dueño a mano). Todos pasan por `fijar_temperatura`, así el historial y los
campos que acompañan a la temperatura (cuándo se cerró, el motivo de pérdida) nunca quedan a medias. No importa nada de otros
módulos de rutas, para que ventas y whatsapp puedan usarlo sin dependencias circulares.
"""
from datetime import datetime
from typing import List, Optional

import psycopg2.errors

from .exceptions import LeadNoEncontradoError, OtroLeadAbiertoError
from .temperaturas import ABIERTAS, PERDIDO, es_final, limpiar_motivo


def fijar_temperatura(
    cur,
    lead_id: int,
    nueva: str,
    origen: str,
    motivo: Optional[str] = None,
    usuario: Optional[str] = None,
    motivo_perdida: Optional[str] = None,
    fijada_hasta: Optional[datetime] = None,
) -> bool:
    """Pone la temperatura de un lead y deja constancia en `lead_historial`. Devuelve True si cambió algo.

    - Bloquea la fila del lead mientras decide (dos cambios a la vez no se pisan).
    - Una temperatura final (perdido/ganado) marca `cerrado_en`; salir de ella lo borra. `motivo_perdida` solo vale en «perdido».
    - `fijada_hasta`: el dueño fija la temperatura y el enfriamiento automático la respeta hasta esa fecha.
    - Reabrir un lead cuando el contacto ya tiene otro abierto lanza `OtroLeadAbiertoError` (índice único parcial).
    """
    cur.execute("select temperatura from leads where id = %s for update", (lead_id,))
    fila = cur.fetchone()
    if fila is None:
        raise LeadNoEncontradoError(f"No existe el lead {lead_id}.")
    actual = fila[0]
    motivo = limpiar_motivo(motivo)
    if actual == nueva and fijada_hasta is None:
        return False
    try:
        cur.execute(
            """
            update leads set
                temperatura = %s, temperatura_origen = %s, temperatura_motivo = %s, temperatura_en = now(),
                temperatura_fijada_hasta = %s,
                motivo_perdida = %s,
                cerrado_en = case when %s then coalesce(cerrado_en, now()) else null end,
                actualizado_en = now()
            where id = %s
            """,
            (nueva, origen, motivo, fijada_hasta, motivo_perdida if nueva == PERDIDO else None, es_final(nueva), lead_id),
        )
    except psycopg2.errors.UniqueViolation as exc:
        raise OtroLeadAbiertoError("Este cliente ya tiene otro lead abierto: solo puede haber uno a la vez.") from exc
    if actual != nueva:
        cur.execute(
            "insert into lead_historial (lead_id, de, a, origen, motivo, usuario) values (%s, %s, %s, %s, %s, %s)",
            (lead_id, actual, nueva, origen, motivo, usuario),
        )
    return True


def cerrar_leads_abiertos_del_contacto(
    cur, contacto_id: int, origen: str, motivo: str, usuario: Optional[str], motivo_perdida: str = "no_le_interesa"
) -> List[int]:
    """Pasa a «perdido» todos los leads abiertos de un contacto (hoy hay a lo sumo uno). Devuelve los ids cerrados."""
    cur.execute(
        "select id from leads where contacto_id = %s and temperatura = any(%s) order by id",
        (contacto_id, list(ABIERTAS)),
    )
    cerrados = []
    for (lead_id,) in cur.fetchall():
        if fijar_temperatura(cur, lead_id, PERDIDO, origen, motivo, usuario, motivo_perdida=motivo_perdida):
            cerrados.append(lead_id)
    return cerrados


def marcar_no_contactar(cur, contacto_id: int, valor: bool, motivo: Optional[str], por: str, usuario: Optional[str]) -> bool:
    """Marca o desmarca «no contactar» en el CONTACTO (vale para todos sus canales). Marcarlo cierra sus leads abiertos
    como «perdido». Devuelve False si el contacto no existe."""
    motivo = limpiar_motivo(motivo)
    cur.execute(
        """
        update contactos set
            no_contactar = %s,
            no_contactar_motivo = case when %s then %s else null end,
            no_contactar_en = case when %s then now() else null end,
            no_contactar_por = case when %s then %s else null end,
            actualizado_en = now()
        where id = %s
        """,
        (valor, valor, motivo, valor, valor, por, contacto_id),
    )
    if cur.rowcount == 0:
        return False
    if valor:
        cerrar_leads_abiertos_del_contacto(
            cur, contacto_id, por, motivo or "Pidió que no lo contacten", usuario, motivo_perdida="no_le_interesa"
        )
    return True
