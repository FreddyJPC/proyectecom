"""Acceso a datos de la bandeja de salida `eventos_meta` (migración 031). Todo SQL va con parámetros."""
from typing import Any, Dict, List, Optional

from src.config.database import get_connection

_MAXIMO_TEXTO = 500


def _recortar(texto: Optional[str]) -> Optional[str]:
    if texto is None:
        return None
    return texto if len(texto) <= _MAXIMO_TEXTO else texto[: _MAXIMO_TEXTO - 1] + "…"


class EventosMetaRepository:
    @staticmethod
    def detectar(minutos_de_espera: int, dias_maximos: int) -> int:
        """Anota como evento cada venta de anuncio ya confirmada que todavía no tiene uno. Devuelve cuántos anotó.

        Solo ventas cuyo lead vino de un anuncio. La confirmación es la misma regla que `reglas.venta_confirmada`: pedido de Rocketfy
        o cobrada, y no cancelada. Se espera `minutos_de_espera` antes (da tiempo a una cancelación, que Meta no deja deshacer). Sin
        identificador de clic o demasiado antigua queda `descartado` con su motivo (así se puede medir cuántas ventas no se pueden avisar).
        Repetirlo no duplica nada: la clave única (tipo, venta) lo impide."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    with candidatas as (
                        select v.id as venta_id, l.id_anuncio, nullif(trim(l.ctwa_clid), '') as ctwa_clid, v.total as valor,
                               case when v.id_pedido_rocketfy is not null then v.cerrada_en else v.cobrada_en end as ocurrido_en
                        from ventas v
                        join leads l on l.id = v.lead_id
                        where l.origen = 'anuncio'
                          and v.estado <> 'cancelada'
                          and (v.id_pedido_rocketfy is not null or v.cobrada_en is not null)
                          and not exists (select 1 from eventos_meta e where e.tipo = 'Purchase' and e.venta_id = v.id)
                    )
                    insert into eventos_meta (tipo, venta_id, id_anuncio, ctwa_clid, valor, ocurrido_en, estado, motivo)
                    select 'Purchase', venta_id, id_anuncio, ctwa_clid, valor, ocurrido_en,
                           case when ctwa_clid is null or ocurrido_en < now() - make_interval(days => %s)
                                then 'descartado' else 'pendiente' end,
                           case when ctwa_clid is null then 'La venta no tiene el identificador del clic del anuncio'
                                when ocurrido_en < now() - make_interval(days => %s) then 'La venta es demasiado antigua para avisarla'
                                else null end
                    from candidatas
                    where ocurrido_en <= now() - make_interval(mins => %s)
                    on conflict (tipo, venta_id) do nothing
                    """,
                    (dias_maximos, dias_maximos, minutos_de_espera),
                )
                return cur.rowcount

    @staticmethod
    def recuperar_colgados(minutos: int = 10) -> int:
        """Un envío que quedó `enviando` (el proceso se cayó a medias) pasa a `dudoso`: no se sabe si Meta lo recibió y NO se reenvía."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    update eventos_meta
                    set estado = 'dudoso', actualizado_en = now(),
                        motivo = 'El envío se interrumpió y no se sabe si Meta lo recibió'
                    where estado = 'enviando' and actualizado_en < now() - make_interval(mins => %s)
                    """,
                    (minutos,),
                )
                return cur.rowcount

    @staticmethod
    def reclamar(limite: int) -> List[Dict[str, Any]]:
        """Reserva (`enviando`, +1 intento) los eventos que toca enviar y devuelve cada uno con el estado actual de su venta."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    with tomados as (
                        update eventos_meta
                        set estado = 'enviando', intentos = intentos + 1, actualizado_en = now()
                        where id in (
                            select id from eventos_meta
                            where estado = 'pendiente' and (proximo_intento_en is null or proximo_intento_en <= now())
                            order by id limit %s for update skip locked
                        )
                        returning id, venta_id, ctwa_clid, valor, moneda, ocurrido_en, intentos
                    )
                    select t.*, v.estado as venta_estado, v.id_pedido_rocketfy, v.cobrada_en
                    from tomados t join ventas v on v.id = t.venta_id
                    order by t.id
                    """,
                    (limite,),
                )
                columnas = [d[0] for d in cur.description]
                return [dict(zip(columnas, fila)) for fila in cur.fetchall()]

    @staticmethod
    def marcar_enviado(evento_id: int, respuesta: str) -> None:
        EventosMetaRepository._actualizar(evento_id, "enviado", None, respuesta, enviado=True)

    @staticmethod
    def marcar_descartado(evento_id: int, motivo: str) -> None:
        EventosMetaRepository._actualizar(evento_id, "descartado", motivo, None)

    @staticmethod
    def marcar_dudoso(evento_id: int, motivo: str) -> None:
        EventosMetaRepository._actualizar(evento_id, "dudoso", motivo, None)

    @staticmethod
    def marcar_fallido(evento_id: int, motivo: str) -> None:
        """Se agotaron los intentos."""
        EventosMetaRepository._actualizar(evento_id, "fallido", motivo, None)

    @staticmethod
    def reprogramar(evento_id: int, motivo: str, minutos: int) -> None:
        """Meta lo rechazó pero se puede reintentar: vuelve a `pendiente` para dentro de `minutos`."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    update eventos_meta
                    set estado = 'pendiente', motivo = %s, proximo_intento_en = now() + make_interval(mins => %s),
                        actualizado_en = now()
                    where id = %s
                    """,
                    (_recortar(motivo), minutos, evento_id),
                )

    @staticmethod
    def _actualizar(evento_id: int, estado: str, motivo: Optional[str], respuesta: Optional[str], enviado: bool = False) -> None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    update eventos_meta
                    set estado = %s, motivo = %s, respuesta = %s, actualizado_en = now(),
                        enviado_en = case when %s then now() else enviado_en end, proximo_intento_en = null
                    where id = %s
                    """,
                    (estado, _recortar(motivo), _recortar(respuesta), enviado, evento_id),
                )
