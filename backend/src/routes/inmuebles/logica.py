"""
Reglas del módulo «Inmuebles» que no tocan la base de datos (se prueban solas): qué sabe el asistente de una propiedad, cómo se
escriben las fechas para el cliente (siempre en hora de Ecuador), qué le falta a una ficha y por qué estados pasa una visita.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional

ZONA_ECUADOR = timezone(timedelta(hours=-5))  # Ecuador no cambia de hora en el año

TIPOS = ("casa", "departamento", "terreno", "local", "oficina", "bodega", "otro")
OPERACIONES = ("venta", "alquiler")
ESTADOS_INMUEBLE = ("borrador", "activo", "pausado", "vendido", "archivado")
USOS = ("residencial", "comercial", "mixto")
ESTADOS_VISITA = ("solicitada", "confirmada", "realizada", "no_asistio", "cancelada")

NOMBRE_TIPO = {
    "casa": "Casa", "departamento": "Departamento", "terreno": "Terreno", "local": "Local comercial", "oficina": "Oficina",
    "bodega": "Bodega", "otro": "Propiedad",
}
NOMBRE_ESTADO_VISITA = {
    "solicitada": "pedida por el cliente, falta confirmar día y hora",
    "confirmada": "confirmada",
    "realizada": "ya se realizó",
    "no_asistio": "el cliente no asistió",
    "cancelada": "cancelada",
}

# Por qué estados puede pasar una visita. El asistente solo crea «solicitada»; todo lo demás lo hace el dueño desde la agenda.
# Las finales se pueden corregir entre sí (un error al marcar) y una cancelada se puede volver a pedir.
TRANSICIONES_VISITA = {
    "solicitada": {"confirmada", "cancelada"},
    "confirmada": {"confirmada", "realizada", "no_asistio", "cancelada"},
    "realizada": {"no_asistio", "cancelada"},
    "no_asistio": {"realizada", "cancelada"},
    "cancelada": {"solicitada", "confirmada"},
}

_DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
_MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


class TransicionDeVisitaInvalida(ValueError):
    pass


def puede_pasar(actual: str, nuevo: str) -> bool:
    return nuevo in TRANSICIONES_VISITA.get(actual, set())


def validar_transicion(actual: str, nuevo: str) -> None:
    if not puede_pasar(actual, nuevo):
        raise TransicionDeVisitaInvalida(
            f"Una visita {NOMBRE_ESTADO_VISITA.get(actual, actual)} no puede pasar a «{NOMBRE_ESTADO_VISITA.get(nuevo, nuevo)}»."
        )


def en_ecuador(momento: datetime) -> datetime:
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=timezone.utc)
    return momento.astimezone(ZONA_ECUADOR)


def fecha_legible(momento: datetime) -> str:
    """«sábado 29 de noviembre»: lo que lee el cliente, en hora de Ecuador."""
    local = en_ecuador(momento)
    return f"{_DIAS[local.weekday()]} {local.day} de {_MESES[local.month - 1]}"


def hora_legible(momento: datetime) -> str:
    """«10:30» (24 horas, como se escribe en Ecuador en un mensaje)."""
    local = en_ecuador(momento)
    return f"{local.hour:02d}:{local.minute:02d}"


def dinero(valor: Any) -> str:
    """$85.000,00 → «$85,000.00» como se escribe en Ecuador en los precios (punto decimal, coma de miles). Nunca float."""
    cantidad = Decimal(str(valor)).quantize(Decimal("0.01"))
    return f"${cantidad:,.2f}"


def _numero(valor: Any) -> str:
    """10.50 → «10,5»; 120.00 → «120» (sin ceros de más; coma decimal, como se habla)."""
    if valor is None:
        return ""
    texto = format(Decimal(str(valor)).normalize(), "f")
    return texto.replace(".", ",")


def coordenadas(inmueble: Dict[str, Any]) -> Optional[tuple]:
    lat, lng = inmueble.get("latitud"), inmueble.get("longitud")
    if lat is None or lng is None:
        return None
    return float(lat), float(lng)


def enlace_mapa(inmueble: Dict[str, Any]) -> Optional[str]:
    c = coordenadas(inmueble)
    return f"https://maps.google.com/?q={c[0]},{c[1]}" if c else None


def ubicacion_corta(inmueble: Dict[str, Any]) -> str:
    partes = [p for p in (inmueble.get("sector"), inmueble.get("ciudad")) if p]
    return ", ".join(partes)


def _linea(etiqueta: str, valor: Any) -> Optional[str]:
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        return None
    return f"- {etiqueta}: {str(valor).strip()}"


def precio_para_el_asistente(inmueble: Dict[str, Any]) -> str:
    """Qué puede decir del precio. Lo decide el dueño en la ficha: decirlo o no, y si es negociable."""
    if not inmueble.get("mostrar_precio") or inmueble.get("precio") is None:
        return (
            "- Precio: NO lo digas. Si el cliente lo pregunta, dile que el precio se lo indica el propietario y usa pasar_al_dueno "
            "con el motivo «pregunta el precio»."
        )
    base = f"- Precio: {dinero(inmueble['precio'])}"
    if inmueble.get("operacion") == "alquiler":
        base += " al mes"
    negociable = inmueble.get("precio_negociable")
    if negociable is True:
        return base + ". Es conversable: si el cliente quiere ofertar, toma nota de su oferta y usa pasar_al_dueno. Tú no aceptas ni rechazas ofertas."
    if negociable is False:
        return base + ". Es el precio final; si el cliente insiste en rebajarlo, usa pasar_al_dueno sin prometer nada."
    return base + ". No digas si es negociable: si el cliente quiere ofertar o pide rebaja, usa pasar_al_dueno sin prometer nada."


def ficha_para_el_asistente(inmueble: Dict[str, Any], cantidad_material: int = 0) -> str:
    """La ficha de la propiedad en texto: es TODO lo que el asistente sabe de ella (lo que no está aquí no lo inventa)."""
    medidas = None
    if inmueble.get("frente_m") is not None and inmueble.get("fondo_m") is not None:
        medidas = f"{_numero(inmueble['frente_m'])} m de frente por {_numero(inmueble['fondo_m'])} m de fondo"
    lineas = [
        f"Código: {inmueble['codigo']}",
        f"{NOMBRE_TIPO.get(inmueble.get('tipo'), 'Propiedad')} en {inmueble.get('operacion') or 'venta'}: {inmueble['titulo']}",
        _linea("Ciudad", inmueble.get("ciudad")),
        _linea("Sector", inmueble.get("sector")),
        _linea("Dirección", inmueble.get("direccion")),
        _linea("Cómo llegar", inmueble.get("referencia_llegada")),
        "- Ubicación en el mapa: disponible (usa enviar_ubicacion para mandarla)" if coordenadas(inmueble) else None,
        _linea("Terreno", f"{_numero(inmueble['terreno_m2'])} m²" if inmueble.get("terreno_m2") is not None else None),
        _linea("Construcción", f"{_numero(inmueble['construccion_m2'])} m²" if inmueble.get("construccion_m2") is not None else None),
        _linea("Medidas del terreno", medidas),
        _linea("Pisos", inmueble.get("pisos")),
        _linea("Habitaciones", inmueble.get("habitaciones")),
        _linea("Baños", _numero(inmueble["banos"]) if inmueble.get("banos") is not None else None),
        _linea("Parqueaderos", inmueble.get("parqueaderos")),
        _linea("Uso o zona", inmueble.get("uso")),
        _linea("Descripción", inmueble.get("descripcion")),
        _linea("Características", inmueble.get("caracteristicas")),
        _linea("Servicios", inmueble.get("servicios")),
        _linea("Documentación", inmueble.get("documentacion")),
        precio_para_el_asistente(inmueble),
        _linea("Horarios en que se puede visitar", inmueble.get("horarios_visita"))
        or "- Horarios de visita: no definidos. Pregunta al cliente qué día y hora prefiere.",
        f"- Fotos y videos: {cantidad_material} (usa enviar_material para mandarlos)" if cantidad_material else "- Fotos y videos: no hay todavía; no los prometas.",
        _linea("Preguntas frecuentes (respóndelas tal cual)", inmueble.get("preguntas_frecuentes")),
        _linea("Temas de los que NO hablas (si preguntan, usa pasar_al_dueno)", inmueble.get("temas_no_responder")),
    ]
    if inmueble.get("estado") == "vendido":
        lineas.append("- IMPORTANTE: esta propiedad YA SE VENDIÓ. Díselo con amabilidad y no agendes visitas.")
    elif inmueble.get("estado") in ("pausado", "archivado", "borrador"):
        lineas.append("- IMPORTANTE: esta propiedad no está disponible ahora. Díselo y usa pasar_al_dueno si el cliente insiste.")
    return "\n".join(l for l in lineas if l)


def catalogo_para_el_asistente(activos: Iterable[Dict[str, Any]]) -> str:
    """La lista corta de propiedades disponibles (cuando todavía no se sabe de cuál habla el cliente)."""
    lineas = []
    for i in activos:
        detalle = ", ".join(p for p in (NOMBRE_TIPO.get(i.get("tipo"), "Propiedad"), ubicacion_corta(i)) if p)
        precio = f" · {dinero(i['precio'])}" if i.get("mostrar_precio") and i.get("precio") is not None else ""
        lineas.append(f"- {i['codigo']}: {i['titulo']} ({detalle}){precio}")
    return "\n".join(lineas) if lineas else "(no hay propiedades disponibles en este momento)"


def visitas_para_el_asistente(visitas: Iterable[Dict[str, Any]]) -> str:
    lineas = []
    for v in visitas:
        texto = f"- {v.get('inmueble_codigo')}: {NOMBRE_ESTADO_VISITA.get(v['estado'], v['estado'])}"
        if v.get("fecha_hora") and v["estado"] == "confirmada":
            texto += f", el {fecha_legible(v['fecha_hora'])} a las {hora_legible(v['fecha_hora'])}"
        elif v.get("preferencia_cliente"):
            texto += f" (pidió: {v['preferencia_cliente']})"
        lineas.append(texto)
    return "\n".join(lineas) if lineas else "(todavía no ha pedido ninguna visita)"


def faltantes(inmueble: Dict[str, Any], cantidad_material: int) -> List[str]:
    """Lo que conviene completar para que el asistente responda bien (se muestra en la ficha; no impide publicar)."""
    falta = []
    if not coordenadas(inmueble):
        falta.append("Ubicación en el mapa (para mandar el pin)")
    if not inmueble.get("referencia_llegada"):
        falta.append("Cómo llegar")
    if inmueble.get("terreno_m2") is None and inmueble.get("construccion_m2") is None:
        falta.append("Metros de terreno o de construcción")
    if inmueble.get("tipo") != "terreno" and inmueble.get("habitaciones") is None:
        falta.append("Habitaciones")
    if inmueble.get("tipo") != "terreno" and inmueble.get("banos") is None:
        falta.append("Baños")
    if inmueble.get("precio") is None:
        falta.append("Precio (aunque no se diga, sirve para tu control)")
    if not inmueble.get("horarios_visita"):
        falta.append("Horarios de visita")
    if not cantidad_material:
        falta.append("Fotos o videos")
    return falta


def requisitos_para_activar(inmueble: Dict[str, Any]) -> List[str]:
    """Lo MÍNIMO para que el asistente pueda atender: sin esto, publicar se rechaza."""
    falta = []
    if not (inmueble.get("titulo") or "").strip():
        falta.append("el título")
    if not ((inmueble.get("sector") or "").strip() or (inmueble.get("direccion") or "").strip()):
        falta.append("el sector o la dirección")
    if not (inmueble.get("descripcion") or "").strip():
        falta.append("la descripción")
    return falta


def texto_confirmacion(plantilla: str, visita: Dict[str, Any], inmueble: Dict[str, Any]) -> str:
    """El mensaje que recibe el cliente cuando el dueño confirma su visita. Las fechas siempre en hora de Ecuador."""
    momento = visita["fecha_hora"]
    referencia = inmueble.get("referencia_llegada") or inmueble.get("direccion") or ubicacion_corta(inmueble)
    valores = {
        "nombre": (visita.get("nombre_cliente") or "").split(" ")[0] if visita.get("nombre_cliente") else "",
        "inmueble": inmueble["titulo"],
        "fecha": fecha_legible(momento),
        "hora": hora_legible(momento),
        "referencia": referencia or "",
    }
    texto = plantilla
    for clave, valor in valores.items():
        texto = texto.replace("{" + clave + "}", valor)
    # «Hola , …» si no se sabe el nombre: se limpia el espacio sobrante (respetando los saltos de línea).
    return "\n".join(" ".join(linea.split()) for linea in texto.replace(" ,", ",").splitlines()).strip()
