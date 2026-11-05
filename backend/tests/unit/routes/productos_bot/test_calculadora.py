"""
Calculadora de precio: lógica pura con Decimal. El primer bloque reproduce el
ejemplo del plan (docs/PLAN_GESTION_PRODUCTOS.md, sección 7) para que la
documentación y el código no puedan separarse sin que un test lo note.
"""
from decimal import Decimal

import pytest

from src.routes.ajustes.dto import AjustesNegocio
from src.routes.productos_bot.calculadora import (
    envio_para_piso,
    ganancia_por_unidad,
    margen_pct,
    precio_para_margen,
    recomendar,
    redondear_precio,
    siguiente_terminado_99,
)

D = Decimal


def _ajustes(**cambios):
    datos = dict(
        margen_minimo_pct=D("25.00"),
        margen_objetivo_pct=D("35.00"),
        envio_estimado=D("5.00"),
        otros_costos_fijos=D("0.00"),
        otros_costos_pct=D("0.00"),
        redondeo="terminado_99",
        confirmado=True,
    )
    datos.update(cambios)
    return AjustesNegocio(**datos)


class TestEjemploDelPlan:
    """costo $10.00, envío $5.00, margen 25 % / 35 %, sugerido $29.90."""

    def setup_method(self):
        self.r = recomendar(D("10.00"), D("29.90"), _ajustes())
        self.por_clave = {n.clave: n for n in self.r.niveles}

    def test_piso(self):
        assert self.r.piso == D("15.00")  # máx(10 + 5, 10)

    def test_los_tres_niveles_con_los_numeros_del_plan(self):
        assert [(n.clave, n.precio, n.ganancia, n.margen_pct) for n in self.r.niveles] == [
            ("minimo", D("20.99"), D("5.99"), D("28.5")),
            ("recomendado", D("23.99"), D("8.99"), D("37.5")),
            ("premium", D("29.90"), D("14.90"), D("49.8")),
        ]

    def test_el_margen_es_sobre_el_precio_no_un_recargo_sobre_el_costo(self):
        # Con costo total $15 y margen 25 %: 15 / 0.75 = $20.00, NO 15 x 1.25 = $18.75.
        assert precio_para_margen(D("10.00"), _ajustes(), D("25.00")) == D("20")


class TestRedondeo:
    @pytest.mark.parametrize(
        "x, esperado",
        [
            ("20.00", "20.99"),
            ("23.08", "23.99"),
            ("20.99", "20.99"),  # ya termina en .99: se queda
            ("20.995", "21.99"),
            ("19.99", "19.99"),
            ("0.50", "0.99"),
            ("0", "0.99"),
            ("100.00", "100.99"),
        ],
    )
    def test_siguiente_terminado_99_nunca_baja(self, x, esperado):
        resultado = siguiente_terminado_99(D(x))
        assert resultado == D(esperado)
        assert resultado >= D(x)

    def test_sin_redondeo_solo_sube_al_siguiente_centavo(self):
        assert redondear_precio(D("24.6153846"), "ninguno") == D("24.62")
        assert redondear_precio(D("24.60"), "ninguno") == D("24.60")

    def test_con_redondeo_99(self):
        assert redondear_precio(D("24.6153846"), "terminado_99") == D("24.99")


