import os

import pytest
import responses

import src.config.settings  # noqa: F401  (side effect: load_dotenv() antes de leer os.environ)

SUPABASE_URL = os.environ["SUPABASE_URL"]

AUTH_HEADER = {"Authorization": "Bearer token-de-prueba"}


def mock_login_ok(email: str = "freddyjavier556@gmail.com") -> None:
    """Registra en `responses` una respuesta 200 de Supabase para el token
    de prueba de AUTH_HEADER. Llamar dentro de un test con @responses.activate,
    antes de golpear una ruta protegida por el login (ver src/app.py)."""
    responses.add(
        responses.GET,
        f"{SUPABASE_URL}/auth/v1/user",
        json={"id": "00000000-0000-0000-0000-000000000000", "email": email},
        status=200,
    )


@pytest.fixture(autouse=True)
def _sin_memoria_de_configuracion():
    """Los parámetros del sistema y las instrucciones publicadas de Victoria se recuerdan 30 s en
    memoria (ver src/config/parametros y src/routes/whatsapp/instrucciones.py): cada test empieza y
    termina sin recordar nada, para que lo que uno guarde no se filtre al siguiente."""
    from src.config.parametros import parametros
    from src.routes.whatsapp.instrucciones import instrucciones_vigentes

    parametros.invalidar()
    instrucciones_vigentes.invalidar()
    yield
    parametros.invalidar()
    instrucciones_vigentes.invalidar()


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "confirma_datos: la prueba usa la confirmación de datos con el cliente ENCENDIDA (como en producción)"
    )


@pytest.fixture(autouse=True)
def _confirmacion_de_datos_apagada(request, monkeypatch):
    """La confirmación de datos antes de cerrar (`bot.confirmar_datos_antes_de_cerrar`) viene encendida de fábrica. Las
    pruebas de cierre de venta que no tratan de ella la dejan apagada para no repetir el paso de confirmar en cada una;
    las que sí la prueban llevan `@pytest.mark.confirma_datos`."""
    if request.node.get_closest_marker("confirma_datos"):
        return
    from src.config.parametros import parametros

    real = parametros.valor
    monkeypatch.setattr(
        parametros, "valor", lambda clave: False if clave == "bot.confirmar_datos_antes_de_cerrar" else real(clave)
    )
