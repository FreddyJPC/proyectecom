"""
StockChecker con un cliente de Rocketfy falso y un reloj controlado: no hay
red ni esperas reales.
"""
from src.integrations.rocketfy import RocketfyRequestError
from src.routes.whatsapp.stock import StockChecker


class ClienteRocketfyFalso:
    def __init__(self, productos=None, error=None):
        self.productos = productos if productos is not None else []
        self.error = error
        self.consultas = []

    def listar_productos(self, q=None, page=1):
        self.consultas.append(q)
        if self.error is not None:
            raise self.error
        return {"data": self.productos}


class Reloj:
    def __init__(self):
        self.ahora = 1000.0

    def __call__(self):
        return self.ahora


def _checker(productos=None, error=None, ttl=300):
    cliente = ClienteRocketfyFalso(productos, error)
    reloj = Reloj()
    return StockChecker(client=cliente, ttl_segundos=ttl, reloj=reloj), cliente, reloj


class TestTiempoDeRecuerdoEsUnParametro:
    """Sin fijar `ttl_segundos`, el StockChecker lo consulta en cada uso (parámetro «Cuánto se
    recuerda el stock consultado»)."""

    @staticmethod
    def _checker_sin_fijar(monkeypatch, segundos):
        from src.config.parametros import parametros

        real = parametros.valor
        valores = {"stock.cache_segundos": segundos}
        monkeypatch.setattr(parametros, "valor", lambda clave: valores[clave] if clave in valores else real(clave))
        cliente = ClienteRocketfyFalso([{"sku": "DEMO-1", "stock": 7}])
        reloj = Reloj()
        return StockChecker(client=cliente, reloj=reloj), cliente, reloj, valores

    def test_por_defecto_recuerda_cinco_minutos(self):
        cliente = ClienteRocketfyFalso([{"sku": "DEMO-1", "stock": 7}])
        reloj = Reloj()
        checker = StockChecker(client=cliente, reloj=reloj)
        checker.stock_de("DEMO-1")
        reloj.ahora += 299
        checker.stock_de("DEMO-1")
        assert len(cliente.consultas) == 1
        reloj.ahora += 2
        checker.stock_de("DEMO-1")
        assert len(cliente.consultas) == 2

    def test_cambiar_el_parametro_se_nota_sin_reconstruir_el_checker(self, monkeypatch):
        checker, cliente, reloj, valores = self._checker_sin_fijar(monkeypatch, 60)
        checker.stock_de("DEMO-1")
        reloj.ahora += 90
        checker.stock_de("DEMO-1")
        assert len(cliente.consultas) == 2  # 90 s > 60 s: vuelve a preguntar

        valores["stock.cache_segundos"] = 600  # el dueño sube el tiempo desde la app
        reloj.ahora += 90
        checker.stock_de("DEMO-1")
        assert len(cliente.consultas) == 2  # 90 s < 600 s: ahora lo recuerda


class TestStockDe:
    def test_devuelve_el_stock_del_sku_exacto_ignorando_otros_resultados_de_la_busqueda(self):
        checker, cliente, _ = _checker(
            [
                {"sku": "DEMO-10", "stock": 99},  # la búsqueda por "DEMO-1" también lo trae
                {"sku": "demo-1 ", "stock": 7},  # mayúsculas/espacios no importan
            ]
        )

        assert checker.stock_de("DEMO-1") == 7
        assert cliente.consultas == ["DEMO-1"]

    def test_la_segunda_consulta_dentro_del_ttl_sale_de_la_cache(self):
        checker, cliente, reloj = _checker([{"sku": "DEMO-1", "stock": 7}])

        checker.stock_de("DEMO-1")
        reloj.ahora += 299
        assert checker.stock_de("DEMO-1") == 7
        assert len(cliente.consultas) == 1

    def test_pasado_el_ttl_vuelve_a_consultar(self):
        checker, cliente, reloj = _checker([{"sku": "DEMO-1", "stock": 7}])

        checker.stock_de("DEMO-1")
        reloj.ahora += 300
        checker.stock_de("DEMO-1")
        assert len(cliente.consultas) == 2

    def test_fresco_ignora_la_cache_y_la_actualiza(self):
        checker, cliente, _ = _checker([{"sku": "DEMO-1", "stock": 7}])
        checker.stock_de("DEMO-1")

        cliente.productos = [{"sku": "DEMO-1", "stock": 2}]
        assert checker.stock_de("DEMO-1", fresco=True) == 2
        assert checker.stock_de("DEMO-1") == 2  # la cache quedó con el dato nuevo
        assert len(cliente.consultas) == 2

    def test_si_rocketfy_falla_devuelve_none_y_no_cachea_el_fallo(self):
        checker, cliente, _ = _checker(error=RocketfyRequestError("timeout"))

        assert checker.stock_de("DEMO-1") is None

        cliente.error = None
        cliente.productos = [{"sku": "DEMO-1", "stock": 4}]
        assert checker.stock_de("DEMO-1") == 4  # se reintenta de inmediato

    def test_cualquier_excepcion_inesperada_tambien_falla_abierto(self):
        checker, _, _ = _checker(error=ValueError("respuesta rara"))
        assert checker.stock_de("DEMO-1") is None

    def test_sku_que_no_aparece_devuelve_none(self):
        checker, _, _ = _checker([{"sku": "OTRO", "stock": 5}])
        assert checker.stock_de("DEMO-1") is None

    def test_stock_cero_es_un_dato_valido_y_se_cachea(self):
        checker, cliente, _ = _checker([{"sku": "DEMO-1", "stock": 0}])

        assert checker.stock_de("DEMO-1") == 0
        assert checker.stock_de("DEMO-1") == 0
        assert len(cliente.consultas) == 1

    def test_stock_ausente_en_el_producto_cuenta_como_cero(self):
        checker, _, _ = _checker([{"sku": "DEMO-1"}])
        assert checker.stock_de("DEMO-1") == 0
