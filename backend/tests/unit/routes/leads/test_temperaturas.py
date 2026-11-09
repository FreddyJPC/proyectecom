"""Reglas puras de temperatura (docs/PLAN_LEADS_CRM.md §2): sin base de datos."""
import pytest

from src.routes.leads import temperaturas as t


class TestHechos:
    @pytest.mark.parametrize("estado,esperada", [
        ("despachado", t.GANADO), ("por_gestionar", t.GANADO), ("cancelado", t.PERDIDO),
        ("recopilando_datos", None), ("esperando_pago", None), ("listo_para_despacho", None), (None, None),
    ])
    def test_la_etapa_impone_la_temperatura_solo_cuando_hay_un_hecho(self, estado, esperada):
        assert t.temperatura_por_hechos(estado) == esperada


class TestClasificacion:
    def test_hay_cinco_temperaturas_tres_abiertas_y_dos_finales(self):
        assert t.TEMPERATURAS == ("caliente", "tibio", "frio", "perdido", "ganado")
        assert t.ABIERTAS == ("caliente", "tibio", "frio") and t.FINALES == ("perdido", "ganado")

    def test_abierta_y_final_son_excluyentes(self):
        for temperatura in t.TEMPERATURAS:
            assert t.es_abierta(temperatura) != t.es_final(temperatura)
        assert not t.es_valida("hirviendo") and not t.es_abierta(None) and not t.es_final(None)

    def test_el_catalogo_de_motivos_de_perdida_tiene_etiquetas_en_espanol(self):
        assert "otro" in t.MOTIVOS_DE_PERDIDA and t.motivo_de_perdida_valido("precio")
        assert not t.motivo_de_perdida_valido("porque si") and not t.motivo_de_perdida_valido(None)
        assert all(etiqueta for etiqueta in t.MOTIVOS_DE_PERDIDA.values())


class TestEnfriamientoPorSilencio:
    UMBRALES = (2, 5, 14)

    @pytest.mark.parametrize("actual,dias,esperada", [
        ("caliente", 0.5, "caliente"),   # escribió hace poco: sigue caliente
        ("caliente", 2, "tibio"),        # alcanza el primer umbral
        ("caliente", 5, "frio"),         # puede saltar más de un peldaño si el silencio es largo
        ("caliente", 14, "perdido"),
        ("tibio", 1, "tibio"),           # no se calienta solo por haber escrito hace poco
        ("tibio", 5, "frio"),
        ("tibio", 30, "perdido"),
        ("frio", 6, "frio"),             # ya está más frío que tibio: conserva
        ("frio", 14, "perdido"),
    ])
    def test_baja_segun_los_dias_sin_responder(self, actual, dias, esperada):
        assert t.temperatura_por_silencio(actual, dias, *self.UMBRALES) == esperada

    def test_nunca_calienta(self):
        for actual in t.ABIERTAS:
            for dias in (0, 1, 3, 8, 20):
                nueva = t.temperatura_por_silencio(actual, dias, *self.UMBRALES)
                assert t.ABIERTAS.index(nueva) >= t.ABIERTAS.index(actual) if nueva in t.ABIERTAS else nueva == t.PERDIDO

    @pytest.mark.parametrize("final", ["perdido", "ganado"])
    def test_un_lead_terminado_no_se_toca(self, final):
        assert t.temperatura_por_silencio(final, 999, *self.UMBRALES) == final

    def test_umbrales_desordenados_se_ordenan_en_vez_de_romper(self):
        assert t.temperatura_por_silencio("caliente", 6, 14, 2, 5) == t.temperatura_por_silencio("caliente", 6, 2, 5, 14) == "frio"


class TestTipoDeContacto:
    @pytest.mark.parametrize("compras,tipo", [(0, "prospecto"), (1, "cliente"), (2, "recurrente"), (7, "recurrente"), (-1, "prospecto")])
    def test_se_deduce_de_las_compras(self, compras, tipo):
        assert t.tipo_de_contacto(compras) == tipo


class TestMotivo:
    def test_se_limpia_y_se_recorta(self):
        assert t.limpiar_motivo("  quiere   pensarlo \n más ") == "quiere pensarlo más"
        assert t.limpiar_motivo("   ") is None and t.limpiar_motivo(None) is None
        assert len(t.limpiar_motivo("x" * 1000)) == t.LARGO_MAXIMO_MOTIVO
