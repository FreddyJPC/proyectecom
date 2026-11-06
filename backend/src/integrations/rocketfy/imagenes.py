"""
Las imágenes de los productos de Rocketfy.

La guía del proveedor dice que `image_url` es una URL completa (`https://...`),
pero lo que devuelve la API real es una RUTA RELATIVA al sitio de Rocketfy, p. ej.
`/storage/products/4193/foto.jpg` (comprobado en producción el 2026-11-06). Una
ruta relativa no sirve en ningún lado: el navegador del panel la buscaría en el
dominio del panel y WhatsApp (Meta) necesita un enlace https completo.

`url_de_imagen` la completa con el sitio de la propia API (mismo dominio que
`ROCKETFY_BASE_URL`, sin el `/api`). Es una suposición razonable (el `/storage` de
este tipo de sitio se sirve desde el mismo dominio) pero NO se pudo comprobar
desde el entorno de desarrollo (el dominio no es alcanzable): ver pendiente #58.
"""
from typing import Optional
from urllib.parse import urlparse

from src.config.settings import load_settings


def url_de_imagen(valor: Optional[str], base_url: Optional[str] = None) -> Optional[str]:
    """URL absoluta de la imagen, o None si el valor no sirve (vacío, esquema raro…)."""
    texto = (valor or "").strip()
    if not texto:
        return None
    minusculas = texto.lower()
    if minusculas.startswith(("https://", "http://")):
        return texto
    if texto.startswith("//"):
        return f"https:{texto}"
    if texto.startswith("/"):
        try:
            partes = urlparse(base_url or load_settings().rocketfy_base_url)
        except Exception:
            return None
        if partes.scheme not in ("http", "https") or not partes.netloc:
            return None
        return f"{partes.scheme}://{partes.netloc}{texto}"
    return None
