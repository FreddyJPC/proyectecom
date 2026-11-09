"""
Revisión del cantón y la provincia que el cliente dice, ANTES de guardarlos (lógica pura, sin base de datos).

Por qué existe: la gente escribe «quto», «guayakil», «Sto. Domingo» o «cuenka». Rocketfy solo acepta los nombres exactos de su
catálogo, así que una ciudad mal escrita no se notaba hasta el cierre de la venta, cuando el pedido fallaba y la conversación
pasaba a una persona. Ahora se resuelve en cuanto el cliente la dice, con sentido común (ver `coincidencia.py`):

  - Lo evidente se corrige SIN preguntar: «quto» es Quito; se guarda «Quito, Pichincha» y el cliente lo ve bien escrito en el
    resumen que confirma. Si dice «Guayaquil» sin provincia, la provincia es Guayas. No se le pregunta lo que ya se sabe.
  - Si podría ser una de varias («San Pedro»…) se le pregunta cuál: no se adivina.
  - Si no cuadra («Guayaquil, Pichincha») se aclara con el cliente.
  - Si no se parece a nada, no se inventa nada: se le pide que lo repita y, si no se aclara, se pasa a una persona.

En un producto de cierre manual (lo gestiona el dueño, no Rocketfy) el lugar puede no estar en el catálogo: ahí lo que dijo el
cliente se guarda tal cual y solo se avisa si hay un nombre parecido.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from src.catalogs.ecuador_locations import EcuadorLocationsCatalog

from .coincidencia import base, buscar

_SI_NO_SE_ACLARA = "Si después de dos intentos no se aclara, no supongas ni inventes: usa escalar_a_humano."


@dataclass
class RevisionDeUbicacion:
    canton: Optional[str] = None  # lo que se puede guardar (nombre oficial); None = no guardar
    provincia: Optional[str] = None
    mensaje: str = ""  # un problema para Victoria (hay que aclarar algo con el cliente); vacío = todo bien
    nota: str = ""  # información, no un problema (p. ej. se corrigió un error de ortografía)
    sugerencias: List[str] = field(default_factory=list)

    @property
    def hay_problema(self) -> bool:
        return bool(self.mensaje)


def nombre_para_mostrar(texto: Optional[str]) -> str:
    """Para mostrarle al cliente: el catálogo guarda los cantones en MAYÚSCULAS («QUITO»)."""
    if not texto:
        return ""
    return texto.title() if texto.isupper() else texto


def _o(opciones: List[str]) -> str:
    return " o ".join(f"«{nombre_para_mostrar(o)}»" for o in opciones)


def _cantones_por_provincia(catalogo: EcuadorLocationsCatalog) -> Dict[str, List[str]]:
    return {p: catalogo.listar_cantones(p) for p in catalogo.listar_provincias()}


def _provincias_de(por_provincia: Dict[str, List[str]], canton_oficial: str) -> List[str]:
    return [p for p, cantones in por_provincia.items() if canton_oficial in cantones]


def _nota_si_cambio(escrito: str, oficial: str) -> str:
    return f"«{escrito}» -> «{nombre_para_mostrar(oficial)}»" if base(escrito) != base(oficial) else ""


def revisar_ubicacion(
    catalogo: EcuadorLocationsCatalog, canton: Optional[str], provincia: Optional[str]
) -> RevisionDeUbicacion:
    """`canton` y `provincia` son los valores que quedarían guardados (lo nuevo que dijo el cliente combinado con lo que ya se
    sabía). Devuelve qué se puede guardar y, si algo no cuadra, qué aclarar con el cliente."""
    canton = (canton or "").strip() or None
    provincia = (provincia or "").strip() or None
    # «Quito, Pichincha» en el campo del cantón: lo de después de la coma es la provincia.
    if canton and "," in canton:
        canton, _, resto = canton.partition(",")
        canton = canton.strip() or None
        if not provincia and resto.strip():
            provincia = resto.strip()
    if canton is None and provincia is None:
        return RevisionDeUbicacion()

    por_provincia = _cantones_por_provincia(catalogo)
    correcciones: List[str] = []

    # --- La provincia
    provincia_oficial: Optional[str] = None
    if provincia:
        m = buscar(provincia, list(por_provincia))
        if m.segura:
            provincia_oficial = m.oficial
            if (c := _nota_si_cambio(provincia, m.oficial)):
                correcciones.append(c)
        elif m.parecidas:
            return RevisionDeUbicacion(
                mensaje=(
                    f"La provincia «{provincia}» puede ser {_o(m.parecidas)}. Pregúntale al cliente cuál es; todavía no se "
                    f"guardó. {_SI_NO_SE_ACLARA}"
                ),
                sugerencias=m.parecidas,
            )
        else:
            return RevisionDeUbicacion(
                mensaje=f"No encontré la provincia «{provincia}». Pídele al cliente que te la diga otra vez. {_SI_NO_SE_ACLARA}"
            )

    if not canton:
        return RevisionDeUbicacion(provincia=provincia_oficial, nota=_armar_nota(correcciones))

    # --- El cantón, dentro de su provincia
    if provincia_oficial:
        m = buscar(canton, por_provincia[provincia_oficial])
        if m.segura:
            if (c := _nota_si_cambio(canton, m.oficial)):
                correcciones.append(c)
            return RevisionDeUbicacion(
                canton=nombre_para_mostrar(m.oficial), provincia=provincia_oficial, nota=_armar_nota(correcciones)
            )
        # No está claro dentro de esa provincia. Antes de sugerir nombres parecidos de aquí, ¿es un lugar conocido de OTRA
        # provincia? Entonces no cuadra («Guayaquil» en Pichincha) y se aclara con el cliente; no se le ofrece cualquier cosa.
        en_todo_el_pais = sorted({c for cantones in por_provincia.values() for c in cantones})
        otra = buscar(canton, en_todo_el_pais)
        if otra.segura:
            provincias = _provincias_de(por_provincia, otra.oficial)
            return RevisionDeUbicacion(
                provincia=provincia_oficial,
                mensaje=(
                    f"No cuadra: {nombre_para_mostrar(otra.oficial)} está en {', '.join(provincias)}, no en "
                    f"{provincia_oficial}. Pregúntale al cliente cuál es la ciudad y la provincia correctas; todavía no se "
                    f"guardó el cantón. {_SI_NO_SE_ACLARA}"
                ),
                sugerencias=provincias,
            )
        if m.parecidas:
            return RevisionDeUbicacion(
                provincia=provincia_oficial,
                mensaje=(
                    f"El cantón «{canton}» puede ser {_o(m.parecidas)} (en {provincia_oficial}). Pregúntale al cliente "
                    f"cuál es; todavía no se guardó el cantón. {_SI_NO_SE_ACLARA}"
                ),
                sugerencias=m.parecidas,
            )
        return RevisionDeUbicacion(
            provincia=provincia_oficial,
            mensaje=(
                f"No encontré el cantón «{canton}» en {provincia_oficial}. Pídele al cliente que te diga la ciudad de entrega "
                f"otra vez; todavía no se guardó. {_SI_NO_SE_ACLARA}"
            ),
        )

    # --- Solo el cantón, sin provincia: si es de una sola provincia, la provincia se sabe (Guayaquil -> Guayas)
    en_todo_el_pais = sorted({c for cantones in por_provincia.values() for c in cantones})
    m = buscar(canton, en_todo_el_pais)
    if m.segura:
        provincias = _provincias_de(por_provincia, m.oficial)
        if len(provincias) == 1:
            if (c := _nota_si_cambio(canton, m.oficial)):
                correcciones.append(c)
            nota = _armar_nota(correcciones, completo=f"{nombre_para_mostrar(m.oficial)}, {provincias[0]}")
            return RevisionDeUbicacion(canton=nombre_para_mostrar(m.oficial), provincia=provincias[0], nota=nota)
        return RevisionDeUbicacion(
            mensaje=(
                f"{nombre_para_mostrar(m.oficial)} existe en varias provincias ({', '.join(provincias)}). Pregúntale al "
                f"cliente de cuál es; todavía no se guardó. {_SI_NO_SE_ACLARA}"
            ),
            sugerencias=provincias,
        )
    if m.parecidas:
        return RevisionDeUbicacion(
            mensaje=(
                f"El cantón «{canton}» puede ser {_o(m.parecidas)}. Pregúntale al cliente cuál es; todavía no se guardó. "
                f"{_SI_NO_SE_ACLARA}"
            ),
            sugerencias=m.parecidas,
        )
    return RevisionDeUbicacion(
        mensaje=(
            f"No encontré el cantón «{canton}». Pregúntale al cliente su ciudad y su provincia otra vez. {_SI_NO_SE_ACLARA}"
        )
    )


def _armar_nota(correcciones: List[str], completo: str = "") -> str:
    partes = []
    if completo:
        partes.append(f"Se guardó {completo}.")
    if correcciones:
        partes.append(
            "Se corrigió la ortografía (" + "; ".join(correcciones) + "): no hace falta preguntarle, el cliente verá el "
            "nombre bien escrito en el resumen que va a confirmar."
        )
    return " ".join(partes)
