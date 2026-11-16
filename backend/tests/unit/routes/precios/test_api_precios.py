"""
API de precios y ofertas (ADR-017) contra la base desechable de pruebas: reglas por producto, valor del negocio, ofertas y su
vínculo con anuncios. Cada prueba borra lo que crea.
"""
from decimal import Decimal

import pytest
import responses

from src.app import create_app
from src.config.database import get_connection
from src.routes.precios.validacion import validar_oferta, validar_reglas_producto
from tests.conftest import AUTH_HEADER, mock_login_ok

SKU_A = "PRUEBA-PRECIOS-A"
SKU_B = "PRUEBA-PRECIOS-B"
SKU_P = "PROP-PRUEBA-PRECIOS"
ANUNCIO = "AD-PRUEBA-PRECIOS-1"


def _client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def _limpiar():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("delete from anuncios_productos where id_anuncio = %s", (ANUNCIO,))
            cur.execute(
                "delete from ofertas where id in (select oferta_id from oferta_items where producto_sku = any(%s))", ([SKU_A, SKU_B, SKU_P],)
            )
            cur.execute("delete from productos_bot where sku = any(%s)", ([SKU_A, SKU_B, SKU_P],))
            cur.execute("update ajustes_negocio set transferencia_tipo = null, transferencia_valor = null where id = 1")


@pytest.fixture(autouse=True)
def productos():
    _limpiar()
    with get_connection() as conn:
        with conn.cursor() as cur:
            for sku, nombre, precio in ((SKU_A, "Linterna", "25.00"), (SKU_B, "Cargador", "12.00")):
                cur.execute(
                    "insert into productos_bot (sku, nombre, descripcion, precio, tiempo_entrega, costo_rocketfy, max_unidades_por_pedido) "
                    "values (%s, %s, 'd', %s, '2 días', 8.00, 3)",
                    (sku, nombre, precio),
                )
            cur.execute(
                "insert into productos_bot (sku, nombre, descripcion, precio, tiempo_entrega, proveedor_id, costo_propio) "
                "values (%s, 'Zapatos', 'd', 30.00, '2 días', 2, 10.00)",
                (SKU_P,),
            )
    yield
    _limpiar()


class TestReglasDeProducto:
    @responses.activate
    def test_leer_y_guardar_reglas_y_escalas(self):
        mock_login_ok()
        c = _client()
        r = c.get(f"/precios/productos/{SKU_A}", headers=AUTH_HEADER)
        assert r.status_code == 200 and r.json["precio"] == "25.00" and r.json["escalas"] == [] and r.json["regateoTipo"] is None

        r = c.put(
            f"/precios/productos/{SKU_A}",
            json={
                "transferenciaTipo": "precio", "transferenciaValor": "20", "regateoTipo": "monto", "regateoValor": "3",
                "escalas": [{"cantidad": 2, "precioTotal": "45"}],
            },
            headers=AUTH_HEADER,
        )
        assert r.status_code == 200, r.json
        assert (r.json["transferenciaValor"], r.json["regateoValor"]) == ("20.00", "3.00")
        assert r.json["escalas"] == [{"cantidad": 2, "precioTotal": "45.00"}]

        r = c.put(f"/precios/productos/{SKU_A}", json={"escalas": []}, headers=AUTH_HEADER)
        assert r.status_code == 200 and r.json["escalas"] == [] and r.json["transferenciaTipo"] is None

    @responses.activate
    def test_errores_en_espanol(self):
        mock_login_ok()
        r = _client().put(
            f"/precios/productos/{SKU_A}",
            json={"transferenciaTipo": "precio", "transferenciaValor": "30", "escalas": [{"cantidad": 2, "precioTotal": "60"}]},
            headers=AUTH_HEADER,
        )
        assert r.status_code == 422
        assert "menor que el precio normal" in r.json["errores"]["transferenciaValor"][0]
        assert "no es una rebaja" in r.json["errores"]["escalas.0"][0]

    @responses.activate
    def test_producto_inexistente(self):
        mock_login_ok()
        assert _client().get("/precios/productos/NO-EXISTE-XYZ", headers=AUTH_HEADER).status_code == 404


class TestNegocio:
    @responses.activate
    def test_guardar_y_borrar(self):
        mock_login_ok()
        c = _client()
        r = c.put("/precios/negocio", json={"transferenciaTipo": "porcentaje", "transferenciaValor": "10"}, headers=AUTH_HEADER)
        assert r.status_code == 200 and r.json == {"transferenciaTipo": "porcentaje", "transferenciaValor": "10.00"}
        assert c.get("/precios/negocio", headers=AUTH_HEADER).json["transferenciaValor"] == "10.00"
        assert c.put("/precios/negocio", json={"transferenciaTipo": "porcentaje", "transferenciaValor": "150"}, headers=AUTH_HEADER).status_code == 422
        assert c.put("/precios/negocio", json={"transferenciaTipo": None}, headers=AUTH_HEADER).json["transferenciaTipo"] is None


