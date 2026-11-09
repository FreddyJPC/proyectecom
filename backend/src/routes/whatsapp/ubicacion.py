"""
Revisión del cantón y la provincia que el cliente dice, ANTES de guardarlos (lógica pura, sin base de datos).

Por qué existe: la gente escribe «kito», «guayakil», «Sto. Domingo» o «cuenka». Rocketfy solo acepta los nombres
exactos de su catálogo (ignora mayúsculas y tildes, pero no corrige nada), así que una ciudad mal escrita no se notaba
hasta el cierre de la venta, cuando el pedido fallaba y la conversación pasaba a una persona después de que el
cliente ya había dado todos sus datos. Ahora se revisa en cuanto el cliente la dice:

  - Si coincide con el catálogo (aunque cambien mayúsculas o tildes) se guarda con el nombre OFICIAL.
  - Si no coincide pero se parece a algo, NO se guarda: se le dan a Victoria las sugerencias para que le pregunte al
    cliente «¿quiso decir Quito, Pichincha?». El sistema nunca corrige solo un error de ortografía: la última palabra
    la tiene el cliente.
  - Si no se parece a nada, tampoco se guarda y se le pide al cliente que lo aclare.

En un producto de cierre manual (lo gestiona el dueño, no Rocketfy) el lugar puede no estar en el catálogo: ahí lo
que el cliente dijo se guarda tal cual y solo se avisa si hay un nombre parecido.
"""
import difflib
from dataclasses import dataclass, field
from typing import List, Optional

from src.catalogs.ecuador_locations import EcuadorLocationsCatalog, _normalizar

# Qué tan parecido debe ser un nombre del catálogo para sugerirlo (0 a 1). Probado con «kito», «guayakil», «cuenka»,
# «pichinca», «latakunga»: todos superan 0.6 y los nombres sin relación no.
_PARECIDO_MINIMO = 0.6
_MAXIMO_SUGERENCIAS = 3


@dataclass
class RevisionDeUbicacion:
    canton: Optional[str] = None  # lo que se puede guardar (nombre oficial); None = no guardar
    provincia: Optional[str] = None
    mensaje: str = ""  # para Victoria; vacío = todo bien
    nota: str = ""  # información, no un problema (p. ej. se completó la provincia)
    sugerencias: List[str] = field(default_factory=list)

    @property
    def hay_problema(self) -> bool:
        return bool(self.mensaje)


def _parecidos(texto: str, opciones: List[str]) -> List[str]:
    por_normal = {_normalizar(o): o for o in opciones}
    cercanos = difflib.get_close_matches(_normalizar(texto), list(por_normal), n=_MAXIMO_SUGERENCIAS, cutoff=_PARECIDO_MINIMO)
    return [por_normal[c] for c in cercanos]


def _provincia_oficial(catalogo: EcuadorLocationsCatalog, provincia: str) -> Optional[str]:
    objetivo = _normalizar(provincia)
    for oficial in catalogo.listar_provincias():
        if _normalizar(oficial) == objetivo:
            return oficial
    return None


def _provincias_con_canton(catalogo: EcuadorLocationsCatalog, canton: str) -> List[str]:
    objetivo = _normalizar(canton)
    return [p for p in catalogo.listar_provincias() if any(_normalizar(c) == objetivo for c in catalogo.listar_cantones(p))]


