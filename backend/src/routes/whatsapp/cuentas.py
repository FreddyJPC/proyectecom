"""
Qué cuenta le da Victoria al cliente que va a pagar por transferencia (lógica pura, sin base de datos).

Reglas (pedidas por Freddy, pendiente #76):
  - Victoria PRIMERO pregunta desde qué banco va a transferir el cliente. Si el dueño tiene cuenta en ese banco, esa es la que se da
    (una transferencia entre cuentas del mismo banco suele ser inmediata y sin comisión).
  - El cliente escribe como puede («Bano Pichncha», «pichincha», «el guayaquil»): el nombre se compara sin tildes ni «banco»/
    «cooperativa» y con tolerancia a faltas (`coincidencia.py`, la misma que corrige las ciudades).
  - Si el banco que dice no está entre los registrados, no se inventa nada: se le dice que por ahora no hay cuenta ahí y se le ofrecen
    los bancos que sí hay, para que elija uno (o no: entonces la venta sigue por otro camino).
  - El texto con los datos lo arma el CÓDIGO desde la tabla: Victoria lo manda tal cual y nunca escribe un número de cuenta.
"""
import difflib
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, List, Optional

from .coincidencia import base, buscar

_ARTICULOS = {"el", "la", "los", "las", "del", "de", "mi", "un", "una"}
_PALABRAS_DE_ENTIDAD = ("banco", "bco", "cooperativa", "coop", "coac")


def _es_palabra_de_entidad(palabra: str) -> bool:
    """«banco», «bco», «cooperativa»… y sus faltas («bano»): no identifican al banco, solo dicen que es uno."""
    return palabra in _PALABRAS_DE_ENTIDAD or any(
        difflib.SequenceMatcher(None, palabra, entidad).ratio() >= 0.8 for entidad in ("banco", "cooperativa")
    )


def nombre_corto(texto: Optional[str]) -> str:
    """'Banco del Pichincha' -> 'pichincha'; 'Bano Pichncha' -> 'pichncha'; 'la JEP' -> 'jep': lo que identifica al banco."""
    palabras = base(texto).split()
    while len(palabras) > 1 and palabras[0] in _ARTICULOS:
        palabras.pop(0)
    if len(palabras) > 1 and _es_palabra_de_entidad(palabras[0]):
        palabras.pop(0)
        while len(palabras) > 1 and palabras[0] in _ARTICULOS:
            palabras.pop(0)
        if palabras[:3] == ["ahorro", "y", "credito"] and len(palabras) > 3:  # «cooperativa de ahorro y crédito JEP»
            palabras = palabras[3:]
    return " ".join(palabras)


@dataclass
class EleccionDeBanco:
    cuentas: List[Dict[str, Any]] = field(default_factory=list)  # las cuentas de ese banco, si se reconoció uno
    parecidos: List[str] = field(default_factory=list)  # si podría ser uno de varios: sus nombres para preguntar

    @property
    def reconocido(self) -> bool:
        return bool(self.cuentas)


def bancos_registrados(cuentas: List[Dict[str, Any]]) -> List[str]:
    """Los nombres de banco con cuenta activa, sin repetir y en el orden de las cuentas."""
    vistos: List[str] = []
    for cuenta in cuentas:
        if cuenta["banco"] not in vistos:
            vistos.append(cuenta["banco"])
    return vistos


def elegir_banco(dicho: Optional[str], cuentas: List[Dict[str, Any]]) -> EleccionDeBanco:
    """¿A cuál de los bancos con cuenta se refiere el cliente? Nada reconocido -> `EleccionDeBanco()` vacío."""
    objetivo = nombre_corto(dicho)
    if not objetivo or not cuentas:
        return EleccionDeBanco()
    por_nombre: Dict[str, str] = {}  # nombre corto -> nombre oficial del banco
    for banco in bancos_registrados(cuentas):
        por_nombre.setdefault(nombre_corto(banco), banco)
    resultado = buscar(objetivo, list(por_nombre))
    if resultado.segura:
        oficial = por_nombre[resultado.oficial]
        return EleccionDeBanco(cuentas=[c for c in cuentas if c["banco"] == oficial])
    # Un pedazo del nombre («pich», «guay»): vale si empieza solo UNO de los bancos registrados.
    if not resultado.parecidas and len(objetivo) >= 4:
        empiezan = [n for n in por_nombre if n.startswith(objetivo)]
        if len(empiezan) == 1:
            oficial = por_nombre[empiezan[0]]
            return EleccionDeBanco(cuentas=[c for c in cuentas if c["banco"] == oficial])
    return EleccionDeBanco(parecidos=[por_nombre[p] for p in resultado.parecidas])


