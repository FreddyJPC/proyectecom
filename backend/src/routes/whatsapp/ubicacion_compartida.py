"""
Las coordenadas que el cliente compartió con el botón de ubicación 📍 de WhatsApp (entrada 0.0.140).

El webhook guarda ese mensaje como texto con un enlace `https://maps.google.com/?q=LAT,LON` (tipo «ubicacion», ver
`controllers._enlace_al_mapa`). Aquí solo se leen de vuelta: son coordenadas EXACTAS que mandó WhatsApp, no algo que el
cliente escribió ni que la IA interpretó. Un enlace de mapa que el cliente pega a mano NO cuenta (no se puede saber qué es).
"""
import re
from typing import Iterable, Optional, Tuple

_PATRON = re.compile(r"https://maps\.google\.com/\?q=(-?\d{1,2}(?:\.\d+)?),(-?\d{1,3}(?:\.\d+)?)")


def coordenadas_compartidas(mensajes: Iterable[dict]) -> Optional[Tuple[float, float]]:
    """La ÚLTIMA ubicación 📍 que mandó el cliente, o None. Se descarta lo que no es una coordenada posible."""
    for fila in reversed(list(mensajes)):
        if fila.get("rol") != "cliente" or fila.get("tipo") != "ubicacion":
            continue
        encontrado = _PATRON.search(fila.get("contenido") or "")
        if not encontrado:
            continue
        latitud, longitud = float(encontrado.group(1)), float(encontrado.group(2))
        if -90 <= latitud <= 90 and -180 <= longitud <= 180:
            return latitud, longitud
    return None
