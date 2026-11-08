"""Galería de fotos de un producto (ADR-012, entrega 2): reglas puras, repositorio, servicio y API."""
from decimal import Decimal
from unittest.mock import patch

import pytest
import responses

from src.config.database import get_connection
from src.routes.imagenes.logica import (
    MAXIMO_POR_PRODUCTO,
    RutaDeImagenInvalida,
    galeria_para_enviar,
    url_publica,
    validar_ruta,
)
from src.routes.imagenes.repository import ImagenRepository as Repo, ImagenYaRegistradaError
from src.routes.productos_bot.exceptions import DatosDeProductoInvalidosError, ProductoBotNoEncontradoError
from src.routes.productos_bot.repository import ProductoBotGestionRepository as Productos
from tests.conftest import AUTH_HEADER, SUPABASE_URL, mock_login_ok
from tests.unit.routes.productos_bot.test_controllers import SERVICIO, _client, _detalle
from tests.unit.routes.productos_bot.test_propios import RepoConPropios, _propio
from tests.unit.routes.productos_bot.test_propios import EntregasEnMemoria, CategoriasEnMemoria
from tests.unit.routes.productos_bot.test_services import AjustesFalsos, MonitoreoFalso, RocketfyFalso
from src.routes.productos_bot.services import ProductosBotService


class TestReglas:
    def test_la_url_publica_la_arma_el_servidor_a_partir_de_la_ruta(self):
        assert url_publica("https://abc.supabase.co/", "PROP-0001/x.jpg") == (
            "https://abc.supabase.co/storage/v1/object/public/productos/PROP-0001/x.jpg"
        )

    def test_la_ruta_con_espacios_o_acentos_se_codifica(self):
        assert url_publica("https://abc.supabase.co", "SKU 1/foto.png").endswith("/productos/SKU%201/foto.png")

    @pytest.mark.parametrize("ruta", ["PROP-0001/abc.jpg", "PROP-0001/a-b_c.1.JPEG", "PROP-0001/z.png"])
    def test_rutas_validas(self, ruta):
        assert validar_ruta("PROP-0001", ruta) == ruta

    @pytest.mark.parametrize(
        "ruta",
        ["", "x.jpg", "OTRO-SKU/a.jpg", "PROP-0001/sub/a.jpg", "PROP-0001/../a.jpg", "PROP-0001/..jpg",
         "PROP-0001/a.gif", "PROP-0001/a.webp", "PROP-0001/a", "PROP-0001/a b.jpg", "/PROP-0001/a.jpg", "PROP-0001/" + "x" * 130 + ".jpg"],
    )
    def test_rutas_que_no_se_aceptan(self, ruta):
        with pytest.raises(RutaDeImagenInvalida):
            validar_ruta("PROP-0001", ruta)

    def test_la_galeria_a_enviar_prefiere_las_subidas(self):
        subidas = [{"url": "https://a/1.jpg"}, {"url": "https://a/2.jpg"}]
        assert galeria_para_enviar(subidas, "https://rocketfy/x.png") == ["https://a/1.jpg", "https://a/2.jpg"]

    def test_sin_subidas_cae_en_la_de_rocketfy_y_sin_ninguna_queda_vacia(self):
        assert galeria_para_enviar([], "https://rocketfy/x.png") == ["https://rocketfy/x.png"]
        assert galeria_para_enviar([], None) == [] and galeria_para_enviar([], "http://inseguro/x.png") == []

    def test_solo_https(self):
        assert galeria_para_enviar([{"url": "http://a/1.jpg"}], None) == []


PREFIJO = "TEST-GALERIA "


def _limpiar():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("delete from productos_bot where nombre like %s", (PREFIJO + "%",))  # cascada: imágenes


@pytest.fixture
def producto():
    _limpiar()
    fila = Productos.crear_propio(
        {
            "nombre": PREFIJO + "Zapatos", "descripcion": "d", "precio": Decimal("30.00"), "variantes": None,
            "tiempo_entrega": "2 días", "metodos_pago_aceptados": "contraentrega", "preguntas_frecuentes": None,
            "temas_no_responder": None, "max_unidades_por_pedido": 1, "categoria_id": None, "costo_propio": None,
            "controla_stock": False, "stock_ultimo": None, "envio_incluido": True, "costo_flete_estimado": None,
        },
        [],
    )
    yield fila["sku"]
    _limpiar()


