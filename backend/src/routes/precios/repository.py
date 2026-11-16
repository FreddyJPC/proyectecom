"""Acceso a datos de precios y ofertas (ADR-017, migración 033). Todo SQL va con parámetros y con listas blancas de columnas."""
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from src.config.database import get_connection

_COLUMNAS_OFERTA = (
    "id, nombre, descripcion, texto_anuncio, precio, envio_incluido, desde, hasta, cupo, maximo_por_cliente, visibilidad, "
    "regateo_tipo, regateo_valor, transferencia_tipo, transferencia_valor, bajo_margen_autorizado, estado, "
    "creada_en, creada_por, actualizada_en"
)
# Lo que se puede escribir de una oferta (el resto lo pone el sistema).
CAMPOS_OFERTA = (
    "nombre", "descripcion", "texto_anuncio", "precio", "envio_incluido", "desde", "hasta", "cupo", "maximo_por_cliente",
    "visibilidad", "regateo_tipo", "regateo_valor", "transferencia_tipo", "transferencia_valor", "bajo_margen_autorizado", "estado",
)
# Reglas de precio de un producto que se editan desde su ficha.
CAMPOS_REGLAS_PRODUCTO = (
    "transferencia_tipo", "transferencia_valor", "regateo_tipo", "regateo_valor",
    "envio_gratis_desde_unidades", "envio_gratis_desde_monto",
)


def _filas(cur) -> List[Dict[str, Any]]:
    columnas = [d[0] for d in cur.description]
    return [dict(zip(columnas, fila)) for fila in cur.fetchall()]


def _fila(cur) -> Optional[Dict[str, Any]]:
    filas = _filas(cur)
    return filas[0] if filas else None


