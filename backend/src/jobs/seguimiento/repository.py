"""
Acceso a datos del seguimiento automático: a quién se le puede escribir, el registro de lo enviado y el tope diario.

El envío se hace en dos tiempos (ver migración 026): `reservar` inserta la fila (el índice único parcial impide que el mismo
cliente reciba dos veces el mismo tipo de mensaje, aunque corran dos procesos a la vez), se envía, y después `marcar_enviado` o
`marcar_fallido` dejan el resultado. Todo texto SQL va con parámetros; nada se arma con lo que llega de fuera.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.config.database import get_connection

from .reglas import DIAS_MAXIMOS_DESDE_EL_ULTIMO_MENSAJE, HORAS_VENTANA_DE_SERVICIO, MARGEN_ANTES_DEL_CIERRE_HORAS, TIPO_EMPUJON

# Cuántas veces se reintenta a un mismo cliente tras un envío fallido, y cuánto se espera entre intentos.
MAXIMO_DE_FALLOS_POR_CLIENTE = 3
HORAS_ENTRE_REINTENTOS = 6


def _filas(cur) -> List[Dict[str, Any]]:
    columnas = [d[0] for d in cur.description]
    return [dict(zip(columnas, fila)) for fila in cur.fetchall()]


# Quién puede recibir un seguimiento (lo común a las dos formas de escribir): un lead abierto y con interés, de una persona que
# no pidió que la dejen en paz, en una conversación que atiende Victoria (no el dueño), por un canal con envío de plantillas,
# donde la última palabra fue NUESTRA (la pelota está en la cancha del cliente) y a quien aún no se le escribió este tipo de
# mensaje. «Con interés» = ya sabemos qué producto quiere: alguien que solo dijo «hola» no recibe nada.
_CANDIDATOS = """
    select l.id as lead_id, l.contacto_id, l.conversacion_id, l.temperatura, c.canal, c.id_externo,
           ct.nombre, ct.telefono, mc.ultimo as ultimo_cliente_en
    from leads l
    join conversaciones c on c.id = l.conversacion_id
    join contactos ct on ct.id = l.contacto_id
    join lateral (
        select rol from mensajes where conversacion_id = l.conversacion_id order by creado_en desc, id desc limit 1
    ) ult on true
    join lateral (
        select max(creado_en) as ultimo from mensajes where conversacion_id = l.conversacion_id and rol = 'cliente'
    ) mc on mc.ultimo is not null
    where l.temperatura in ('caliente', 'tibio')
      and l.estado not in ('despachado', 'por_gestionar', 'cancelado')
      and (l.producto_sku is not null or l.producto_nombre is not null)
      and not ct.no_contactar
      and c.canal = any(%(canales)s)
      and c.estado in ('activa', 'esperando_pago')
      and ult.rol = 'bot'
      and {momento}
      and {extra}
      and not exists (
          select 1 from seguimientos s
          where s.contacto_id = l.contacto_id and s.tipo = %(tipo)s and s.estado in ('reservado', 'enviado')
      )
      and (
          select count(*) from seguimientos s
          where s.contacto_id = l.contacto_id and s.tipo = %(tipo)s and s.estado = 'fallido'
      ) < %(maximo_fallos)s
      and not exists (
          select 1 from seguimientos s
          where s.contacto_id = l.contacto_id and s.tipo = %(tipo)s and s.estado = 'fallido'
            and s.creado_en > %(ahora)s - make_interval(hours => %(horas_reintento)s)
      )
    order by (l.temperatura = 'caliente') desc, mc.ultimo desc
    limit %(limite)s