class TestOtrosCostos:
    def test_costos_fijos_y_porcentaje_entran_en_el_precio_y_en_la_ganancia(self):
        ajustes = _ajustes(otros_costos_fijos=D("1.00"), otros_costos_pct=D("5.00"), redondeo="ninguno")
        # (10 + 5 + 1) / (1 - 0.30 - 0.05) = 24.6153... -> 24.62
        assert precio_para_margen(D("10.00"), ajustes, D("30.00")).quantize(D("0.0001")) == D("24.6154")

        r = recomendar(D("10.00"), None, ajustes)
        recomendado = {n.clave: n for n in r.niveles}["recomendado"]  # margen objetivo 35 %
        # Lo importante: tras restar TODOS los costos, el margen real no baja del objetivo.
        assert recomendado.margen_pct >= D("34.9")
        assert recomendado.ganancia == ganancia_por_unidad(recomendado.precio, D("10.00"), ajustes)

    def test_ganancia_resta_costo_envio_fijos_y_porcentaje_del_precio(self):
        ajustes = _ajustes(otros_costos_fijos=D("1.00"), otros_costos_pct=D("5.00"))
        # 24.62 - 10 - 5 - 1 - (24.62 x 5 %) = 7.389 -> 7.39
        assert ganancia_por_unidad(D("24.62"), D("10.00"), ajustes) == D("7.39")

    def test_margen_pct_con_un_decimal(self):
        assert margen_pct(D("24.62"), D("7.39")) == D("30.0")
        assert margen_pct(D("0"), D("1.00")) == D("0.0")


class TestPiso:
    def test_nunca_baja_del_recaudo_minimo_de_rocketfy(self):
        r = recomendar(D("3.00"), None, _ajustes(envio_estimado=D("2.00")))
        assert r.piso == D("10.00")  # costo + envío = 5, pero Rocketfy exige 10
        # Y los niveles no quedan por debajo del piso (6.67 -> sube a 10 -> .99):
        assert all(n.precio >= D("10.00") for n in r.niveles)
        assert r.niveles[0].precio == D("10.99")

    def test_sin_redondeo_el_nivel_puede_ser_exactamente_el_piso(self):
        r = recomendar(D("3.00"), None, _ajustes(envio_estimado=D("2.00"), redondeo="ninguno"))
        assert r.niveles[0].precio == D("10.00")

    def test_el_piso_cuenta_el_envio_solo_si_el_dueno_ya_confirmo_sus_ajustes(self):
        confirmados = _ajustes(confirmado=True)
        de_partida = _ajustes(confirmado=False)

        assert envio_para_piso(confirmados) == D("5.00")
        assert envio_para_piso(de_partida) is None
        assert recomendar(D("12.00"), None, confirmados).piso == D("17.00")
        assert recomendar(D("12.00"), None, de_partida).piso == D("12.00")

    def test_con_ajustes_de_partida_igual_se_recomienda_usando_su_envio(self):
        r = recomendar(D("10.00"), D("29.90"), _ajustes(confirmado=False))
        assert r.niveles[0].precio == D("20.99")  # el envío de partida sí se usa para recomendar


class TestPrecioSugeridoDeRocketfy:
    def test_sin_sugerido_solo_hay_dos_niveles(self):
        assert [n.clave for n in recomendar(D("10.00"), None, _ajustes()).niveles] == ["minimo", "recomendado"]

    def test_premium_solo_si_el_sugerido_supera_al_recomendado(self):
        r = recomendar(D("10.00"), D("23.99"), _ajustes())
        assert [n.clave for n in r.niveles] == ["minimo", "recomendado"]

    def test_sugerido_bajo_el_recomendado_avisa_de_competitividad(self):
        r = recomendar(D("10.00"), D("22.00"), _ajustes())  # entre mínimo (20.99) y recomendado (23.99)
        assert [n.clave for n in r.niveles] == ["minimo", "recomendado"]
        assert any("competitividad" in a for a in r.avisos)

    def test_sugerido_bajo_el_minimo_avisa_que_ganarias_menos_del_margen_minimo(self):
        r = recomendar(D("10.00"), D("18.00"), _ajustes())
        assert any("margen mínimo" in a and "$18.00" in a for a in r.avisos)
        assert not any("competitividad" in a for a in r.avisos)


