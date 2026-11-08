"""
El servicio de parámetros (src/config/parametros/servicio.py) con un repositorio falso:
prioridad app > servidor > código, memoria de 30 s, respaldo si la base falla y avisos
de cambio. No toca la base.
"""
from datetime import datetime, timezone

import pytest

from src.config.parametros import (
    CATALOGO,
    ORIGEN_APP,
    ORIGEN_ORIGINAL,
    ORIGEN_SERVIDOR,
    ParametroDesconocidoError,
    ParametrosService,
    ValorInvalido,
)

CLAVE = "bot.max_mensajes_historial"  # entero 10..100, respaldo 40, variable BOT_MAX_MENSAJES_HISTORIAL
VARIABLE = "BOT_MAX_MENSAJES_HISTORIAL"


class RepoFalso:
    def __init__(self):
        self.filas = {}
        self.historial_guardado = []
        self.lecturas = 0
        self.falla = False

    def listar(self):
        self.lecturas += 1
        if self.falla:
            raise RuntimeError("la base no responde")
        return {k: dict(v) for k, v in self.filas.items()}

    def guardar(self, clave, valor, usuario):
        anterior = self.filas.get(clave, {}).get("valor")
        if anterior == valor:
            return False
        self.filas[clave] = {"valor": valor, "actualizado_por": usuario, "actualizado_en": datetime(2026, 11, 8, tzinfo=timezone.utc)}
        self.historial_guardado.append((clave, anterior, valor, usuario))
        return True

    def restaurar(self, clave, usuario):
        fila = self.filas.pop(clave, None)
        if fila is None:
            return False
        self.historial_guardado.append((clave, fila["valor"], None, usuario))
        return True

    def historial(self, limite=50):
        return []


class Reloj:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


@pytest.fixture
def repo():
    return RepoFalso()


@pytest.fixture
def reloj():
    return Reloj()


@pytest.fixture
def entorno():
    return {}


@pytest.fixture
def servicio(repo, reloj, entorno):
    return ParametrosService(repo=repo, reloj=reloj, entorno=entorno)


class TestPrioridad:
    def test_sin_nada_vale_el_respaldo_del_codigo(self, servicio):
        r = servicio.resolver(CLAVE)
        assert (r.valor, r.origen) == (40, ORIGEN_ORIGINAL)

    def test_la_variable_del_servidor_gana_al_codigo(self, servicio, entorno):
        entorno[VARIABLE] = "25"
        r = servicio.resolver(CLAVE)
        assert (r.valor, r.origen, r.valor_servidor) == (25, ORIGEN_SERVIDOR, 25)

    def test_lo_guardado_en_la_app_gana_a_todo(self, servicio, repo, entorno):
        entorno[VARIABLE] = "25"
        repo.filas[CLAVE] = {"valor": "60", "actualizado_por": "ana@x.com", "actualizado_en": None}
        r = servicio.resolver(CLAVE)
        assert (r.valor, r.origen, r.valor_app, r.valor_servidor, r.actualizado_por) == (60, ORIGEN_APP, 60, 25, "ana@x.com")

    def test_un_booleano_guardado_como_false_gana_aunque_sea_falso(self, servicio, repo, entorno):
        entorno["BOT_ENVIAR_FOTOS"] = "true"
        repo.filas["bot.enviar_fotos"] = {"valor": "false", "actualizado_por": None, "actualizado_en": None}
        r = servicio.resolver("bot.enviar_fotos")
        assert (r.valor, r.origen) == (False, ORIGEN_APP)

    def test_variable_vacia_cuenta_como_no_puesta(self, servicio, entorno):
        entorno[VARIABLE] = "   "
        assert servicio.resolver(CLAVE).origen == ORIGEN_ORIGINAL

    def test_restaurar_vuelve_al_servidor_y_si_no_al_codigo(self, servicio, entorno):
        entorno[VARIABLE] = "25"
        servicio.guardar(CLAVE, 60, "ana@x.com")
        assert servicio.valor(CLAVE) == 60
        assert servicio.restaurar(CLAVE, "ana@x.com").valor == 25
        del entorno[VARIABLE]
        assert servicio.valor(CLAVE) == 40

    def test_la_variable_del_servidor_se_lee_siempre_fresca(self, servicio, entorno):
        assert servicio.valor(CLAVE) == 40
        entorno[VARIABLE] = "70"
        assert servicio.valor(CLAVE) == 70

    def test_todo_el_catalogo_se_resuelve_sin_nada_guardado(self, servicio):
        resueltos = servicio.listar()
        assert [r.parametro.clave for r in resueltos] == [p.clave for p in CATALOGO]
        assert all(r.origen == ORIGEN_ORIGINAL and r.valor == r.parametro.defecto for r in resueltos)

    def test_clave_desconocida_falla_fuerte(self, servicio):
        with pytest.raises(ParametroDesconocidoError):
            servicio.valor("no.existe")


