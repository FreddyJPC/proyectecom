"""
Reglas de la galería de fotos de un producto (ADR-012). Lógica PURA: se prueba sin base de datos.

Las fotos las sube la propia app al bucket público `productos` (con la sesión del dueño) y después le avisa al
servidor la ruta del archivo. El servidor NUNCA acepta una URL escrita por el cliente: la arma él mismo a partir
de la ruta, para que solo se puedan registrar archivos de ese bucket.

Cada producto tiene su carpeta en el bucket: `p<id>` (el id numérico, no el SKU: un SKU puede traer espacios o
símbolos que Storage no admite en una ruta).
"""
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote

BUCKET = "productos"
MAXIMO_POR_PRODUCTO = 8
EXTENSIONES = ("jpg", "jpeg", "png")
_NOMBRE_DE_ARCHIVO = re.compile(r"^[A-Za-z0-9._-]{1,120}$")


class RutaDeImagenInvalida(ValueError):
    pass


def url_publica(supabase_url: str, ruta: str) -> str:
    """Enlace https público de un archivo del bucket."""
    return f"{supabase_url.rstrip('/')}/storage/v1/object/public/{BUCKET}/{quote(ruta, safe='/')}"


def carpeta_de(producto_id: int) -> str:
    """La carpeta del producto dentro del bucket."""
    return f"p{producto_id}"


def validar_ruta(carpeta_esperada: str, ruta: str) -> str:
    """La ruta tiene que ser `<carpeta>/<archivo>.jpg|png`: dentro de la carpeta de ESTE producto, sin subcarpetas
    ni trucos (`..`). Devuelve la ruta limpia o lanza `RutaDeImagenInvalida`."""
    ruta = (ruta or "").strip()
    carpeta, _, archivo = ruta.rpartition("/")
    if carpeta != carpeta_esperada or not _NOMBRE_DE_ARCHIVO.match(archivo) or ".." in archivo:
        raise RutaDeImagenInvalida("La foto debe estar en la carpeta de este producto, con un nombre simple.")
    if archivo.rsplit(".", 1)[-1].lower() not in EXTENSIONES:
        raise RutaDeImagenInvalida("Solo se aceptan fotos JPG o PNG (WhatsApp no acepta otros formatos).")
    return ruta


def galeria_para_enviar(subidas: List[Dict[str, Any]], imagen_de_rocketfy: Optional[str]) -> List[str]:
    """Las URLs que Victoria puede mandar: las fotos subidas (en su orden) o, si no hay ninguna, la de
    Rocketfy. Solo enlaces https: Meta no descarga otra cosa."""
    urls = [i["url"] for i in subidas if str(i.get("url", "")).lower().startswith("https://")]
    if urls:
        return urls
    if imagen_de_rocketfy and imagen_de_rocketfy.lower().startswith("https://"):
        return [imagen_de_rocketfy]
    return []
