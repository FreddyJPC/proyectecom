import os

import responses

from src.app import create_app
from tests.conftest import AUTH_HEADER, mock_login_ok

SUPABASE_URL = os.environ["SUPABASE_URL"]


def _client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


class TestLoginRequerido:
    """Fase 2 - Etapa 1: ninguna ruta interna se sirve sin sesión válida
    de Supabase, salvo /health y /webhooks/* (ver src/app.py)."""

    def test_sin_header_de_autorizacion_devuelve_401(self):
        resp = _client().get("/catalogos/ubicaciones")
        assert resp.status_code == 401

    @responses.activate
    def test_token_rechazado_por_supabase_devuelve_401(self):
        responses.add(responses.GET, f"{SUPABASE_URL}/auth/v1/user", json={"msg": "invalid JWT"}, status=401)

        resp = _client().get("/catalogos/ubicaciones", headers=AUTH_HEADER)
        assert resp.status_code == 401

    @responses.activate
    def test_token_valido_deja_pasar_a_la_ruta(self):
        mock_login_ok()

        resp = _client().get("/catalogos/ubicaciones", headers=AUTH_HEADER)
        assert resp.status_code == 200

    def test_health_no_requiere_login(self):
        resp = _client().get("/health")
        assert resp.status_code == 200