class TestCasosLimite:
    def test_sin_costo_no_hay_niveles_y_se_explica_como_resolverlo(self):
        r = recomendar(None, D("29.90"), _ajustes(), precio_evaluado=D("24.99"))
        assert r.niveles == [] and r.evaluacion is None
        assert any("Actualizar desde Rocketfy" in a for a in r.avisos)
        assert r.piso == D("10.00")  # solo el recaudo mínimo: sin costo no se puede más

    def test_porcentajes_que_suman_cien_no_dan_precio(self):
        ajustes = _ajustes(margen_minimo_pct=D("50"), margen_objetivo_pct=D("60"), otros_costos_pct=D("40"))
        assert precio_para_margen(D("10"), ajustes, D("60")) is None
        r = recomendar(D("10.00"), None, ajustes)
        assert r.niveles == []
        assert any("100 %" in a for a in r.avisos)

    def test_todo_es_decimal_nunca_float(self):
        r = recomendar(D("10.00"), D("29.90"), _ajustes(), precio_evaluado=D("24.99"))
        for n in r.niveles:
            assert all(isinstance(v, Decimal) for v in (n.precio, n.ganancia, n.margen_pct))
        assert all(isinstance(v, Decimal) for v in (r.piso, r.evaluacion.precio, r.evaluacion.ganancia, r.evaluacion.margen_pct))


class TestEvaluacionDeUnPrecio:
    def test_precio_sano_no_avisa_nada(self):
        r = recomendar(D("10.00"), D("29.90"), _ajustes(), precio_evaluado=D("24.99"))
        ev = r.evaluacion
        assert (ev.ganancia, ev.margen_pct, ev.bajo_piso, ev.bajo_margen_minimo) == (D("9.99"), D("40.0"), False, False)
        assert r.avisos == []

    def test_sobre_el_piso_pero_bajo_el_margen_minimo(self):
        r = recomendar(D("10.00"), D("29.90"), _ajustes(), precio_evaluado=D("17.00"))
        ev = r.evaluacion
        assert (ev.ganancia, ev.margen_pct) == (D("2.00"), D("11.8"))
        assert (ev.bajo_piso, ev.bajo_margen_minimo) == (False, True)
        assert any("margen" in a and "25.00 %" in a for a in r.avisos)

    def test_bajo_el_piso_no_se_podra_publicar_y_pierde_plata(self):
        r = recomendar(D("10.00"), D("29.90"), _ajustes(), precio_evaluado=D("12.00"))
        ev = r.evaluacion
        assert (ev.ganancia, ev.bajo_piso) == (D("-3.00"), True)
        assert any("no se podrá publicar" in a and "$15.00" in a for a in r.avisos)
        assert any("pierdes $3.00" in a for a in r.avisos)

    def test_con_ajustes_de_partida_perder_plata_se_avisa_pero_no_es_bajo_el_piso(self):
        # Piso sin envío = $12.00; a $13.00 se puede publicar, pero con el envío de partida ($5) se pierde.
        r = recomendar(D("12.00"), None, _ajustes(confirmado=False), precio_evaluado=D("13.00"))
        assert r.evaluacion.bajo_piso is False
        assert r.evaluacion.ganancia == D("-4.00")
        assert any("pierdes $4.00" in a for a in r.avisos)

    def test_precio_cero_o_negativo_no_se_evalua(self):
        assert recomendar(D("10.00"), None, _ajustes(), precio_evaluado=D("0")).evaluacion is None


class TestCompetencia:
    def test_tu_precio_mayor_que_el_de_la_competencia(self):
        r = recomendar(D("10.00"), D("29.90"), _ajustes(), precio_evaluado=D("24.99"), precio_competencia=D("22.00"))
        assert any("$22.00" in a and "competencia" in a for a in r.avisos)

    def test_competencia_bajo_tu_minimo_sin_precio_evaluado(self):
        r = recomendar(D("10.00"), D("29.90"), _ajustes(), precio_competencia=D("15.00"))
        assert any("competencia" in a and "$20.99" in a for a in r.avisos)

    def test_competencia_mas_cara_no_avisa(self):
        r = recomendar(D("10.00"), D("29.90"), _ajustes(), precio_evaluado=D("24.99"), precio_competencia=D("39.00"))
        assert r.avisos == []
