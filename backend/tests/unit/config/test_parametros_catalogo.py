"""
El catálogo de parámetros (src/config/parametros/catalogo.py): invariantes de TODO el
catálogo (cada parámetro explicado, con un respaldo válido y sin secretos) y las reglas
de lectura de cada tipo.
"""
import pytest

from src.config.parametros import CATALOGO, GRUPOS, ParametroDesconocidoError, ValorInvalido, definicion
from src.config.parametros.catalogo import (
    PALABRAS_DE_SECRETO,
    TIPO_BOOLEANO,
    TIPO_ENTERO,
    TIPO_OPCION,
    TIPO_TEXTO,
)

POR_TIPO = {tipo: [p for p in CATALOGO if p.tipo == tipo] for tipo in (TIPO_ENTERO, TIPO_BOOLEANO, TIPO_TEXTO, TIPO_OPCION)}


class TestInvariantesDelCatalogo:
    def test_las_claves_son_unicas(self):
        claves = [p.clave for p in CATALOGO]
        assert len(claves) == len(set(claves))

    def test_estan_todos_los_parametros(self):
        # 15 del plan de parametrización + «Fotos por envío» (ADR-012) + 8 de leads (enfriamiento, atribución y cliente
        # recurrente) + 10 del seguimiento automático (interruptores, horario, tope, textos y su tarea).
        assert len(CATALOGO) == 41

    def test_el_seguimiento_automatico_viene_apagado_de_fabrica(self):
        """Escribirle a un cliente por iniciativa propia nunca debe empezar solo: hay que encenderlo a propósito."""
        assert definicion("seguimiento.empujon_activo").defecto is False
        assert definicion("seguimiento.plantilla_activa").defecto is False

    @pytest.mark.parametrize("p", CATALOGO, ids=lambda p: p.clave)
    def test_cada_parametro_esta_explicado_y_pertenece_a_un_grupo_real(self, p):
        assert p.nombre.strip() and len(p.para_que_sirve.strip()) > 40
        assert p.aplica.strip()
        assert p.grupo in {g.clave for g in GRUPOS}

    @pytest.mark.parametrize("p", CATALOGO, ids=lambda p: p.clave)
    def test_el_valor_por_defecto_cumple_las_reglas_del_propio_parametro(self, p):
        # El respaldo del código tiene que ser un valor que la app también aceptaría guardar.
        assert p.desde_json(p.defecto) == p.defecto

    @pytest.mark.parametrize("p", POR_TIPO[TIPO_ENTERO], ids=lambda p: p.clave)
    def test_los_enteros_tienen_rango_y_unidad(self, p):
        assert p.minimo is not None and p.maximo is not None and p.minimo < p.maximo
        assert p.unidad

    @pytest.mark.parametrize("p", POR_TIPO[TIPO_TEXTO], ids=lambda p: p.clave)
    def test_los_textos_tienen_largo_maximo(self, p):
        assert p.largo_maximo

    @pytest.mark.parametrize("p", POR_TIPO[TIPO_OPCION], ids=lambda p: p.clave)
    def test_las_opciones_incluyen_el_valor_por_defecto(self, p):
        assert p.defecto in {o.valor for o in p.opciones}
        assert all(o.etiqueta for o in p.opciones)

    @pytest.mark.parametrize("p", CATALOGO, ids=lambda p: p.clave)
    def test_ningun_parametro_parece_un_secreto(self, p):
        """Los secretos viven solo en Railway/Vercel (CLAUDE.md): no pueden entrar al catálogo."""
        nombres = [p.clave.lower(), (p.variable_servidor or "").lower()]
        for palabra in PALABRAS_DE_SECRETO:
            assert not any(palabra in n for n in nombres), f"{p.clave} parece un secreto ({palabra})"

    def test_las_tareas_automaticas_tienen_un_minimo_que_protege_a_rocketfy(self):
        for p in CATALOGO:
            if p.clave.startswith("jobs.minutos_"):
                assert p.minimo >= 15

    def test_el_modelo_de_ia_es_una_lista_cerrada_sin_los_modelos_que_rompen_el_codigo(self):
        valores = {o.valor for o in definicion("llm.modelo").opciones}
        # Estos rechazan la herramienta forzada de «Redactar con IA» (ver el comentario del catálogo).
        assert not valores & {"claude-sonnet-5-5", "claude-opus-5-5", "claude-fable-5-1"}
        assert "claude-sonnet-5" in valores


