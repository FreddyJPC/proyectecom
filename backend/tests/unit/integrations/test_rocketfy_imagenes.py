"""La API real de Rocketfy devuelve la imagen como ruta relativa (`/storage/...`)."""
import pytest

from src.integrations.rocketfy.imagenes import url_de_imagen

BASE = "https://rocket-e.com/api"


class TestUrlDeImagen:
    def test_una_ruta_relativa_se_completa_con_el_sitio_de_la_api_sin_el_api(self):
        assert url_de_imagen("/storage/products/4193/foto.jpg", BASE) == "https://rocket-e.com/storage/products/4193/foto.jpg"

    def test_sigue_el_dominio_configurado_aunque_sea_otro_pais(self):
        assert url_de_imagen("/storage/x.jpg", "https://cl.rocket-e.com/api") == "https://cl.rocket-e.com/storage/x.jpg"

    @pytest.mark.parametrize("url", ["https://cdn.ejemplo.com/a.png", "http://cdn.ejemplo.com/a.png", "HTTPS://CDN.EJEMPLO.COM/A.PNG"])
    def test_una_url_completa_se_deja_igual(self, url):
        assert url_de_imagen(url, BASE) == url

    def test_sin_esquema_con_doble_barra_se_asume_https(self):
        assert url_de_imagen("//cdn.ejemplo.com/a.png", BASE) == "https://cdn.ejemplo.com/a.png"

    def test_se_recortan_los_espacios(self):
        assert url_de_imagen("  /storage/a.jpg \n", BASE) == "https://rocket-e.com/storage/a.jpg"

    @pytest.mark.parametrize("valor", [None, "", "   ", "foto.jpg", "storage/a.jpg", "javascript:alert(1)", "data:image/png;base64,AAAA", "ftp://x/y.png", "file:///etc/passwd"])
    def test_lo_que_no_sirve_devuelve_none(self, valor):
        assert url_de_imagen(valor, BASE) is None

    @pytest.mark.parametrize("base", ["", "no-es-una-url", "ftp://rocket-e.com/api", "/api"])
    def test_con_una_base_inservible_una_ruta_relativa_no_se_inventa(self, base):
        assert url_de_imagen("/storage/a.jpg", base) is None or base == ""

    def test_sin_base_explicita_usa_la_configurada(self):
        assert url_de_imagen("/storage/a.jpg") == "http://localhost:9/storage/a.jpg"  # ROCKETFY_BASE_URL de prueba