class PreciosRepository:
    # ------------------------------------------------------------------ escalas
    @staticmethod
    def escalas_de(skus: Iterable[str]) -> Dict[str, List[Dict[str, Any]]]:
        skus = sorted({s for s in skus if s})
        if not skus:
            return {}
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "select producto_sku, cantidad, precio_total from producto_escalas where producto_sku = any(%s) order by cantidad",
                    (skus,),
                )
                salida: Dict[str, List[Dict[str, Any]]] = {}
                for sku, cantidad, precio_total in cur.fetchall():
                    salida.setdefault(sku, []).append({"cantidad": cantidad, "precio_total": precio_total})
                return salida

    @staticmethod
    def reglas_de_producto(sku: str) -> Optional[Dict[str, Any]]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"select sku, nombre, precio, costo_rocketfy, costo_propio, envio_incluido, proveedor_id, "
                    f"{', '.join(CAMPOS_REGLAS_PRODUCTO)} from productos_bot where sku = %s",
                    (sku,),
                )
                return _fila(cur)

    @staticmethod
    def guardar_reglas_de_producto(sku: str, reglas: Dict[str, Any], escalas: List[Dict[str, Any]]) -> bool:
        """Guarda las reglas y REEMPLAZA las escalas del producto, todo junto. False si el producto no existe."""
        columnas = [c for c in CAMPOS_REGLAS_PRODUCTO if c in reglas]
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("select 1 from productos_bot where sku = %s for update", (sku,))
                if cur.fetchone() is None:
                    return False
                if columnas:
                    cur.execute(
                        f"update productos_bot set {', '.join(f'{c} = %s' for c in columnas)}, actualizado_en = now() where sku = %s",
                        (*[reglas[c] for c in columnas], sku),
                    )
                cur.execute("delete from producto_escalas where producto_sku = %s", (sku,))
                for escala in escalas:
                    cur.execute(
                        "insert into producto_escalas (producto_sku, cantidad, precio_total) values (%s, %s, %s)",
                        (sku, escala["cantidad"], escala["precio_total"]),
                    )
                return True

    # ------------------------------------------------------------------ negocio
    @staticmethod
    def transferencia_negocio() -> Dict[str, Any]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("select transferencia_tipo, transferencia_valor from ajustes_negocio where id = 1")
                fila = cur.fetchone()
        return {"tipo": fila[0], "valor": fila[1]} if fila else {"tipo": None, "valor": None}

    @staticmethod
    def guardar_transferencia_negocio(tipo: Optional[str], valor) -> None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "update ajustes_negocio set transferencia_tipo = %s, transferencia_valor = %s, actualizado_en = now() where id = 1",
                    (tipo, valor),
                )

    # ------------------------------------------------------------------ ofertas
    @staticmethod
    def _items(cur, ids: List[int]) -> Dict[int, List[Dict[str, Any]]]:
        if not ids:
            return {}
        cur.execute(
            "select i.oferta_id, i.producto_sku, i.cantidad, i.variante, p.nombre as producto_nombre, p.precio, p.activo, p.estado "
            "from oferta_items i join productos_bot p on p.sku = i.producto_sku where i.oferta_id = any(%s) order by i.orden, i.id",
            (ids,),
        )
        salida: Dict[int, List[Dict[str, Any]]] = {}
        for fila in _filas(cur):
            salida.setdefault(fila.pop("oferta_id"), []).append(fila)
        return salida

    @staticmethod
    def ofertas(ids: Optional[Iterable[int]] = None, incluir_archivadas: bool = False) -> List[Dict[str, Any]]:
        """Ofertas con sus productos. `ids` = solo esas; si no, todas (sin las archivadas, salvo que se pidan)."""
        filtros, params = [], []
        if ids is not None:
            lista = sorted({int(i) for i in ids})
            if not lista:
                return []
            filtros.append("id = any(%s)")
            params.append(lista)
        if not incluir_archivadas:
            filtros.append("estado <> 'archivada'")
        where = f"where {' and '.join(filtros)}" if filtros else ""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"select {_COLUMNAS_OFERTA} from ofertas {where} order by id desc", params)
                ofertas = _filas(cur)
                items = PreciosRepository._items(cur, [o["id"] for o in ofertas])
                cur.execute(
                    "select oferta_id, count(*) from anuncios_productos where oferta_id = any(%s) group by oferta_id",
                    ([o["id"] for o in ofertas],),
                )
                anuncios = dict(cur.fetchall())
        for oferta in ofertas:
            oferta["items"] = items.get(oferta["id"], [])
            oferta["anuncios"] = int(anuncios.get(oferta["id"], 0))
        return ofertas

    @staticmethod
    def oferta(oferta_id: int) -> Optional[Dict[str, Any]]:
        encontradas = PreciosRepository.ofertas([oferta_id], incluir_archivadas=True)
        return encontradas[0] if encontradas else None

    @staticmethod
    def ofertas_publicas() -> List[Dict[str, Any]]:
        """Las que Victoria puede ofrecer a cualquier cliente (regla P6: por defecto una oferta es solo de su anuncio)."""
        return [o for o in PreciosRepository.ofertas() if o["visibilidad"] == "publica" and o["estado"] == "activa"]

    @staticmethod
    def crear_oferta(datos: Dict[str, Any], items: List[Dict[str, Any]], usuario: Optional[str]) -> int:
        columnas = [c for c in CAMPOS_OFERTA if c in datos]
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"insert into ofertas ({', '.join(columnas)}, creada_por) values ({', '.join(['%s'] * len(columnas))}, %s) returning id",
                    (*[datos[c] for c in columnas], usuario),
                )
                oferta_id = cur.fetchone()[0]
                PreciosRepository._guardar_items(cur, oferta_id, items)
                return oferta_id

    @staticmethod
    def actualizar_oferta(oferta_id: int, datos: Dict[str, Any], items: Optional[List[Dict[str, Any]]]) -> bool:
        columnas = [c for c in CAMPOS_OFERTA if c in datos]
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("select 1 from ofertas where id = %s for update", (oferta_id,))
                if cur.fetchone() is None:
                    return False
                if columnas:
                    cur.execute(
                        f"update ofertas set {', '.join(f'{c} = %s' for c in columnas)}, actualizada_en = now() where id = %s",
                        (*[datos[c] for c in columnas], oferta_id),
                    )
                if items is not None:
                    cur.execute("delete from oferta_items where oferta_id = %s", (oferta_id,))
                    PreciosRepository._guardar_items(cur, oferta_id, items)
                return True

    @staticmethod
    def _guardar_items(cur, oferta_id: int, items: List[Dict[str, Any]]) -> None:
        for orden, item in enumerate(items):
            cur.execute(
                "insert into oferta_items (oferta_id, producto_sku, cantidad, variante, orden) values (%s, %s, %s, %s, %s)",
                (oferta_id, item["producto_sku"], item.get("cantidad") or 1, item.get("variante") or None, orden),
            )

    @staticmethod
    def ventas_de_oferta(oferta_id: int, contacto_id: Optional[int] = None) -> int:
        """Ventas no canceladas que llevaron esta oferta (todas o de un contacto). Sirve para el cupo y el máximo por cliente."""
        filtro_contacto = "and v.contacto_id = %s" if contacto_id is not None else ""
        params: List[Any] = [oferta_id] + ([contacto_id] if contacto_id is not None else [])
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"select count(distinct v.id) from ventas v join ventas_lineas l on l.venta_id = v.id "
                    f"where l.oferta_id = %s and v.estado <> 'cancelada' {filtro_contacto}",
                    params,
                )
                return int(cur.fetchone()[0])

    @staticmethod
    def resumen_ventas_ofertas() -> Dict[int, Dict[str, Any]]:
        """Por oferta: ventas no canceladas e ingreso (para la lista del panel)."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "select l.oferta_id, count(distinct v.id), coalesce(sum(distinct v.total), 0) from ventas v "
                    "join ventas_lineas l on l.venta_id = v.id where l.oferta_id is not null and v.estado <> 'cancelada' "
                    "group by l.oferta_id"
                )
                return {fila[0]: {"ventas": int(fila[1]), "ingreso": fila[2]} for fila in cur.fetchall()}

    # ------------------------------------------------------------------ anuncios
    @staticmethod
    def vinculo_de_anuncio(id_anuncio: str) -> Optional[Dict[str, Any]]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("select id_anuncio, producto_sku, oferta_id, nombre from anuncios_productos where id_anuncio = %s", (id_anuncio,))
                return _fila(cur)

    @staticmethod
    def vincular_anuncio_a_oferta(id_anuncio: str, oferta_id: int, nombre: Optional[str]) -> None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into anuncios_productos (id_anuncio, producto_sku, oferta_id, nombre) values (%s, null, %s, %s)
                    on conflict (id_anuncio) do update set producto_sku = null, oferta_id = excluded.oferta_id,
                        nombre = coalesce(excluded.nombre, anuncios_productos.nombre), actualizado_en = now()
                    """,
                    (id_anuncio, oferta_id, nombre),
                )

    @staticmethod
    def anuncios_de_ofertas(ids: Iterable[int]) -> Dict[int, List[str]]:
        lista = sorted({int(i) for i in ids})
        if not lista:
            return {}
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("select oferta_id, id_anuncio from anuncios_productos where oferta_id = any(%s) order by id_anuncio", (lista,))
                salida: Dict[int, List[str]] = {}
                for oferta_id, id_anuncio in cur.fetchall():
                    salida.setdefault(oferta_id, []).append(id_anuncio)
                return salida


def vigente(oferta: Dict[str, Any], ahora: datetime) -> bool:
    """¿La oferta se puede vender ahora? Activa y dentro de sus fechas. (El cupo se revisa aparte: necesita contar ventas.)"""
    if oferta.get("estado") != "activa":
        return False
    if oferta.get("desde") is not None and ahora < oferta["desde"]:
        return False
    if oferta.get("hasta") is not None and ahora >= oferta["hasta"]:
        return False
    return True
