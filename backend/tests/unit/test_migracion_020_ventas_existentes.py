"""
Migración 020: las ventas que ya estaban despachadas por Rocketfy pasan a la tabla `ventas` (con su costo
congelado), sin duplicarse si el bloque se vuelve a correr.
"""
from decimal import Decimal
from pathlib import Path

import pytest

from src.config.database import get_connection

MIGRACION = Path(__file__).resolve().parents[2] / "migrations" / "020_productos_propios_ventas_gestion.sql"
TELEFONO = "593900007777"
SKU = "TEST-MIG020"


def _bloque_de_traslado() -> str:
    sql = MIGRACION.read_text(encoding="utf-8")
    inicio = sql.index("insert into ventas (")
    fin = sql.index("-- Sin policies")
    return sql[inicio:fin]


def _limpiar():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("delete from ventas where telefono = %s", (TELEFONO,))
            cur.execute("delete from conversaciones where telefono = %s", (TELEFONO,))
            cur.execute("delete from productos_bot where sku = %s", (SKU,))


@pytest.fixture(autouse=True)
def limpio():
    _limpiar()
    yield
    _limpiar()


def test_el_traslado_copia_los_despachados_y_es_idempotente():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "insert into productos_bot (sku, nombre, descripcion, precio, tiempo_entrega, costo_rocketfy) "
                "values (%s, 'Audífonos', 'd', 24.99, '2 días', 12.00)",
                (SKU,),
            )
            cur.execute("insert into conversaciones (telefono, origen) values (%s, 'fep') returning id", (TELEFONO,))
            conversacion_id = cur.fetchone()[0]
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into leads (conversacion_id, telefono, nombre_cliente, producto_sku, producto_nombre, cantidad,
                                   total, metodo_pago, estado, id_pedido_local, id_pedido_rocketfy)
                values (%s, %s, 'Ana', %s, 'Audífonos', 2, 49.98, 'contraentrega', 'despachado', 11, 99)
                returning id
                """,
                (conversacion_id, TELEFONO, SKU),
            )
            lead_id = cur.fetchone()[0]
            cur.execute(_bloque_de_traslado())
            cur.execute(_bloque_de_traslado())  # segunda vez: no debe duplicar

            cur.execute(
                "select proveedor_id, canal, estado, total, costo_productos, id_pedido_rocketfy, cliente_nombre from ventas where lead_id = %s",
                (lead_id,),
            )
            assert cur.fetchall() == [(1, "fep", "despachada", Decimal("49.98"), Decimal("24.00"), 99, "Ana")]
            cur.execute(
                "select vl.producto_sku, vl.cantidad, vl.precio_unitario, vl.costo_unitario from ventas_lineas vl join ventas v on v.id = vl.venta_id where v.lead_id = %s",
                (lead_id,),
            )
            assert cur.fetchall() == [(SKU, 2, Decimal("24.99"), Decimal("12.00"))]
