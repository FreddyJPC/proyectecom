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
