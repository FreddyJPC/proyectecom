"""
Reglas de las opciones de entrega de un producto (ADR-012). Lógica PURA, sin base
de datos ni red: se prueba con diccionarios (tests/unit/routes/entregas/).

Cada producto tiene sus propias opciones: un envío dentro de Cuenca por $2, un retiro
en una dirección, un envío al resto del país por $5… Los productos de Rocketfy suelen
tener «envío incluido en el precio» y ninguna opción.

Cómo se decide qué opciones se le ofrecen a un cliente:
  - Un RETIRO se ofrece a cualquiera.
  - Un ENVÍO con cobertura explícita (cantones y/o provincias) solo si el destino del
    cliente está en esa lista.
  - Un ENVÍO «al resto del país» solo si NINGÚN envío con cobertura explícita cubre el
    destino (así «Cuenca $2» y «resto del país $5» no se ofrecen juntos a alguien de Cuenca).

El dinero es siempre `Decimal` (nunca float).
"""
import re
import unicodedata
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

TIPOS = ("envio", "retiro")
MAXIMO_OPCIONES_POR_PRODUCTO = 12
LARGO_MAXIMO_TEXTO = 200
CENTAVO = Decimal("0.01")

_PREFIJOS_DE_CANTON = ("canton ", "ciudad de ", "ciudad ", "parroquia ")


def normalizar(texto: Optional[str]) -> str:
    """'  Cantón CUENCA ' -> 'cuenca': sin tildes, minúsculas y sin prefijos como «cantón»."""
    if not texto:
        return ""
    sin_tildes = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode("ascii")
    limpio = re.sub(r"\s+", " ", sin_tildes.strip().lower())
    for prefijo in _PREFIJOS_DE_CANTON:
        if limpio.startswith(prefijo):
            limpio = limpio[len(prefijo):]
    return limpio.strip()


def dinero(valor: Any) -> Decimal:
    return Decimal(str(valor)).quantize(CENTAVO, rounding=ROUND_HALF_UP)


def _lista_normalizada(valores) -> List[str]:
    return [normalizar(v) for v in (valores or []) if normalizar(v)]


def tiene_cobertura_explicita(opcion: Dict[str, Any]) -> bool:
    return bool(_lista_normalizada(opcion.get("cantones")) or _lista_normalizada(opcion.get("provincias")))


def cubre_destino(opcion: Dict[str, Any], canton: Optional[str], provincia: Optional[str]) -> bool:
    """¿La cobertura EXPLÍCITA de este envío incluye el destino?"""
    cantones = _lista_normalizada(opcion.get("cantones"))
    provincias = _lista_normalizada(opcion.get("provincias"))
    if cantones and normalizar(canton) in cantones:
        return True
    return bool(provincias) and normalizar(provincia) in provincias


def opciones_aplicables(
    opciones: List[Dict[str, Any]], canton: Optional[str], provincia: Optional[str]
) -> List[Dict[str, Any]]:
    """Las opciones ACTIVAS que se le pueden ofrecer a un cliente de ese destino, en el
    orden en que el dueño las ordenó."""
    activas = [o for o in opciones if o.get("activo", True)]
    con_cobertura = [o for o in activas if o["tipo"] == "envio" and tiene_cobertura_explicita(o)]
    destino_cubierto = any(cubre_destino(o, canton, provincia) for o in con_cobertura)

    resultado = []
    for opcion in activas:
        if opcion["tipo"] == "retiro":
            resultado.append(opcion)
        elif tiene_cobertura_explicita(opcion):
            if cubre_destino(opcion, canton, provincia):
                resultado.append(opcion)
        elif opcion.get("resto_del_pais") and not destino_cubierto:
            resultado.append(opcion)
    return resultado


def elegir_opcion(opciones: List[Dict[str, Any]], texto: Optional[str]) -> Optional[Dict[str, Any]]:
    """Encuentra la opción que quiso decir Victoria: por número de lista («1»), por id, por
    nombre exacto o por una parte del nombre que sea única. Devuelve None si es ambiguo o no existe."""
    consulta = normalizar(texto)
    if not consulta:
        return None
    if consulta.isdigit():
        posicion = int(consulta)
        if 1 <= posicion <= len(opciones):
            return opciones[posicion - 1]
        for opcion in opciones:
            if str(opcion.get("id")) == consulta:
                return opcion
        return None
    exactas = [o for o in opciones if normalizar(o["nombre"]) == consulta]
    if len(exactas) == 1:
        return exactas[0]
    parciales = [o for o in opciones if consulta in normalizar(o["nombre"]) or normalizar(o["nombre"]) in consulta]
    return parciales[0] if len(parciales) == 1 else None


def total_con_envio(subtotal: Any, opcion: Optional[Dict[str, Any]]) -> Decimal:
    extra = dinero(opcion["costo_cliente"]) if opcion else Decimal("0.00")
    return dinero(subtotal) + extra