class TestRepositorio:
    def test_agrega_al_final_y_lista_en_orden(self, producto):
        a = Repo.agregar(producto, "https://x/a.jpg", f"{producto}/a.jpg", "freddy")
        b = Repo.agregar(producto, "https://x/b.jpg", f"{producto}/b.jpg", "freddy")
        assert (a["orden"], b["orden"]) == (0, 1)
        assert [i["storage_path"] for i in Repo.listar(producto)] == [f"{producto}/a.jpg", f"{producto}/b.jpg"]
        assert a["creado_por"] == "freddy"

    def test_la_misma_ruta_no_se_registra_dos_veces(self, producto):
        Repo.agregar(producto, "https://x/a.jpg", f"{producto}/a.jpg", None)
        with pytest.raises(ImagenYaRegistradaError):
            Repo.agregar(producto, "https://x/a.jpg", f"{producto}/a.jpg", None)

    def test_reordenar(self, producto):
        ids = [Repo.agregar(producto, f"https://x/{n}.jpg", f"{producto}/{n}.jpg", None)["id"] for n in "abc"]
        listadas = Repo.reordenar(producto, [ids[2], ids[0], ids[1]])
        assert [i["id"] for i in listadas] == [ids[2], ids[0], ids[1]]

    def test_quitar_devuelve_la_fila_y_solo_de_ese_producto(self, producto):
        foto = Repo.agregar(producto, "https://x/a.jpg", f"{producto}/a.jpg", None)
        assert Repo.quitar("OTRO-SKU", foto["id"]) is None
        borrada = Repo.quitar(producto, foto["id"])
        assert borrada["storage_path"] == f"{producto}/a.jpg" and Repo.listar(producto) == []

    def test_la_base_exige_https(self, producto):
        import psycopg2.errors

        with pytest.raises(psycopg2.errors.CheckViolation):
            Repo.agregar(producto, "http://x/a.jpg", f"{producto}/a.jpg", None)

    def test_al_borrar_el_producto_se_borra_su_galeria(self, producto):
        Repo.agregar(producto, "https://x/a.jpg", f"{producto}/a.jpg", None)
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("delete from productos_bot where sku = %s", (producto,))
        assert Repo.listar(producto) == []

    def test_el_orden_nuevo_arranca_en_cero_en_cada_producto(self, producto):
        otro = Productos.crear_propio(
            {"nombre": PREFIJO + "Otro", "descripcion": "d", "precio": Decimal("5.00"), "variantes": None, "tiempo_entrega": "1",
             "metodos_pago_aceptados": "contraentrega", "preguntas_frecuentes": None, "temas_no_responder": None,
             "max_unidades_por_pedido": 1, "categoria_id": None, "costo_propio": None, "controla_stock": False,
             "stock_ultimo": None, "envio_incluido": True, "costo_flete_estimado": None}, [],
        )["sku"]
        Repo.agregar(producto, "https://x/a.jpg", f"{producto}/a.jpg", None)
        assert Repo.agregar(otro, "https://x/b.jpg", f"{otro}/b.jpg", None)["orden"] == 0


class ImagenesEnMemoria:
    def __init__(self):
        self.filas, self._id = [], 0

    def listar(self, sku):
        return sorted([dict(f) for f in self.filas if f["producto_sku"] == sku], key=lambda f: (f["orden"], f["id"]))

    def agregar(self, sku, url, ruta, usuario):
        if any(f["storage_path"] == ruta for f in self.filas):
            raise ImagenYaRegistradaError("Esa foto ya está registrada.")
        self._id += 1
        fila = {"id": self._id, "producto_sku": sku, "url": url, "storage_path": ruta, "orden": len(self.listar(sku))}
        self.filas.append(fila)
        return fila

    def quitar(self, sku, imagen_id):
        for f in self.filas:
            if f["id"] == imagen_id and f["producto_sku"] == sku:
                self.filas.remove(f)
                return f
        return None

    def reordenar(self, sku, ids):
        for orden, i in enumerate(ids):
            next(f for f in self.filas if f["id"] == i)["orden"] = orden


def _servicio(filas=None):
    imagenes = ImagenesEnMemoria()
    repo = RepoConPropios(filas if filas is not None else [_propio()])
    servicio = ProductosBotService(
        client=RocketfyFalso(), repo=repo, monitoreo_repo=MonitoreoFalso(), ajustes_service=AjustesFalsos(),
        entregas_repo=EntregasEnMemoria(), categorias_repo=CategoriasEnMemoria(), imagenes_repo=imagenes,
    )
    return servicio, imagenes, repo


