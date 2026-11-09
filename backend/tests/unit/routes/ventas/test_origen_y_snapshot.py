"""Origen del producto, flete por producto y la foto de la venta (ADR-012). Sin base de datos."""
from decimal import Decimal

from src.routes.ventas.origen import (
    controla_su_stock,
    costo_unitario,
    es_de_cierre_manual,
    es_propio,
    flete_estimado,
)
from src.routes.ventas.snapshot import armar_venta, ganancia_de

ROCKETFY = {
    "sku": "R-1", "nombre": "Audífonos", "precio": Decimal("24.99"), "costo_rocketfy": Decimal("12.00"),
    "proveedor_id": 1, "proveedor_clave": "rocketfy", "proveedor_cierre": "rocketfy", "envio_incluido": True,
    "costo_flete_estimado": None, "categoria_id": 7, "categoria_nombre": "Electrónica",
}
PROPIO = {
    "sku": "PROP-0001", "nombre": "Zapatos", "precio": Decimal("30.00"), "costo_propio": Decimal("18.00"),
    "proveedor_id": 2, "proveedor_clave": "propio", "proveedor_cierre": "manual", "envio_incluido": False,
    "controla_stock": True, "stock_ultimo": 5, "costo_flete_estimado": None, "categoria_id": 3, "categoria_nombre": "Calzado",
}


class TestOrigen:
    def test_cierre_manual_solo_los_propios(self):
        assert es_de_cierre_manual(PROPIO) and es_propio(PROPIO)
        assert not es_de_cierre_manual(ROCKETFY) and not es_propio(ROCKETFY)

    def test_una_fila_sin_datos_de_proveedor_se_trata_como_rocketfy(self):
        assert not es_de_cierre_manual({"sku": "X"}) and not es_de_cierre_manual(None)

    def test_costo_unitario_segun_el_origen(self):
        assert costo_unitario(ROCKETFY) == Decimal("12.00")
        assert costo_unitario(PROPIO) == Decimal("18.00")
        assert costo_unitario({**PROPIO, "costo_propio": None}) is None

    def test_el_costo_de_un_propio_no_toma_el_de_rocketfy(self):
        assert costo_unitario({**PROPIO, "costo_rocketfy": Decimal("99.00"), "costo_propio": None}) is None

    def test_controla_su_stock_solo_si_es_propio_y_lo_activo(self):
        assert controla_su_stock(PROPIO)
        assert not controla_su_stock({**PROPIO, "controla_stock": False})
        assert not controla_su_stock(ROCKETFY)


class TestFlete:
    GENERAL = Decimal("5.00")

    def test_el_flete_del_producto_manda(self):
        assert flete_estimado({**ROCKETFY, "costo_flete_estimado": Decimal("9.50")}, self.GENERAL) == Decimal("9.50")

    def test_sin_flete_propio_y_envio_incluido_se_usa_el_general(self):
        assert flete_estimado(ROCKETFY, self.GENERAL) == Decimal("5.00")

    def test_envio_cobrado_aparte_no_resta_del_precio(self):
        assert flete_estimado(PROPIO, self.GENERAL) == Decimal("0.00")

    def test_un_flete_anotado_no_cuenta_si_el_envio_se_cobra_aparte(self):
        assert flete_estimado({**PROPIO, "costo_flete_estimado": Decimal("9.50")}, self.GENERAL) == Decimal("0.00")

    def test_un_flete_en_cero_anotado_por_el_dueno_cuenta(self):
        assert flete_estimado({**ROCKETFY, "costo_flete_estimado": Decimal("0.00")}, self.GENERAL) == Decimal("0.00")


def _lead(**cambios):
    lead = {
        "id": 10, "conversacion_id": 20, "nombre_cliente": "Ana", "telefono": "593999999999",
        "direccion": "Calle 1", "canton": "Cuenca", "provincia": "Azuay", "producto_sku": "PROP-0001",
        "producto_nombre": "Zapatos", "producto_variante": "talla 40", "cantidad": 2, "subtotal": Decimal("60.00"),
        "total": Decimal("62.00"), "costo_envio": Decimal("2.00"), "metodo_pago": "contraentrega",
        "entrega_opcion_id": 5, "entrega_nombre": "Envío en Cuenca", "entrega_tipo": "envio",
    }
    lead.update(cambios)
    return lead