def describir(opcion: Dict[str, Any], con_numero: Optional[int] = None) -> str:
    """Una línea que Victoria lee: «1) Envío en Cuenca: $2.00 · llega en 1 día»."""
    partes = [f"{opcion['nombre']}: ${dinero(opcion['costo_cliente'])}" if dinero(opcion["costo_cliente"]) > 0 else f"{opcion['nombre']}: sin costo"]
    if opcion["tipo"] == "retiro" and opcion.get("direccion_retiro"):
        partes.append(f"se retira en {opcion['direccion_retiro']}")
    if opcion.get("tiempo_entrega"):
        partes.append(opcion["tiempo_entrega"])
    texto = " · ".join(partes)
    return f"{con_numero}) {texto}" if con_numero is not None else texto


def donde_aplica(opcion: Dict[str, Any]) -> str:
    """Para la ficha: a quién se le ofrece esta opción."""
    if opcion["tipo"] == "retiro":
        return "cualquier cliente"
    lugares = [*(opcion.get("cantones") or []), *(opcion.get("provincias") or [])]
    if lugares:
        return "clientes de " + ", ".join(lugares)
    return "el resto del país"


def texto_para_la_ficha(envio_incluido: bool, opciones: List[Dict[str, Any]]) -> str:
    """Lo que Victoria sabe del envío de un producto (va en su ficha)."""
    activas = [o for o in opciones if o.get("activo", True)]
    if envio_incluido:
        # Las opciones solo existen cuando el envío se cobra aparte: con el envío incluido no hay nada que elegir.
        return "Envío: INCLUIDO en el precio; no se le cobra nada aparte al cliente."
    if not activas:
        return "Envío: este producto todavía no tiene opciones de entrega definidas; si el cliente pregunta, usa escalar_a_humano."
    lineas = [f"- {describir(o)} (para {donde_aplica(o)})" for o in activas]
    return (
        "Envío: se cobra aparte según el destino del cliente. Opciones:\n"
        + "\n".join(lineas)
        + "\nCuando sepas el cantón y la provincia del cliente, usa registrar_entrega para ofrecerle las que le aplican."
    )


# ----------------------------------------------------------------------
# Validación de lo que escribe el dueño
# ----------------------------------------------------------------------
def _texto(valor) -> str:
    return (str(valor) if valor is not None else "").strip()


def _opcional_dinero(valor, campo: str, errores: List[str], posicion: int) -> Optional[Decimal]:
    if valor is None or valor == "":
        return None
    try:
        numero = dinero(valor)
    except (InvalidOperation, ValueError):
        errores.append(f"Opción {posicion}: «{campo}» debe ser un monto, por ejemplo 2.50.")
        return None
    if numero < 0:
        errores.append(f"Opción {posicion}: «{campo}» no puede ser negativo.")
    return numero


def limpiar_y_validar(opciones: List[Dict[str, Any]]) -> "tuple[List[Dict[str, Any]], List[str]]":
    """Devuelve (opciones limpias, errores). Si hay errores, nada se guarda."""
    errores: List[str] = []
    limpias: List[Dict[str, Any]] = []

    if len(opciones) > MAXIMO_OPCIONES_POR_PRODUCTO:
        errores.append(f"Máximo {MAXIMO_OPCIONES_POR_PRODUCTO} opciones de entrega por producto.")
        return [], errores

    for posicion, crudo in enumerate(opciones, start=1):
        nombre = _texto(crudo.get("nombre"))
        tipo = _texto(crudo.get("tipo")) or "envio"
        if not nombre:
            errores.append(f"Opción {posicion}: falta el nombre (por ejemplo «Envío dentro de Cuenca»).")
        if len(nombre) > LARGO_MAXIMO_TEXTO:
            errores.append(f"Opción {posicion}: el nombre es demasiado largo.")
        if tipo not in TIPOS:
            errores.append(f"Opción {posicion}: el tipo debe ser «envio» o «retiro».")

        costo_cliente = _opcional_dinero(crudo.get("costo_cliente", 0), "lo que paga el cliente", errores, posicion)
        costo_negocio = _opcional_dinero(crudo.get("costo_negocio"), "lo que te cuesta", errores, posicion)
        cantones = [c for c in (_texto(x) for x in crudo.get("cantones") or []) if c]
        provincias = [p for p in (_texto(x) for x in crudo.get("provincias") or []) if p]
        resto = bool(crudo.get("resto_del_pais"))
        direccion = _texto(crudo.get("direccion_retiro")) or None

        if tipo == "retiro":
            if not direccion:
                errores.append(f"Opción {posicion}: un retiro necesita la dirección donde se retira.")
            cantones, provincias, resto = [], [], False
        elif tipo == "envio":
            if resto and (cantones or provincias):
                errores.append(
                    f"Opción {posicion}: elige UNA de dos: «el resto del país» o cantones/provincias concretos."
                )
            if not resto and not cantones and not provincias:
                errores.append(f"Opción {posicion}: indica a qué cantones o provincias aplica, o marca «el resto del país».")
            direccion = None

        limpias.append(
            {
                "nombre": nombre,
                "tipo": tipo,
                "costo_cliente": costo_cliente if costo_cliente is not None else Decimal("0.00"),
                "costo_negocio": costo_negocio,
                "cantones": cantones,
                "provincias": provincias,
                "resto_del_pais": resto,
                "direccion_retiro": direccion,
                "tiempo_entrega": _texto(crudo.get("tiempo_entrega")) or None,
                "activo": bool(crudo.get("activo", True)),
            }
        )
    return limpias, errores