class TestValoresInvalidos:
    def test_un_valor_guardado_invalido_se_ignora_y_se_avisa(self, servicio, repo, caplog):
        repo.filas[CLAVE] = {"valor": "muchos", "actualizado_por": None, "actualizado_en": None}
        r = servicio.resolver(CLAVE)
        assert (r.valor, r.origen) == (40, ORIGEN_ORIGINAL)
        assert any("ya no es válido" in a for a in r.avisos)
        assert "no es válido" in caplog.text

    def test_un_valor_fuera_de_rango_guardado_a_mano_se_ignora(self, servicio, repo):
        repo.filas[CLAVE] = {"valor": "5000", "actualizado_por": None, "actualizado_en": None}
        assert servicio.valor(CLAVE) == 40

    def test_una_variable_del_servidor_invalida_se_ignora_y_se_avisa(self, servicio, entorno):
        entorno[VARIABLE] = "mil"
        r = servicio.resolver(CLAVE)
        assert (r.valor, r.origen) == (40, ORIGEN_ORIGINAL)
        assert any(VARIABLE in a for a in r.avisos)

    def test_el_aviso_en_el_log_sale_una_sola_vez(self, servicio, entorno, caplog):
        entorno[VARIABLE] = "mil"
        for _ in range(5):
            servicio.valor(CLAVE)
        assert caplog.text.count("la variable BOT_MAX_MENSAJES_HISTORIAL del servidor") == 1

    def test_una_variable_con_valor_valido_pero_el_guardado_invalido_usa_la_variable(self, servicio, repo, entorno):
        entorno[VARIABLE] = "25"
        repo.filas[CLAVE] = {"valor": "xx", "actualizado_por": None, "actualizado_en": None}
        r = servicio.resolver(CLAVE)
        assert (r.valor, r.origen) == (25, ORIGEN_SERVIDOR)


class TestMemoria:
    def test_dentro_de_treinta_segundos_no_se_vuelve_a_consultar_la_base(self, servicio, repo, reloj):
        servicio.valor(CLAVE)
        servicio.valor("bot.max_turnos_herramientas")
        reloj.t += 29
        servicio.valor(CLAVE)
        assert repo.lecturas == 1

    def test_pasados_treinta_segundos_se_vuelve_a_consultar(self, servicio, repo, reloj):
        servicio.valor(CLAVE)
        reloj.t += 31
        repo.filas[CLAVE] = {"valor": "80", "actualizado_por": None, "actualizado_en": None}
        assert servicio.valor(CLAVE) == 80
        assert repo.lecturas == 2

    def test_guardar_se_nota_al_instante_sin_esperar_los_treinta_segundos(self, servicio, repo):
        assert servicio.valor(CLAVE) == 40
        servicio.guardar(CLAVE, 55, "ana@x.com")
        assert servicio.valor(CLAVE) == 55

    def test_un_cambio_hecho_directo_en_la_base_se_nota_al_vencer_la_memoria(self, servicio, repo, reloj):
        assert servicio.valor(CLAVE) == 40
        repo.filas[CLAVE] = {"valor": "80", "actualizado_por": None, "actualizado_en": None}
        assert servicio.valor(CLAVE) == 40  # todavía recuerda
        servicio.invalidar()
        assert servicio.valor(CLAVE) == 80


