"""
Las instrucciones de Victoria (src/routes/whatsapp/instrucciones.py): el archivo original partido en
secciones, el ensamblado (que no puede romper `str.format`), la validación y la lectura con respaldo.
No toca la base (el repositorio es un doble).
"""
import pytest

from src.routes.whatsapp import instrucciones as ins
from src.routes.whatsapp.instrucciones import (
    EDITABLES,
    GENERAL,
    HUECOS,
    MAXIMO_TOTAL,
    SECCIONES,
    ArchivoOriginalInvalido,
    InstruccionesInvalidas,
    InstruccionesVigentes,
    caracteres_fijos,
    cuerpo_fijo,
    ensamblar,
    estimar_tokens,
    secciones_originales,
    texto_original,
    validar,
)

HUECOS_RELLENOS = {"contexto_producto": "FICHA", "contexto_lead_actual": "LEAD", "fecha_actual": "HOY"}


def _validas(**cambios):
    secciones = secciones_originales()
    secciones.update(cambios)
    return secciones


class TestElArchivoOriginal:
    def test_tiene_las_diez_secciones_que_el_codigo_espera(self):
        assert [s.id for s in SECCIONES] == ["intro", "personalidad", "objetivo", "producto", "reglas", "herramientas", "variantes", "clasificacion", "estado", "fecha"]
        # Si alguien renombra un título del archivo, esto avisa antes de llegar a producción.
        assert ins._trozos().keys() == {s.id for s in SECCIONES}

    def test_ensamblar_sin_cambios_devuelve_el_archivo_idéntico_byte_a_byte(self):
        assert ensamblar() == texto_original()
        assert ensamblar(secciones_originales()) == texto_original()

    def test_las_secciones_bloqueadas_son_las_de_los_huecos_y_las_herramientas(self):
        assert [s.id for s in SECCIONES if not s.editable] == ["producto", "herramientas", "estado", "fecha"]
        for hueco, seccion in zip(HUECOS, ("producto", "estado", "fecha")):
            assert "{" + hueco + "}" in cuerpo_fijo(seccion)

    def test_el_texto_original_se_puede_rellenar(self):
        listo = texto_original().format(**HUECOS_RELLENOS)
        assert "FICHA" in listo and "LEAD" in listo and "HOY" in listo and "{" not in listo

    def test_si_el_archivo_no_tiene_las_secciones_esperadas_falla_fuerte(self, monkeypatch):
        monkeypatch.setattr(ins, "texto_original", lambda: "Eres Victoria.\n\n## Otra cosa\ntexto\n")
        ins._trozos.cache_clear()
        try:
            with pytest.raises(ArchivoOriginalInvalido):
                ins._trozos()
        finally:
            ins._trozos.cache_clear()


class TestEnsamblar:
    def test_el_texto_editado_reemplaza_solo_su_seccion(self):
        armado = ensamblar(_validas(personalidad="Eres muy amable."))
        assert "Eres muy amable." in armado
        assert "Hablas como una persona real" not in armado
        assert "## Tu personalidad\nEres muy amable.\n\n## Tu objetivo" in armado
        # lo demás queda como estaba
        assert cuerpo_fijo("herramientas") in armado and "## Reglas que nunca rompes" in armado

    def test_las_llaves_del_texto_editado_no_rompen_el_format(self):
        """El riesgo principal del análisis: una `{` suelta dejaría muda a Victoria con todos los clientes."""
        armado = ensamblar(_validas(reglas="Nunca digas {precio} ni }}raro{{ ni {contexto_producto} en las reglas."))
        listo = armado.format(**HUECOS_RELLENOS)  # no debe lanzar
        assert "{precio}" in listo and "}}raro{{" in listo
        # el hueco real sigue rellenándose una sola vez, en su sección bloqueada
        assert listo.count("FICHA") == 1
        assert "{contexto_producto} en las reglas" in listo

    def test_los_huecos_del_sistema_estan_siempre_aunque_se_edite_todo(self):
        todo = {s.id: f"Texto de {s.id}." for s in EDITABLES}
        listo = ensamblar(todo).format(**HUECOS_RELLENOS)
        assert all(valor in listo for valor in HUECOS_RELLENOS.values())

    def test_el_espacio_de_los_bordes_se_recorta(self):
        assert "## Tu objetivo\nVender.\n\n" in ensamblar(_validas(objetivo="  \n Vender. \n\n "))

    def test_la_primera_seccion_no_lleva_titulo(self):
        assert ensamblar(_validas(intro="Eres Vera, asesora.")).startswith("Eres Vera, asesora.\n\n## Tu personalidad")