def revisar_ubicacion(
    catalogo: EcuadorLocationsCatalog, canton: Optional[str], provincia: Optional[str]
) -> RevisionDeUbicacion:
    """`canton` y `provincia` son los valores que quedarían guardados (lo nuevo que dijo el cliente combinado con lo que
    ya se sabía). Devuelve qué se puede guardar y, si algo no cuadra, qué decirle a Victoria."""
    canton = (canton or "").strip() or None
    provincia = (provincia or "").strip() or None
    if canton is None and provincia is None:
        return RevisionDeUbicacion()

    # Los dos y coinciden con el catálogo.
    if canton and provincia:
        encontrado = catalogo.resolver(provincia, canton)
        if encontrado is not None:
            return RevisionDeUbicacion(canton=nombre_para_mostrar(encontrado.canton), provincia=encontrado.provincia)

    provincia_oficial = _provincia_oficial(catalogo, provincia) if provincia else None

    # La provincia está mal escrita (o no existe).
    if provincia and provincia_oficial is None:
        sugeridas = _parecidos(provincia, catalogo.listar_provincias())
        if sugeridas:
            return RevisionDeUbicacion(
                mensaje=(
                    f"No encontré la provincia «{provincia}». ¿Será {_o(sugeridas)}? Pregúntaselo al cliente para "
                    "confirmarlo; todavía no se guardó la provincia."
                ),
                sugerencias=sugeridas,
            )
        return RevisionDeUbicacion(
            mensaje=f"No encontré la provincia «{provincia}» en el catálogo de entregas. Pídele al cliente que te diga su provincia otra vez."
        )

    # Hay provincia válida: se revisa el cantón dentro de ella.
    if provincia_oficial and canton:
        cantones = catalogo.listar_cantones(provincia_oficial)
        sugeridos = _parecidos(canton, cantones)
        if sugeridos:
            return RevisionDeUbicacion(
                provincia=provincia_oficial,
                mensaje=(
                    f"No encontré el cantón «{canton}» en {provincia_oficial}. ¿Será {_o(sugeridos)}? Pregúntaselo al "
                    "cliente para confirmarlo; todavía no se guardó el cantón."
                ),
                sugerencias=sugeridos,
            )
        otras = _provincias_con_canton(catalogo, canton)
        if otras:
            return RevisionDeUbicacion(
                provincia=provincia_oficial,
                mensaje=(
                    f"«{canton}» no está en {provincia_oficial}; sí existe en {_y(otras)}. Aclara con el cliente de qué "
                    "provincia es; todavía no se guardó el cantón."
                ),
                sugerencias=otras,
            )
        return RevisionDeUbicacion(
            provincia=provincia_oficial,
            mensaje=(
                f"No encontré el cantón «{canton}» en {provincia_oficial}. Pídele al cliente que te diga el cantón (la "
                "ciudad) de entrega otra vez; todavía no se guardó."
            ),
        )

    # Solo provincia válida (falta el cantón): se guarda.
    if provincia_oficial:
        return RevisionDeUbicacion(provincia=provincia_oficial)

    # Solo cantón, sin provincia: si el nombre existe en una sola provincia, se completa (Quito solo puede ser de Pichincha).
    if canton:
        provincias = _provincias_con_canton(catalogo, canton)
        if len(provincias) == 1:
            encontrado = catalogo.resolver(provincias[0], canton)
            nombre = nombre_para_mostrar(encontrado.canton)
            return RevisionDeUbicacion(
                canton=nombre,
                provincia=encontrado.provincia,
                nota=f"{nombre} está en la provincia {encontrado.provincia}: se guardaron las dos.",
            )
        if len(provincias) > 1:
            return RevisionDeUbicacion(
                mensaje=f"«{canton}» existe en varias provincias ({_y(provincias)}). Pregúntale al cliente de cuál es.",
                sugerencias=provincias,
            )
        sugeridos = _parecidos(canton, sorted({c for p in catalogo.listar_provincias() for c in catalogo.listar_cantones(p)}))
        if sugeridos:
            return RevisionDeUbicacion(
                mensaje=f"No encontré el cantón «{canton}». ¿Será {_o(sugeridos)}? Pregúntaselo al cliente para confirmarlo; todavía no se guardó.",
                sugerencias=sugeridos,
            )
        return RevisionDeUbicacion(
            mensaje=(
                f"No encontré el cantón «{canton}». Pregúntale al cliente su provincia y su ciudad otra vez y guárdalos juntos."
            )
        )
    return RevisionDeUbicacion()


def _o(opciones: List[str]) -> str:
    return " o ".join(f"«{o.title() if o.isupper() else o}»" for o in opciones)


def _y(opciones: List[str]) -> str:
    return ", ".join(opciones)


def nombre_para_mostrar(texto: Optional[str]) -> str:
    """Para mostrarle al cliente: el catálogo guarda los cantones en MAYÚSCULAS («QUITO»)."""
    if not texto:
        return ""
    return texto.title() if texto.isupper() else texto
