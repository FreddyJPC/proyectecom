from decimal import Decimal

from src.routes.whatsapp.ficha import formatear_ficha_producto


def _producto(**cambios):
    producto = {
        "sku": "DEMO-1",
        "nombre": "Producto Demo",
        "descripcion": "Un producto de prueba.",
        "precio": Decimal("24.99"),
        "tiempo_entrega": "2 a 4 días hábiles",
        "metodos_pago_aceptados": "contraentrega",
    }
    producto.update(cambios)
    return producto


class TestFormatearFichaProducto:
    def test_incluye_sku_precio_por_unidad_y_maximo_de_unidades(self):
        ficha = formatear_ficha_producto(_producto(max_unidades_por_pedido=3))

        assert "SKU: DEMO-1" in ficha
        assert "Precio por unidad: $24.99" in ficha
        assert "Unidades máximas por pedido: 3" in ficha

    def test_el_maximo_es_un_dato_interno_que_victoria_no_debe_mencionar_por_su_cuenta(self):
        ficha = formatear_ficha_producto(_producto(max_unidades_por_pedido=1))
        assert "NO lo menciones por tu cuenta" in ficha
        assert "solo dilo si el cliente pregunta" in ficha

    def test_sin_maximo_en_los_datos_se_asume_una_unidad(self):
        assert "Unidades máximas por pedido: 1" in formatear_ficha_producto(_producto())
        assert "Unidades máximas por pedido: 1" in formatear_ficha_producto(_producto(max_unidades_por_pedido=None))

    def test_los_campos_opcionales_solo_aparecen_si_existen(self):
        minima = formatear_ficha_producto(_producto())
        for etiqueta in ("Variantes:", "Preguntas frecuentes:", "Temas que NO debes responder:"):
            assert etiqueta not in minima

        completa = formatear_ficha_producto(
            _producto(variantes="negro, blanco", preguntas_frecuentes="¿Trae cargador? Sí.", temas_no_responder="garantías")
        )
        assert "Variantes: negro, blanco" in completa
        assert "Preguntas frecuentes: ¿Trae cargador? Sí." in completa
        assert "Temas que NO debes responder: garantías" in completa