class TestValidar:
    def test_el_original_es_valido_y_se_devuelve_limpio(self):
        assert validar(secciones_originales()) == secciones_originales()

    def test_devuelve_los_textos_recortados(self):
        assert validar(_validas(objetivo="  Vender.  "))["objetivo"] == "Vender."

    @pytest.mark.parametrize("seccion", [s.id for s in EDITABLES])
    def test_ninguna_seccion_editable_puede_quedar_vacia_ni_faltar(self, seccion):
        with pytest.raises(InstruccionesInvalidas) as e:
            validar(_validas(**{seccion: "   "}))
        assert e.value.errores == {seccion: ["No puede quedar vacía."]}

        incompleta = secciones_originales()
        del incompleta[seccion]
        with pytest.raises(InstruccionesInvalidas) as e:
            validar(incompleta)
        assert e.value.errores == {seccion: ["Falta esta sección."]}

    @pytest.mark.parametrize("seccion", [s.id for s in EDITABLES])
    def test_cada_seccion_tiene_su_largo_maximo(self, seccion):
        maximo = next(s.maximo for s in EDITABLES if s.id == seccion)
        with pytest.raises(InstruccionesInvalidas) as e:
            validar(_validas(**{seccion: "x" * (maximo + 1)}))
        assert "demasiado larga" in e.value.errores[seccion][0]

    def test_no_se_pueden_editar_las_secciones_bloqueadas(self):
        for bloqueada in ("herramientas", "producto", "estado", "fecha", "inventada"):
            with pytest.raises(InstruccionesInvalidas) as e:
                validar({**secciones_originales(), bloqueada: "otra cosa"})
            assert GENERAL in e.value.errores and bloqueada in e.value.errores[GENERAL][0]

    @pytest.mark.parametrize("titulo", ["## Un título", "# Otro", "texto\n### Más abajo"])
    def test_no_se_aceptan_titulos_que_imiten_a_los_del_sistema(self, titulo):
        with pytest.raises(InstruccionesInvalidas) as e:
            validar(_validas(reglas=titulo))
        assert "No uses títulos" in e.value.errores["reglas"][0]

    def test_el_prompt_completo_tiene_un_maximo(self):
        casi_todo = {s.id: "x" * s.maximo for s in EDITABLES}
        assert sum(s.maximo for s in EDITABLES) + caracteres_fijos() > MAXIMO_TOTAL  # el tope total sí puede saltar
        with pytest.raises(InstruccionesInvalidas) as e:
            validar(casi_todo)
        assert GENERAL in e.value.errores and str(MAXIMO_TOTAL) in e.value.errores[GENERAL][0]

    @pytest.mark.parametrize("malo", [None, "texto", ["a"], 5])
    def test_algo_que_no_es_un_conjunto_de_secciones(self, malo):
        with pytest.raises(InstruccionesInvalidas) as e:
            validar(malo)
        assert GENERAL in e.value.errores

    def test_un_valor_que_no_es_texto(self):
        with pytest.raises(InstruccionesInvalidas) as e:
            validar(_validas(objetivo=123))
        assert e.value.errores == {"objetivo": ["Debe ser un texto."]}

    def test_junta_todos_los_errores_de_una_vez(self):
        with pytest.raises(InstruccionesInvalidas) as e:
            validar(_validas(objetivo="", reglas="", personalidad="x" * 99999))
        assert set(e.value.errores) == {"objetivo", "reglas", "personalidad"}

    def test_llaves_sueltas_son_validas_porque_se_escapan(self):
        validar(_validas(reglas="usa {llaves} } { sueltas"))


