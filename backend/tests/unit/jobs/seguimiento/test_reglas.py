"""Reglas puras del seguimiento automático: momento, horario de Ecuador, tope diario y nombre de plantilla."""
from datetime import datetime, timedelta, timezone

import pytest

from src.jobs.seguimiento.reglas import (
    cupo_restante,
    dentro_del_horario,
    es_momento_de_la_plantilla,
    es_momento_del_empujon,
    hora_de_ecuador,
    inicio_del_dia_de_ecuador,
    nombre_de_plantilla_valido,
)

AHORA = datetime(2026, 11, 10, 17, 0, tzinfo=timezone.utc)  # 12:00 en Ecuador


def _hace(horas):
    return AHORA - timedelta(hours=horas)


class TestHorarioDeEcuador:
    def test_la_hora_se_cuenta_en_ecuador_utc_menos_5(self):
        assert hora_de_ecuador(AHORA) == 12
        assert hora_de_ecuador(datetime(2026, 11, 10, 3, 0, tzinfo=timezone.utc)) == 22
        assert hora_de_ecuador(datetime(2026, 11, 10, 4, 59, tzinfo=timezone.utc)) == 23

    @pytest.mark.parametrize("horas_utc,esperado", [(13, False), (14, True), (24, True), (25, False)])
    def test_de_9_a_20(self, horas_utc, esperado):
        # Horas contadas desde las 00:00 UTC del 10 de noviembre. 13 = 8:00 Ecuador (todavía no); 14 = 9:00 (entra);
        # 24 = 19:00 (todavía); 25 = 20:00 (ya no: la hora final no se incluye).
        momento = datetime(2026, 11, 10, 0, 0, tzinfo=timezone.utc) + timedelta(hours=horas_utc)
        assert dentro_del_horario(momento, 9, 20) is esperado

    @pytest.mark.parametrize("desde,hasta", [(20, 9), (9, 9), (15, 10)])
    def test_un_rango_al_reves_o_vacio_no_envia_nada(self, desde, hasta):
        for hora in range(24):
            assert dentro_del_horario(datetime(2026, 11, 10, hora, 0, tzinfo=timezone.utc), desde, hasta) is False

    def test_el_dia_para_el_tope_empieza_a_la_medianoche_de_ecuador(self):
        # Las 12:00 de Ecuador del 10 de noviembre: el día empezó a las 00:00 de Ecuador = 05:00 UTC.
        assert inicio_del_dia_de_ecuador(AHORA) == datetime(2026, 11, 10, 5, 0, tzinfo=timezone.utc)
        # A las 02:00 UTC del 10 todavía es el 9 en Ecuador (21:00): el día empezó el 9.
        assert inicio_del_dia_de_ecuador(datetime(2026, 11, 10, 2, 0, tzinfo=timezone.utc)) == datetime(2026, 11, 9, 5, 0, tzinfo=timezone.utc)


class TestMomentoDelEmpujon:
    def test_antes_de_la_espera_todavia_no(self):
        assert es_momento_del_empujon(_hace(3.9), AHORA, 4) is False

    def test_pasada_la_espera_si(self):
        assert es_momento_del_empujon(_hace(4), AHORA, 4) is True
        assert es_momento_del_empujon(_hace(10), AHORA, 4) is True

    def test_deja_una_hora_antes_de_que_se_cierre_la_ventana(self):
        assert es_momento_del_empujon(_hace(23), AHORA, 4) is True
        assert es_momento_del_empujon(_hace(23.01), AHORA, 4) is False
        assert es_momento_del_empujon(_hace(25), AHORA, 4) is False

    def test_la_espera_se_ajusta(self):
        assert es_momento_del_empujon(_hace(2), AHORA, 1) is True
        assert es_momento_del_empujon(_hace(2), AHORA, 3) is False


class TestMomentoDeLaPlantilla:
    def test_solo_cuando_la_ventana_de_24_horas_ya_se_cerro(self):
        assert es_momento_de_la_plantilla(_hace(23.9), AHORA) is False
        assert es_momento_de_la_plantilla(_hace(24), AHORA) is False
        assert es_momento_de_la_plantilla(_hace(24.1), AHORA) is True
        assert es_momento_de_la_plantilla(_hace(100), AHORA) is True

    def test_no_se_solapa_con_el_empujon_salvo_el_margen_de_una_hora(self):
        # Entre las 23 y las 24 h no corresponde ninguno de los dos: el empujón ya no y la plantilla todavía no.
        silencio = _hace(23.5)
        assert es_momento_del_empujon(silencio, AHORA, 4) is False
        assert es_momento_de_la_plantilla(silencio, AHORA) is False


class TestTopeYNombre:
    def test_cupo(self):
        assert cupo_restante(10, 0) == 10
        assert cupo_restante(10, 7) == 3
        assert cupo_restante(10, 10) == 0
        assert cupo_restante(10, 15) == 0

    @pytest.mark.parametrize("nombre", ["retomar_conversacion", "a", "plantilla_2", "x" * 100])
    def test_nombres_validos(self, nombre):
        assert nombre_de_plantilla_valido(nombre) is True

    @pytest.mark.parametrize("nombre", ["", "Retomar", "con espacio", "con-guion", "ñandú", "x" * 101, None])
    def test_nombres_invalidos(self, nombre):
        assert nombre_de_plantilla_valido(nombre) is False