class TestOfertas:
    def _crear(self, c, **cambios):
        datos = {
            "nombre": "Linterna + cargador", "precio": "30", "items": [{"productoSku": SKU_A}, {"productoSku": SKU_B}],
            "textoAnuncio": "Combo a $30", "maximoPorCliente": 2,
        }
        datos.update(cambios)
        return c.post("/precios/ofertas", json=datos, headers=AUTH_HEADER)

    @responses.activate
    def test_crear_listar_editar_y_vincular_un_anuncio(self):
        mock_login_ok()
        c = _client()
        r = self._crear(c)
        assert r.status_code == 201, r.json
        oferta = r.json
        assert (oferta["precio"], oferta["precioLista"], oferta["ahorro"], oferta["situacion"]) == ("30.00", "37.00", "7.00", "vigente")
        assert oferta["visibilidad"] == "anuncio" and [i["productoSku"] for i in oferta["items"]] == [SKU_A, SKU_B]

        assert any(o["id"] == oferta["id"] for o in c.get("/precios/ofertas", headers=AUTH_HEADER).json["ofertas"])
        r = c.put(f"/precios/ofertas/{oferta['id']}", json={"estado": "pausada"}, headers=AUTH_HEADER)
        assert r.status_code == 200 and r.json["situacion"] == "pausada" and r.json["precio"] == "30.00"

        r = c.put(f"/precios/ofertas/{oferta['id']}/anuncios/{ANUNCIO}", json={}, headers=AUTH_HEADER)
        assert r.status_code == 200 and r.json["ofertaId"] == oferta["id"]
        assert c.get(f"/precios/ofertas/{oferta['id']}", headers=AUTH_HEADER).json["anuncios"] == [ANUNCIO]

        # El anuncio ahora puede pasar a un producto (con confirmación) sin chocar con la regla «un solo vínculo».
        r = c.put(f"/anuncios/{ANUNCIO}/producto", json={"sku": SKU_A, "reasignar": True}, headers=AUTH_HEADER)
        assert r.status_code == 200, r.json

    @responses.activate
    def test_combo_mas_caro_que_por_separado_o_sin_productos(self):
        mock_login_ok()
        c = _client()
        assert "por separado" in self._crear(c, precio="40").json["errores"]["precio"][0]
        assert self._crear(c, items=[]).status_code == 422

    @responses.activate
    def test_p5_no_mezcla_rocketfy_y_propio(self):
        mock_login_ok()
        r = self._crear(_client(), items=[{"productoSku": SKU_A}, {"productoSku": SKU_P}], precio="50")
        assert r.status_code == 422 and "P5" in r.json["errores"]["items"][0]

    @responses.activate
    def test_fechas_invertidas(self):
        mock_login_ok()
        r = self._crear(_client(), desde="2026-12-10T00:00:00-05:00", hasta="2026-12-01T00:00:00-05:00")
        assert r.status_code == 422 and "posterior" in r.json["errores"]["hasta"][0]


class TestValidacionPura:
    PRODUCTO = {"precio": Decimal("25"), "envio_incluido": True, "max_unidades_por_pedido": 3}

    def test_bajo_margen_avisa(self):
        from src.routes.precios.reglas import AjustesPiso

        ajustes = AjustesPiso(True, Decimal("25"), Decimal("4"), Decimal("0"), Decimal("0"))
        r = validar_reglas_producto({"transferenciaTipo": "precio", "transferenciaValor": "15"}, self.PRODUCTO, Decimal("10"), ajustes)
        assert r.valido and r.bajo_margen and "18.67" in r.bajo_margen[0]  # (10 + 4) / 0.75

    def test_envio_gratis_no_aplica_si_ya_esta_incluido(self):
        r = validar_reglas_producto({"envioGratisDesdeUnidades": 2}, self.PRODUCTO, None, None)
        assert "envioGratis" in r.errores

    def test_escala_sobre_el_maximo(self):
        r = validar_reglas_producto({"escalas": [{"cantidad": 5, "precioTotal": "100"}]}, self.PRODUCTO, None, None)
        assert "máximo por pedido" in r.errores["escalas.0"][0]

    def test_oferta_bajo_margen_solo_con_autorizacion(self):
        from src.routes.precios.reglas import AjustesPiso

        ajustes = AjustesPiso(True, Decimal("25"), Decimal("4"), Decimal("0"), Decimal("0"))
        productos = {"A": {"precio": Decimal("25"), "proveedor_cierre": "rocketfy"}}
        entrada = {"nombre": "Promo", "precio": "15", "items": [{"productoSku": "A"}]}
        assert validar_oferta(entrada, productos, {"A": Decimal("10")}, ajustes, True).bajo_margen
        autorizada = validar_oferta({**entrada, "bajoMargenAutorizado": True}, productos, {"A": Decimal("10")}, ajustes, True)
        assert not autorizada.bajo_margen
