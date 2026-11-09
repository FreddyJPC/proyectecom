"""
Sentido común para nombres mal escritos (lógica pura): ¿a cuál de las opciones oficiales se refiere el cliente?

Ejemplos: «quto» -> Quito, «guayakil» -> Guayaquil, «cuenka» -> Cuenca, «sto domingo» -> Santo Domingo, «negrp» -> Negro.

La regla es la de una persona sensata:
  - Si lo escrito se parece MUCHO a una sola opción (o suena igual), es esa: se corrige sin preguntarle nada al cliente
    (después, en el resumen que confirma, se verá bien escrito).
  - Si podría ser una de VARIAS, no se adivina: se le pregunta cuál.
  - Si no se parece a nada, no se inventa: se aclara con el cliente o se pasa a una persona.

Cómo se compara: se quitan mayúsculas, tildes y adornos («cantón», «ciudad de»…), se expanden abreviaturas («sto» -> santo)
y se mira tanto la escritura como cómo SUENA (k/c/qu, b/v, s/z/c, h muda, ll/y). Lo que suena igual y es único, es seguro.
"""
import difflib
import re
import unicodedata
from dataclasses import dataclass, field
from typing import List, Optional, Sequence

# Qué tan parecido debe ser para considerarlo (0 a 1).
_MINIMO = 0.7
_SEGURO_SI_ES_LA_UNICA = 0.75
_SEGURO_SI_DESTACA = 0.8
_VENTAJA_SOBRE_LA_SEGUNDA = 0.1
_MAXIMO_SUGERENCIAS = 3
# Textos muy cortos se confunden con cualquier cosa: ahí solo vale la coincidencia exacta o por sonido.
_LARGO_MINIMO_PARA_PARECIDO = 4
# Para la regla «una palabra contenida en la otra»: las letras que deben compartir (evita que «el» o «de» cuenten).
_LARGO_MINIMO_DE_LA_PALABRA_COMPARTIDA = 3

_ABREVIATURAS = {"sto": "santo", "sta": "santa", "pto": "puerto", "gral": "general", "cnel": "coronel", "dr": "doctor"}
_COMPLEMENTOS = {"sur", "norte", "centro", "este", "oeste", "valle", "ciudad", "canton"}
_ADORNOS = ("provincia de ", "provincia ", "canton ", "ciudad de ", "ciudad ", "parroquia ", "cdla ", "sector ")


def base(texto: Optional[str]) -> str:
    """'  Cantón QUITÓ. ' -> 'quito': minúsculas, sin tildes ni signos, sin adornos y con abreviaturas expandidas."""
    if not texto:
        return ""
    sin_tildes = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode("ascii").lower()
    limpio = re.sub(r"[^a-z0-9 ]", " ", sin_tildes)
    limpio = re.sub(r"\s+", " ", limpio).strip()
    for adorno in _ADORNOS:
        if limpio.startswith(adorno):
            limpio = limpio[len(adorno):]
    palabras = [_ABREVIATURAS.get(p, p) for p in limpio.split()]
    return " ".join(palabras)


def fonetica(texto: str) -> str:
    """Cómo suena en español, a grandes rasgos: 'guayaquil' y 'guayakil' dan lo mismo; 'quito' y 'kito' también."""
    s = base(texto)
    s = re.sub(r"qu", "k", s)
    s = s.replace("q", "k")
    s = re.sub(r"c(?=[ei])", "s", s)
    s = s.replace("c", "k")
    s = s.replace("z", "s").replace("v", "b").replace("w", "u").replace("h", "").replace("ll", "y")
    s = re.sub(r"(.)\1+", r"\1", s)
    return s


def parecido(a: str, b: str) -> float:
    ba, bb = base(a), base(b)
    escrito = difflib.SequenceMatcher(None, ba, bb).ratio()
    sonido = difflib.SequenceMatcher(None, fonetica(a), fonetica(b)).ratio()
    return max(escrito, sonido)


@dataclass
class Coincidencia:
    oficial: Optional[str] = None  # la opción a la que se refiere, si es seguro
    parecidas: List[str] = field(default_factory=list)  # si no es seguro: las más parecidas (de la más a la menos)
    exacta: bool = False  # el texto ya era el nombre oficial (salvo mayúsculas/tildes)

    @property
    def segura(self) -> bool:
        return self.oficial is not None


def buscar(texto: Optional[str], opciones: Sequence[str]) -> Coincidencia:
    """¿A qué opción se refiere `texto`? Ver la regla en el encabezado del módulo."""
    objetivo = base(texto)
    if not objetivo or not opciones:
        return Coincidencia()

    exactas = [o for o in opciones if base(o) == objetivo]
    if exactas:
        return Coincidencia(oficial=exactas[0], exacta=True)

    sonido = fonetica(objetivo)
    iguales_de_sonido = {o for o in opciones if fonetica(o) == sonido}
    if len(iguales_de_sonido) == 1:
        return Coincidencia(oficial=next(iter(iguales_de_sonido)))

    # «coca» dentro de «El Coca», «Zamora» dentro de «Zamora Chinchipe»: el cliente dijo MENOS que el nombre oficial y solo
    # hay una opción así. También «Quito sur»: lo que sobra es un complemento sin importancia («sur», «centro»…).
    palabras = set(objetivo.split())
    incluidas = []
    for o in opciones:
        de_la_opcion = set(base(o).split())
        compartidas = sum(len(w) for w in (palabras & de_la_opcion))
        if compartidas < _LARGO_MINIMO_DE_LA_PALABRA_COMPARTIDA:
            continue
        if palabras <= de_la_opcion or (de_la_opcion <= palabras and (palabras - de_la_opcion) <= _COMPLEMENTOS):
            incluidas.append(o)
    if len(incluidas) == 1:
        return Coincidencia(oficial=incluidas[0])

    if len(objetivo) < _LARGO_MINIMO_PARA_PARECIDO:
        return Coincidencia(parecidas=sorted(iguales_de_sonido)[:_MAXIMO_SUGERENCIAS])

    puntuadas = sorted(((parecido(objetivo, o), o) for o in opciones), key=lambda x: (-x[0], x[1]))
    candidatas = [(p, o) for p, o in puntuadas if p >= _MINIMO]
    if not candidatas:
        return Coincidencia()
    mejor, segunda = candidatas[0][0], (candidatas[1][0] if len(candidatas) > 1 else 0.0)
    # Las palabras de 4 letras o menos se parecen a demasiadas cosas: ahí se pide más parecido.
    exigencia = 0.0 if len(objetivo) >= _LARGO_MINIMO_PARA_PARECIDO + 1 else 0.85
    unica = len(candidatas) == 1 and mejor >= max(_SEGURO_SI_ES_LA_UNICA, exigencia)
    destaca = mejor >= max(_SEGURO_SI_DESTACA, exigencia) and (mejor - segunda) >= _VENTAJA_SOBRE_LA_SEGUNDA
    if unica or destaca:
        return Coincidencia(oficial=candidatas[0][1])
    return Coincidencia(parecidas=[o for _, o in candidatas[:_MAXIMO_SUGERENCIAS]])