class TestDefinicion:
    def test_clave_desconocida(self):
        with pytest.raises(ParametroDesconocidoError):
            definicion("no.existe")


class TestEnteros:
    P = definicion("bot.max_mensajes_historial")  # 10..100

    @pytest.mark.parametrize("crudo, esperado", [(40, 40), ("40", 40), (" 55 ", 55), (10, 10), (100, 100)])
    def test_acepta_enteros_y_texto_de_enteros(self, crudo, esperado):
        assert self.P.desde_json(crudo) == esperado

    @pytest.mark.parametrize("crudo", [9, 101, 0, -5, 40.5, "40.5", "abc", "", True, False, None, [40]])
    def test_rechaza_lo_demas(self, crudo):
        with pytest.raises(ValorInvalido):
            self.P.desde_json(crudo)

    def test_el_mensaje_dice_el_rango_y_la_unidad(self):
        with pytest.raises(ValorInvalido, match=r"entre 10 y 100 mensajes"):
            self.P.desde_json(5)

    def test_desde_texto_del_servidor_tambien_respeta_el_rango(self):
        with pytest.raises(ValorInvalido):
            self.P.desde_texto("0", del_servidor=True)


class TestBooleanos:
    P = definicion("bot.enviar_fotos")

    def test_desde_json_exige_un_booleano_de_verdad(self):
        assert self.P.desde_json(True) is True and self.P.desde_json(False) is False
        for malo in ("true", 1, 0, None):
            with pytest.raises(ValorInvalido):
                self.P.desde_json(malo)

    def test_lo_guardado_es_true_o_false(self):
        assert self.P.desde_texto("true") is True and self.P.desde_texto("false") is False
        with pytest.raises(ValorInvalido):
            self.P.desde_texto("quizas")

    @pytest.mark.parametrize("texto, esperado", [("1", True), ("true", True), ("YES", True), ("sí", True), ("si", True), ("false", False), ("0", False), ("no", False), ("cualquier cosa", False)])
    def test_la_variable_del_servidor_conserva_su_criterio_de_siempre(self, texto, esperado):
        assert self.P.desde_texto(texto, del_servidor=True) is esperado

    def test_a_texto(self):
        assert self.P.a_texto(True) == "true" and self.P.a_texto(False) == "false"


class TestTextos:
    P = definicion("bot.texto_postventa")  # máx. 300

    def test_recorta_los_espacios(self):
        assert self.P.desde_json("  Hola  ") == "Hola"

    @pytest.mark.parametrize("crudo", ["", "   ", "x" * 301, "con\x00nulo", 5, None, True])
    def test_rechaza_vacios_largos_y_otros_tipos(self, crudo):
        with pytest.raises(ValorInvalido):
            self.P.desde_json(crudo)

    def test_acepta_emojis_y_el_largo_justo(self):
        assert self.P.desde_json("🙋" * 300) == "🙋" * 300


class TestOpciones:
    P = definicion("llm.modelo")

    def test_solo_acepta_las_de_la_lista(self):
        assert self.P.desde_json("claude-haiku-5-5") == "claude-haiku-5-5"
        for malo in ("claude-inventado", "", 3, None):
            with pytest.raises(ValorInvalido):
                self.P.desde_json(malo)

    def test_la_variable_del_servidor_puede_traer_un_modelo_fuera_de_la_lista(self):
        # Lo que ya está configurado en Railway no se descarta por no estar en el catálogo cerrado.
        assert self.P.desde_texto("claude-lo-que-sea", del_servidor=True) == "claude-lo-que-sea"
        with pytest.raises(ValorInvalido):
            self.P.desde_texto("", del_servidor=True)