def _dinero(valor: Any) -> Optional[str]:
    try:
        return f"{Decimal(str(valor)).quantize(Decimal('0.01'))}"
    except Exception:
        return None


def texto_de_cuentas(cuentas: List[Dict[str, Any]], total: Any = None) -> str:
    """El mensaje que se le manda al cliente con los datos para transferir. Lo escribe el código, no la IA."""
    bloques = []
    for c in cuentas:
        lineas = [f"🏦 {c['banco']}", f"Tipo de cuenta: {c['tipo_cuenta']}", f"Número: {c['numero']}", f"Titular: {c['titular']}"]
        if c.get("identificacion"):
            lineas.append(f"Cédula: {c['identificacion']}")
        bloques.append("\n".join(lineas))
    partes = ["Estos son los datos para su transferencia:", "\n\n".join(bloques)]
    monto = _dinero(total) if total is not None else None
    if monto:
        partes.append(f"Valor a transferir: ${monto}")
    partes.append("Cuando la haga, envíeme por favor la foto del comprobante 🙏")
    return "\n\n".join(partes)


def _lista(nombres: List[str]) -> str:
    if len(nombres) <= 1:
        return "".join(nombres)
    return ", ".join(nombres[:-1]) + " o " + nombres[-1]


def respuesta_para_victoria(dicho: Optional[str], cualquiera: bool, cuentas: List[Dict[str, Any]], total: Any = None) -> str:
    """Lo que le devuelve la herramienta a Victoria: qué decirle al cliente y cuál es el siguiente paso."""
    if not cuentas:
        return (
            "Por ahora no hay cuentas para transferir configuradas. No inventes ninguna: dile al cliente con amabilidad que un asesor le "
            "pasa los datos y usa escalar_a_humano."
        )
    if cualquiera:
        # «Cualquiera»: la cuenta principal (la de menor orden), con todas las cuentas de ese mismo banco.
        principal = cuentas[0]["banco"]
        return _enviar([c for c in cuentas if c["banco"] == principal], total)
    if not (dicho or "").strip():
        return (
            "Antes de pasarle la cuenta, pregúntale al cliente desde qué banco va a transferir (una sola pregunta corta). Si tenemos "
            "cuenta en ese banco, se la damos. Cuando responda, vuelve a usar esta herramienta con ese banco."
        )
    eleccion = elegir_banco(dicho, cuentas)
    if eleccion.reconocido:
        return _enviar(eleccion.cuentas, total)
    if eleccion.parecidos:
        return (
            f"«{dicho}» puede ser {_lista([f'«{p}»' for p in eleccion.parecidos])}. Pregúntale al cliente a cuál se refiere y vuelve a "
            "usar esta herramienta con su respuesta."
        )
    nuestros = _lista(bancos_registrados(cuentas))
    return (
        f"No tenemos cuenta en «{dicho}». Dile al cliente con amabilidad que por el momento no contamos con cuenta en ese banco, pero que "
        f"podemos ayudarle pasándole una cuenta de {nuestros}, y pregúntale si desea alguna de esas. Si elige una, vuelve a usar esta "
        "herramienta con ese banco; si dice que cualquiera, úsala con cualquiera=true; si prefiere no transferir, sigue con la "
        "conversación (por ejemplo, ofrece contraentrega si el producto la acepta). No inventes datos de ninguna cuenta."
    )


def _enviar(elegidas: List[Dict[str, Any]], total: Any) -> str:
    return (
        "Envíale al cliente este mensaje TAL CUAL, sin cambiar ni un dígito (puedes agregar un saludo breve antes) y espera su "
        f"comprobante. Si dice que ya transfirió, pídele la foto del comprobante.\n\n{texto_de_cuentas(elegidas, total)}"
    )