def test_estimar_tokens_es_aproximado_pero_sube_con_el_largo():
    assert estimar_tokens("") == 0 and estimar_tokens("abcd") == 1 and estimar_tokens("abcde") == 2


def test_los_caracteres_fijos_mas_lo_editable_dan_el_largo_del_original():
    editable = sum(len(t) for t in secciones_originales().values())
    # El original mide lo mismo que lo fijo más sus cuerpos editables (los títulos y saltos ya están en lo fijo).
    assert caracteres_fijos() + editable == len(texto_original())


# ---------------------------------------------------------------------------------------------
# Lo que usa Victoria en cada mensaje
# ---------------------------------------------------------------------------------------------
class RepoFalso:
    def __init__(self, publicada=None):
        self.publicada_actual = publicada
        self.lecturas = 0
        self.falla = False

    def publicada(self):
        self.lecturas += 1
        if self.falla:
            raise RuntimeError("la base no responde")
        return self.publicada_actual


class Reloj:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


@pytest.fixture
def reloj():
    return Reloj()


def _vigentes(repo, reloj):
    return InstruccionesVigentes(repo=repo, reloj=reloj)


class TestInstruccionesVigentes:
    def test_sin_version_publicada_rige_el_archivo_original(self, reloj):
        assert _vigentes(RepoFalso(), reloj).plantilla() == texto_original()

    def test_con_version_publicada_rige_esa(self, reloj):
        repo = RepoFalso({"secciones": _validas(personalidad="Eres de Guayaquil.")})
        assert "Eres de Guayaquil." in _vigentes(repo, reloj).plantilla()

    def test_una_version_publicada_invalida_no_deja_a_victoria_sin_instrucciones(self, reloj, caplog):
        repo = RepoFalso({"secciones": {"personalidad": "solo una sección"}})
        assert _vigentes(repo, reloj).plantilla() == texto_original()
        assert "No se pudo leer la versión publicada" in caplog.text

    def test_si_la_base_falla_se_usa_el_original(self, reloj):
        repo = RepoFalso()
        repo.falla = True
        assert _vigentes(repo, reloj).plantilla() == texto_original()

    def test_si_la_base_falla_despues_se_conserva_lo_ultimo_que_funciono(self, reloj):
        repo = RepoFalso({"secciones": _validas(objetivo="Vender mucho.")})
        vigentes = _vigentes(repo, reloj)
        assert "Vender mucho." in vigentes.plantilla()
        repo.falla = True
        reloj.t += 31
        assert "Vender mucho." in vigentes.plantilla()

    def test_recuerda_treinta_segundos_y_reintenta_pronto_si_fallo(self, reloj):
        repo = RepoFalso()
        vigentes = _vigentes(repo, reloj)
        vigentes.plantilla()
        reloj.t += 29
        vigentes.plantilla()
        assert repo.lecturas == 1
        reloj.t += 2
        vigentes.plantilla()
        assert repo.lecturas == 2

        repo.falla = True
        reloj.t += 31
        vigentes.plantilla()
        lecturas = repo.lecturas
        reloj.t += 5  # no martilla la base
        vigentes.plantilla()
        assert repo.lecturas == lecturas
        reloj.t += 6
        vigentes.plantilla()
        assert repo.lecturas == lecturas + 1

    def test_invalidar_hace_que_un_cambio_se_note_al_instante(self, reloj):
        repo = RepoFalso()
        vigentes = _vigentes(repo, reloj)
        assert vigentes.plantilla() == texto_original()
        repo.publicada_actual = {"secciones": _validas(variantes="Sin variantes por ahora.")}
        assert vigentes.plantilla() == texto_original()  # todavía recuerda
        vigentes.invalidar()
        assert "Sin variantes por ahora." in vigentes.plantilla()