"""


class SeguimientoRepository:
    @staticmethod
    def candidatos(tipo: str, canales: List[str], ahora: datetime, horas_de_espera: int, limite: int) -> List[Dict[str, Any]]:
        """Clientes a quienes les toca este tipo de mensaje por TIEMPO (la última palabra del cliente fue hace el tiempo justo).
        El empujón mira la ventana de 24 h abierta; la plantilla, solo conversaciones que llegaron por anuncio y cuya ventana
        de 24 h ya se cerró (la ventana gratuita exacta se comprueba después, con las fechas de cada conversación)."""
        if tipo == TIPO_EMPUJON:
            momento = "mc.ultimo <= %(ahora)s - make_interval(hours => %(horas_de_espera)s) and mc.ultimo >= %(ahora)s - make_interval(hours => %(horas_maximas)s)"
            extra = "true"
        else:
            momento = "mc.ultimo < %(ahora)s - make_interval(hours => %(horas_ventana)s) and mc.ultimo >= %(ahora)s - make_interval(days => %(dias_maximos)s)"
            extra = "exists (select 1 from conversacion_anuncios a where a.conversacion_id = l.conversacion_id)"
        parametros = {
            "tipo": tipo, "canales": list(canales), "ahora": ahora, "horas_de_espera": horas_de_espera,
            "horas_maximas": HORAS_VENTANA_DE_SERVICIO - MARGEN_ANTES_DEL_CIERRE_HORAS, "horas_ventana": HORAS_VENTANA_DE_SERVICIO,
            "dias_maximos": DIAS_MAXIMOS_DESDE_EL_ULTIMO_MENSAJE, "maximo_fallos": MAXIMO_DE_FALLOS_POR_CLIENTE,
            "horas_reintento": HORAS_ENTRE_REINTENTOS, "limite": limite,
        }
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(_CANDIDATOS.format(momento=momento, extra=extra), parametros)
                return _filas(cur)

    @staticmethod
    def mensajes_de(conversacion_id: int) -> List[Dict[str, Any]]:
        """Rol y fecha de cada mensaje (lo que necesita el cálculo de la ventana gratuita)."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "select rol, creado_en from mensajes where conversacion_id = %s order by creado_en, id", (conversacion_id,)
                )
                return _filas(cur)

    @staticmethod
    def contar_del_dia(desde: datetime) -> int:
        """Seguimientos del día (reservados o enviados): los que ya gastaron cupo. Un `reservado` que quedó a medias cuenta:
        ante la duda se cuenta de más, no de menos."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "select count(*) from seguimientos where creado_en >= %s and estado in ('reservado', 'enviado')", (desde,)
                )
                return int(cur.fetchone()[0])

    @staticmethod
    def contar_fallos(tipo: str, desde: datetime) -> int:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("select count(*) from seguimientos where tipo = %s and estado = 'fallido' and creado_en >= %s", (tipo, desde))
                return int(cur.fetchone()[0])

    @staticmethod
    def reservar(
        lead_id: int, canal: str, tipo: str, contenido: str, plantilla: Optional[str] = None
    ) -> Optional[int]:
        """Reserva el envío. Devuelve el id de la reserva, o None si NO se debe enviar: el cliente ya recibió este tipo de
        mensaje (índice único), pidió que no lo contacten, su lead ya no está abierto, la conversación pasó a manos del dueño
        o el cliente acaba de escribir (la última palabra ya no es nuestra). La comprobación va en la misma sentencia que el
        insert: no hay hueco entre «puedo escribirle» y «le escribo», ni siquiera de unos segundos."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into seguimientos (lead_id, contacto_id, conversacion_id, canal, tipo, contenido, plantilla)
                    select l.id, l.contacto_id, l.conversacion_id, %s, %s, %s, %s
                    from leads l
                    join contactos ct on ct.id = l.contacto_id
                    join conversaciones c on c.id = l.conversacion_id
                    where l.id = %s and not ct.no_contactar and l.temperatura in ('caliente', 'tibio')
                      and c.estado in ('activa', 'esperando_pago')
                      and (
                          select rol from mensajes where conversacion_id = l.conversacion_id order by creado_en desc, id desc limit 1
                      ) = 'bot'
                    on conflict (contacto_id, tipo) where estado in ('reservado', 'enviado') do nothing
                    returning id
                    """,
                    (canal, tipo, contenido, plantilla, lead_id),
                )
                fila = cur.fetchone()
                return fila[0] if fila else None

    @staticmethod
    def marcar_enviado(seguimiento_id: int, conversacion_id: int, contenido: str, wamid: Optional[str]) -> None:
        """Deja el envío como hecho y lo anota en la conversación (rol `bot`) para que Victoria sepa, si el cliente contesta,
        que ya se le escribió y qué se le dijo. Todo en una transacción."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "update seguimientos set estado = 'enviado', wamid = %s, enviado_en = now() where id = %s",
                    (wamid, seguimiento_id),
                )
                cur.execute(
                    "insert into mensajes (conversacion_id, rol, contenido, tipo, wamid) values (%s, 'bot', %s, 'texto', %s)",
                    (conversacion_id, contenido, wamid),
                )
                cur.execute("update conversaciones set actualizada_en = now() where id = %s", (conversacion_id,))

    @staticmethod
    def marcar_fallido(seguimiento_id: int, error: str) -> None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "update seguimientos set estado = 'fallido', error = %s where id = %s", (error[:500], seguimiento_id)
                )


__all__ = ["SeguimientoRepository", "MAXIMO_DE_FALLOS_POR_CLIENTE", "HORAS_ENTRE_REINTENTOS"]
