import os

import requests
import responses

from src.config.settings import load_settings
from src.config.supabase_auth import verificar_token

SUPABASE_URL = os.environ["SUPABASE_URL"]


class TestVerificarToken:
    @responses.activate
    def test_token_valido_devuelve_el_usuario(self):
        responses.add(
            responses.GET,
            f"{SUPABASE_URL}/auth/v1/user",
            json={"id": "u1", "email": "freddyjavier556@gmail.com"},
            status=200,
        )

        usuario = verificar_token("token-valido", load_settings())

        assert usuario == {"id": "u1", "email": "freddyjavier556@gmail.com"}

    @responses.activate
    def test_token_invalido_devuelve_none(self):
        responses.add(
            responses.GET,
            f"{SUPABASE_URL}/auth/v1/user",
            json={"msg": "invalid JWT"},
            status=401,
        )

        assert verificar_token("token-vencido", load_settings()) is None

    @responses.activate
    def test_error_de_red_devuelve_none_en_vez_de_lanzar(self):
        responses.add(
            responses.GET,
            f"{SUPABASE_URL}/auth/v1/user",
            body=requests.exceptions.ConnectionError("boom"),
        )

        assert verificar_token("token-cualquiera", load_settings()) is None
