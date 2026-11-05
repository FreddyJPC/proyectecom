"""
Registro de usos de la IA contra la base real (la de pruebas local): el conteo
del tope diario y, sobre todo, que «hoy» sea el día de ECUADOR y no el de UTC.
"""
import psycopg2.errors
import pytest

from src.config.database import get_connection
from src.routes.productos_bot.generaciones import GeneracionesIARepository as Repo

SKU = "TEST-FASE-D-IA"
INICIO_DE_HOY_EN_ECUADOR = "(date_trunc('day', now() at time zone 'America/Guayaquil') at time zone 'America/Guayaquil')"


def _borrar():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("delete from generaciones_ia where sku = %s", (SKU,))


@pytest.fixture(autouse=True)
def limpio():
    _borrar()
    yield
    _borrar()


def _insertar(resultado="ok", tipo="contenido", cuando="now()"):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"insert into generaciones_ia (sku, tipo, resultado, creado_en) values (%s, %s, %s, {cuando})",
                (SKU, tipo, resultado),
            )


class TestRegistrar:
    def test_guarda_quien_que_modelo_y_los_campos(self):
        Repo.registrar(SKU, "ana@ejemplo.com", "modelo-x", "ok", ["nombre", "descripcion"])

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("select sku, usuario, tipo, modelo, campos, resultado, creado_en from generaciones_ia where sku = %s", (SKU,))
                fila = cur.fetchone()
        assert fila[:6] == (SKU, "ana@ejemplo.com", "contenido", "modelo-x", "nombre,descripcion", "ok")
        assert fila[6] is not None

    def test_rechaza_un_resultado_desconocido_antes_de_tocar_la_base(self):
        with pytest.raises(ValueError):
            Repo.registrar(SKU, None, None, "quizas", [])

    def test_la_base_tambien_lo_rechaza(self):
        with pytest.raises(psycopg2.errors.CheckViolation):
            _insertar(resultado="quizas")


class TestContarHoy:
    def test_cuentan_los_ok_y_los_invalidos_pero_no_los_fallos(self):
        antes = Repo.contar_hoy()
        for resultado in ("ok", "ok", "invalido", "fallo", "fallo"):
            _insertar(resultado)
        assert Repo.contar_hoy() - antes == 3

    def test_solo_cuenta_el_tipo_pedido(self):
        antes = Repo.contar_hoy()
        _insertar("ok", tipo="contenido")
        _insertar("ok", tipo="simulacion")  # (otra fase futura: tiene su propio tope)
        assert Repo.contar_hoy() - antes == 1
        assert Repo.contar_hoy("simulacion") >= 1

    def test_lo_de_ayer_no_cuenta(self):
        antes = Repo.contar_hoy()
        _insertar("ok", cuando="now() - interval '1 day'")
        assert Repo.contar_hoy() == antes

    def test_el_dia_cambia_a_medianoche_de_ecuador_no_a_medianoche_utc(self):
        antes = Repo.contar_hoy()
        # 23:59 de AYER en Ecuador = 04:59 de HOY en UTC: si se contara por UTC, entraría.
        _insertar("ok", cuando=f"{INICIO_DE_HOY_EN_ECUADOR} - interval '1 minute'")
        assert Repo.contar_hoy() == antes
        # 00:01 de HOY en Ecuador sí cuenta.
        _insertar("ok", cuando=f"{INICIO_DE_HOY_EN_ECUADOR} + interval '1 minute'")
        assert Repo.contar_hoy() == antes + 1