class TestArmarVenta:
    def test_venta_propia_con_envio_cobrado_aparte(self):
        entrega = {"costo_negocio": Decimal("1.50")}
        venta, lineas = armar_venta(
            _lead(), PROPIO, {"origen": "anuncio", "canal": "instagram", "id_anuncio": "ad-1", "contacto_id": 5},
            entrega, "por_gestionar", Decimal("5.00"),
        )

        assert venta["estado"] == "por_gestionar" and venta["proveedor_id"] == 2
        assert (venta["subtotal"], venta["costo_envio_cliente"], venta["total"]) == (Decimal("60.00"), Decimal("2.00"), Decimal("62.00"))
        assert venta["costo_productos"] == Decimal("36.00")  # 18.00 x 2
        assert venta["costo_envio_negocio"] == Decimal("1.50")
        # ORIGEN = cómo llegó (anuncio); CANAL = por dónde conversa (aquí, un cliente de Instagram).
        assert (venta["origen"], venta["canal"], venta["id_anuncio"], venta["contacto_id"]) == ("anuncio", "instagram", "ad-1", 5)
        assert venta["entrega_nombre"] == "Envío en Cuenca"
        assert lineas == [
            {
                "producto_sku": "PROP-0001", "producto_nombre": "Zapatos", "variante": "talla 40", "categoria_id": 3,
                "categoria_nombre": "Calzado", "cantidad": 2, "precio_unitario": Decimal("30.00"), "costo_unitario": Decimal("18.00"),
            }
        ]
        assert ganancia_de(venta) == Decimal("62.00") - Decimal("36.00") - Decimal("1.50")

    def test_venta_de_rocketfy_con_envio_incluido_usa_el_flete_estimado(self):
        lead = _lead(producto_sku="R-1", producto_nombre="Audífonos", producto_variante=None, cantidad=1,
                     subtotal=Decimal("24.99"), total=Decimal("24.99"), costo_envio=Decimal("0.00"),
                     entrega_opcion_id=None, entrega_nombre=None, entrega_tipo=None, id_pedido_local=1, id_pedido_rocketfy=99)
        venta, _ = armar_venta(lead, ROCKETFY, {"origen": "directo", "id_anuncio": None}, None, "despachada", Decimal("5.00"))

        assert venta["entrega_tipo"] == "incluido" and venta["entrega_nombre"] == "Envío incluido en el precio"
        assert venta["costo_productos"] == Decimal("12.00")
        assert venta["costo_envio_negocio"] == Decimal("5.00")
        assert ganancia_de(venta) == Decimal("7.99")
        assert venta["id_pedido_rocketfy"] == 99

    def test_el_flete_propio_del_producto_se_congela_en_la_venta(self):
        lead = _lead(producto_sku="R-1", cantidad=1, subtotal=Decimal("24.99"), total=Decimal("24.99"),
                     costo_envio=Decimal("0.00"), entrega_opcion_id=None, entrega_nombre=None, entrega_tipo=None)
        producto = {**ROCKETFY, "costo_flete_estimado": Decimal("8.00")}
        venta, _ = armar_venta(lead, producto, None, None, "despachada", Decimal("5.00"))
        assert venta["costo_envio_negocio"] == Decimal("8.00")

    def test_sin_costo_no_se_inventa_la_ganancia(self):
        venta, _ = armar_venta(_lead(), {**PROPIO, "costo_propio": None}, None, None, "por_gestionar", Decimal("5.00"))
        assert venta["costo_productos"] is None and ganancia_de(venta) is None

    def test_envio_aparte_sin_costo_anotado_deja_el_costo_del_envio_sin_saber(self):
        venta, _ = armar_venta(_lead(), PROPIO, None, {"costo_negocio": None}, "por_gestionar", Decimal("5.00"))
        assert venta["costo_envio_negocio"] is None

    def test_lead_viejo_sin_subtotal_lo_deduce_del_total(self):
        venta, _ = armar_venta(_lead(subtotal=None), PROPIO, None, None, "por_gestionar", Decimal("0"))
        assert venta["subtotal"] == Decimal("60.00")

    def test_origen_directo_y_canal_whatsapp_por_defecto(self):
        venta, _ = armar_venta(_lead(), PROPIO, None, None, "por_gestionar", Decimal("0"))
        assert venta["origen"] == "directo" and venta["canal"] == "whatsapp" and venta["id_anuncio"] is None
