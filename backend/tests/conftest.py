import os

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
