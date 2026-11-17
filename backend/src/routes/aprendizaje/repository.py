"""Tabla `victoria_aprendizaje` (migración 035): guardar un caso, listarlos, resumirlos y anotar la revisión del dueño."""
from typing import Any, Dict, List, Optional, Tuple

from psycopg2.extras import Json

from src.config.database import get_connection

_COLUMNAS = (
    "a.id, a.creado_en, a.conversacion_id, a.lead_id, a.contacto_id, a.tipo, a.origen, a.motivo, a.mensaje_cliente, a.etapa, "
    "a.producto_sku, a.contexto, a.estado, a.categoria, a.accion, a.nota, a.revisado_por, a.revisado_en"
)
_CLIENTE = (
    "coalesce(nullif(l.nombre_cliente, ''), nullif(ct.nombre, ''), nullif(c.nombre_perfil, ''), ct.telefono) as cliente, c.canal"
)
_DESDE = (
    "from victoria_aprendizaje a "
    "left join conversaciones c on c.id = a.conversacion_id "
    "left join contactos ct on ct.id = a.contacto_id "
    "left join leads l on l.id = a.lead_id"
)


def _filas(cur) -> List[Dict[str, Any]]:
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, fila)) for fila in cur.fetchall()]


class AprendizajeRepository:
    @staticmethod
    def insertar(datos: Dict[str, Any]) -> int:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into victoria_aprendizaje
                        (conversacion_id, lead_id, contacto_id, tipo, origen, motivo, mensaje_cliente, etapa, producto_sku, contexto)
                    values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    returning id
                    """,
                    (
                        datos.get("conversacion_id"), datos.get("lead_id"), datos.get("contacto_id"), datos["tipo"], datos["origen"],
                        datos["motivo"], datos.get("mensaje_cliente"), datos.get("etapa"), datos.get("producto_sku"),
                        Json(datos.get("contexto") or {}),
                    ),
                )
                return cur.fetchone()[0]

    @staticmethod
    def _filtros(estado: Optional[str], tipo: Optional[str], dias: Optional[int]) -> Tuple[str, list]:
        condiciones, valores = [], []
        if estado:
            condiciones.append("a.estado = %s")
            valores.append(estado)
        if tipo:
            condiciones.append("a.tipo = %s")
            valores.append(tipo)
        if dias:
            condiciones.append("a.creado_en >= now() - make_interval(days => %s)")
            valores.append(dias)
        return (" where " + " and ".join(condiciones)) if condiciones else "", valores

    @staticmethod
    def listar(estado: Optional[str], tipo: Optional[str], dias: Optional[int], limite: int, desplazamiento: int) -> Tuple[List[dict], int]:
        donde, valores = AprendizajeRepository._filtros(estado, tipo, dias)
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"select count(*) from victoria_aprendizaje a{donde}", valores)
                total = cur.fetchone()[0]
                cur.execute(
                    f"select {_COLUMNAS}, {_CLIENTE} {_DESDE}{donde} order by a.creado_en desc, a.id desc limit %s offset %s",
                    (*valores, limite, desplazamiento),
                )
                return _filas(cur), total

    @staticmethod
    def obtener(caso_id: int) -> Optional[dict]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"select {_COLUMNAS}, {_CLIENTE} {_DESDE} where a.id = %s", (caso_id,))
                filas = _filas(cur)
                return filas[0] if filas else None

    @staticmethod
    def resumen(dias: Optional[int]) -> Dict[str, Any]:
        donde, valores = AprendizajeRepository._filtros(None, None, dias)
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("select count(*) from victoria_aprendizaje where estado = 'pendiente'")
                pendientes = cur.fetchone()[0]
                cur.execute(f"select a.tipo, count(*) from victoria_aprendizaje a{donde} group by a.tipo order by count(*) desc", valores)
                por_tipo = [{"tipo": t, "cantidad": n} for t, n in cur.fetchall()]
                cur.execute(f"select a.etapa, count(*) from victoria_aprendizaje a{donde} group by a.etapa order by count(*) desc", valores)
                por_etapa = [{"etapa": e, "cantidad": n} for e, n in cur.fetchall()]
        return {"pendientes": pendientes, "total": sum(f["cantidad"] for f in por_tipo), "por_tipo": por_tipo, "por_etapa": por_etapa}

    @staticmethod
    def revisar(caso_id: int, estado: str, categoria: Optional[str], accion: Optional[str], nota: Optional[str], usuario: Optional[str]) -> bool:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    update victoria_aprendizaje set
                        estado = %s, categoria = %s, accion = %s, nota = %s,
                        revisado_por = case when %s = 'pendiente' then null else %s end,
                        revisado_en  = case when %s = 'pendiente' then null else now() end
                    where id = %s
                    """,
                    (estado, categoria, accion, nota, estado, usuario, estado, caso_id),
                )
                return cur.rowcount == 1