class TestSiLaBaseFalla:
    def test_al_arrancar_sin_base_se_usa_el_respaldo_y_no_se_lanza(self, servicio, repo, entorno):
        repo.falla = True
        entorno[VARIABLE] = "25"
        assert servicio.valor(CLAVE) == 25
        assert servicio.valor("bot.max_turnos_herramientas") == 5

    def test_se_conserva_lo_ultimo_que_se_leyo(self, servicio, repo, reloj):
        repo.filas[CLAVE] = {"valor": "80", "actualizado_por": None, "actualizado_en": None}
        assert servicio.valor(CLAVE) == 80
        repo.falla = True
        reloj.t += 31
        assert servicio.valor(CLAVE) == 80

    def test_reintenta_pronto_y_se_recupera_cuando_la_base_vuelve(self, servicio, repo, reloj):
        repo.falla = True
        assert servicio.valor(CLAVE) == 40
        lecturas = repo.lecturas
        reloj.t += 5  # antes del reintento: no martilla la base
        servicio.valor(CLAVE)
        assert repo.lecturas == lecturas
        repo.falla = False
        repo.filas[CLAVE] = {"valor": "80", "actualizado_por": None, "actualizado_en": None}
        reloj.t += 6  # ya pasaron los 10 s del reintento
        assert servicio.valor(CLAVE) == 80


class TestGuardar:
    def test_valida_antes_de_escribir(self, servicio, repo):
        with pytest.raises(ValorInvalido):
            servicio.guardar(CLAVE, 5, "ana@x.com")
        assert repo.filas == {} and repo.historial_guardado == []

    def test_clave_desconocida(self, servicio):
        with pytest.raises(ParametroDesconocidoError):
            servicio.guardar("no.existe", 1, "ana@x.com")

    def test_guarda_con_su_historial(self, servicio, repo):
        r = servicio.guardar(CLAVE, "60", "ana@x.com")
        assert (r.valor, r.origen) == (60, ORIGEN_APP)
        assert repo.historial_guardado == [(CLAVE, None, "60", "ana@x.com")]

    def test_guardar_lo_mismo_no_escribe_otra_vez_ni_avisa(self, servicio, repo):
        avisos = []
        servicio.suscribir("bot.", avisos.append)
        servicio.guardar(CLAVE, 60, "ana@x.com")
        servicio.guardar(CLAVE, 60, "ana@x.com")
        assert len(repo.historial_guardado) == 1 and avisos == [CLAVE]

    def test_restaurar_sin_nada_guardado_no_hace_nada(self, servicio, repo):
        avisos = []
        servicio.suscribir("bot.", avisos.append)
        assert servicio.restaurar(CLAVE, "ana@x.com").origen == ORIGEN_ORIGINAL
        assert repo.historial_guardado == [] and avisos == []

    def test_los_booleanos_se_guardan_como_true_o_false(self, servicio, repo):
        servicio.guardar("sync.autopausa_agotado", False, "ana@x.com")
        assert repo.filas["sync.autopausa_agotado"]["valor"] == "false"
        assert servicio.valor("sync.autopausa_agotado") is False


class TestSuscriptores:
    def test_avisan_solo_si_la_clave_empieza_por_el_prefijo(self, servicio):
        jobs, bot = [], []
        servicio.suscribir("jobs.", jobs.append)
        servicio.suscribir("bot.", bot.append)
        servicio.guardar("jobs.minutos_sync_productos", 30, "ana@x.com")
        servicio.restaurar("jobs.minutos_sync_productos", "ana@x.com")
        assert jobs == ["jobs.minutos_sync_productos"] * 2 and bot == []

    def test_un_suscriptor_que_falla_no_impide_guardar(self, servicio):
        def roto(_clave):
            raise RuntimeError("boom")

        servicio.suscribir("bot.", roto)
        assert servicio.guardar(CLAVE, 60, "ana@x.com").valor == 60
