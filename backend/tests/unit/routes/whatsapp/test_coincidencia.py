"""El motor de «sentido común» para nombres mal escritos (lógica pura)."""
import pytest

from src.routes.whatsapp.coincidencia import base, buscar, fonetica

CIUDADES = ["QUITO", "GUAYAQUIL", "CUENCA", "SANTO DOMINGO", "EL COCA", "SAN SEBASTIAN DEL COCA", "AMBATO", "AMBATILLO"]


class TestBase:
    @pytest.mark.parametrize("texto, esperado", [
        ("  Cantón QUITÓ. ", "quito"), ("Ciudad de Cuenca", "cuenca"), ("sto. domingo", "santo domingo"),
        ("Provincia de Pichincha", "pichincha"), ("pto lopez", "puerto lopez"),
    ])
    def test_normaliza(self, texto, esperado):
        assert base(texto) == esperado

    def test_suena_igual(self):
        assert fonetica("quito") == fonetica("kito") and fonetica("guayaquil") == fonetica("guayakil")
        assert fonetica("cuenca") == fonetica("cuenka") and fonetica("vaca") == fonetica("baca")


class TestBuscar:
    @pytest.mark.parametrize("escrito, oficial", [
        ("quito", "QUITO"), ("QUTO", "QUITO"), ("kito", "QUITO"), ("guayakil", "GUAYAQUIL"), ("guayaquill", "GUAYAQUIL"),
        ("cuenka", "CUENCA"), ("sto domingo", "SANTO DOMINGO"), ("anbato", "AMBATO"), ("quito sur", "QUITO"),
    ])
    def test_lo_evidente_es_seguro(self, escrito, oficial):
        assert buscar(escrito, CIUDADES).oficial == oficial

    def test_exacta_se_marca(self):
        assert buscar("Cuenca", CIUDADES).exacta is True and buscar("cuenka", CIUDADES).exacta is False

    def test_si_podria_ser_una_de_varias_no_se_adivina(self):
        m = buscar("coca", CIUDADES)  # «El Coca» o «San Sebastián del Coca»
        assert not m.segura

    def test_si_no_se_parece_a_nada_no_se_inventa(self):
        m = buscar("xyzxyz", CIUDADES)
        assert not m.segura and m.parecidas == []

    def test_textos_muy_cortos_no_se_confunden_con_cualquier_cosa(self):
        assert not buscar("ab", CIUDADES).segura

    def test_sin_texto_o_sin_opciones(self):
        assert not buscar("", CIUDADES).segura and not buscar("quito", []).segura and not buscar(None, CIUDADES).segura


class TestConErroresAlAzar:
    """Prueba de estrés con el catálogo REAL: errores de escritura automáticos sobre los 832 cantones. Lo que importa: casi
    todo se corrige bien y NUNCA se «corrige» a otro lugar; lo dudoso se pregunta."""

    @staticmethod
    def _mutar(nombre, azar):
        n = nombre.lower()
        tipo = azar.choice(["borrar", "cambiar", "intercambiar", "duplicar", "k"])
        i = azar.randrange(1, len(n) - 1)
        if tipo == "borrar":
            return n[:i] + n[i + 1:]
        if tipo == "cambiar":
            return n[:i] + azar.choice("aeiounrst") + n[i + 1:]
        if tipo == "intercambiar":
            return n[:i] + n[i + 1] + n[i] + n[i + 2:]
        if tipo == "duplicar":
            return n[:i] + n[i] + n[i:]
        return n.replace("qu", "k").replace("c", "k", 1)

    def test_corrige_casi_todo_y_nunca_se_equivoca_de_lugar(self):
        import random

        from src.catalogs.ecuador_locations import get_catalog

        azar = random.Random(7)
        catalogo = get_catalog()
        total = bien = mal = 0
        for provincia in catalogo.listar_provincias():
            cantones = catalogo.listar_cantones(provincia)
            for oficial in cantones:
                if len(base(oficial)) < 5:
                    continue
                for _ in range(3):
                    escrito = self._mutar(oficial, azar)
                    total += 1
                    m = buscar(escrito, cantones)
                    if m.segura:
                        if m.oficial == oficial or base(m.oficial) == base(escrito):
                            bien += 1
                        else:
                            mal += 1
        assert mal == 0, f"{mal} de {total} se corrigieron a OTRO lugar"
        assert bien / total >= 0.9, f"solo {bien} de {total} se corrigieron bien"
