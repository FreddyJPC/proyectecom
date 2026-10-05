from typing import List

from src.config.database import get_connection


class SkuMonitoreadoRepository:
    @staticmethod
    def upsert(sku: str, umbral_stock_minimo: int) -> None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into skus_monitoreados (sku, umbral_stock_minimo, activo)
                    values (%s, %s, true)
                    on conflict (sku) do update set
                        umbral_stock_minimo = excluded.umbral_stock_minimo,
                        activo = true
                    """,
                    (sku, umbral_stock_minimo),
                )

    @staticmethod
    def desactivar(sku: str) -> bool:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("update skus_monitoreados set activo = false where sku = %s", (sku,))
                return cur.rowcount == 1

    @staticmethod
    def listar(solo_activos: bool = False) -> List[dict]:
        filtro = "where m.activo = true" if solo_activos else ""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    select m.sku, m.umbral_stock_minimo, m.activo, s.stock, s.price, s.capturado_en
                    from skus_monitoreados m
                    left join lateral (
                        select stock, price, capturado_en from stock_snapshots
                        where sku = m.sku order by capturado_en desc limit 1
                    ) s on true
                    {filtro}
                    order by m.sku
                    """
                )
                cols = [d[0] for d in cur.description]
                return [dict(zip(cols, row)) for row in cur.fetchall()]