class TestServicio:
    def test_registrar_arma_la_url_con_el_proyecto_de_supabase_y_la_muestra_en_el_detalle(self):
        servicio, imagenes, repo = _servicio()
        detalle = servicio.registrar_imagen("PROP-0001", "PROP-0001/a.jpg", "freddy@azoshop.com")

        esperada = f"{SUPABASE_URL}/storage/v1/object/public/productos/PROP-0001/a.jpg"
        assert detalle.imagenes == [{"id": 1, "url": esperada, "storage_path": "PROP-0001/a.jpg", "orden": 0}]
        assert repo.historial[-1]["cambios"] == {"fotos": ["+1"]}

    def test_rutas_de_otro_producto_o_formatos_raros_se_rechazan(self):
        servicio, imagenes, _ = _servicio()
        for ruta in ("OTRO/a.jpg", "PROP-0001/a.gif", "PROP-0001/../x.jpg"):
            with pytest.raises(DatosDeProductoInvalidosError):
                servicio.registrar_imagen("PROP-0001", ruta, "x")
        assert imagenes.filas == []

    def test_maximo_de_fotos_por_producto(self):
        servicio, imagenes, _ = _servicio()
        for n in range(MAXIMO_POR_PRODUCTO):
            servicio.registrar_imagen("PROP-0001", f"PROP-0001/{n}.jpg", "x")
        with pytest.raises(DatosDeProductoInvalidosError) as error:
            servicio.registrar_imagen("PROP-0001", "PROP-0001/otra.jpg", "x")
        assert "Máximo" in error.value.mensajes[0]

    def test_la_misma_foto_dos_veces(self):
        servicio, *_ = _servicio()
        servicio.registrar_imagen("PROP-0001", "PROP-0001/a.jpg", "x")
        with pytest.raises(DatosDeProductoInvalidosError):
            servicio.registrar_imagen("PROP-0001", "PROP-0001/a.jpg", "x")

    def test_un_producto_archivado_no_recibe_fotos(self):
        from src.routes.productos_bot.exceptions import TransicionInvalidaError

        servicio, *_ = _servicio([_propio(estado="archivado")])
        with pytest.raises(TransicionInvalidaError):
            servicio.registrar_imagen("PROP-0001", "PROP-0001/a.jpg", "x")

    def test_quitar_y_quitar_una_que_no_existe(self):
        servicio, imagenes, _ = _servicio()
        servicio.registrar_imagen("PROP-0001", "PROP-0001/a.jpg", "x")
        assert servicio.quitar_imagen("PROP-0001", 1, "x").imagenes == []
        with pytest.raises(ProductoBotNoEncontradoError):
            servicio.quitar_imagen("PROP-0001", 1, "x")

    def test_ordenar_exige_exactamente_las_que_hay(self):
        servicio, *_ = _servicio()
        for n in "abc":
            servicio.registrar_imagen("PROP-0001", f"PROP-0001/{n}.jpg", "x")
        orden = servicio.ordenar_imagenes("PROP-0001", [3, 1, 2], "x")
        assert [i["id"] for i in orden.imagenes] == [3, 1, 2]
        for malo in ([1, 2], [1, 2, 3, 4], [1, 1, 2], [1, 2, 9]):
            with pytest.raises(DatosDeProductoInvalidosError):
                servicio.ordenar_imagenes("PROP-0001", malo, "x")


class TestHTTP:
    @responses.activate
    def test_registrar_pasa_solo_la_ruta_nunca_una_url(self):
        mock_login_ok()
        with patch(SERVICIO) as servicio:
            servicio.return_value.registrar_imagen.return_value = _detalle()
            r = _client().post(
                "/productos-bot/PROP-0001/imagenes",
                json={"storagePath": "PROP-0001/a.jpg", "url": "https://malo.example/x.jpg"},
                headers=AUTH_HEADER,
            )
        assert r.status_code == 201
        servicio.return_value.registrar_imagen.assert_called_once_with("PROP-0001", "PROP-0001/a.jpg", "freddyjavier556@gmail.com")

    @responses.activate
    def test_sin_ruta_es_422(self):
        mock_login_ok()
        assert _client().post("/productos-bot/PROP-0001/imagenes", json={}, headers=AUTH_HEADER).status_code == 422

    @responses.activate
    def test_ordenar_y_quitar(self):
        mock_login_ok()
        with patch(SERVICIO) as servicio:
            servicio.return_value.ordenar_imagenes.return_value = _detalle()
            r = _client().put("/productos-bot/PROP-0001/imagenes/orden", json={"ids": [2, 1]}, headers=AUTH_HEADER)
        assert r.status_code == 200
        servicio.return_value.ordenar_imagenes.assert_called_once_with("PROP-0001", [2, 1], "freddyjavier556@gmail.com")

        mock_login_ok()
        with patch(SERVICIO) as servicio:
            servicio.return_value.quitar_imagen.return_value = _detalle()
            assert _client().delete("/productos-bot/PROP-0001/imagenes/5", headers=AUTH_HEADER).status_code == 200
        servicio.return_value.quitar_imagen.assert_called_once_with("PROP-0001", 5, "freddyjavier556@gmail.com")

    @responses.activate
    def test_quitar_una_inexistente_es_404(self):
        mock_login_ok()
        with patch(SERVICIO) as servicio:
            servicio.return_value.quitar_imagen.side_effect = ProductoBotNoEncontradoError("Esa foto no existe en este producto.")
            assert _client().delete("/productos-bot/PROP-0001/imagenes/5", headers=AUTH_HEADER).status_code == 404
