"""
Ficha de venta de un producto, tal como la lee Victoria. Un solo formateador
compartido por dos caminos:

- el contexto del system prompt cuando ya se sabe de qué producto habla la
  conversación (conversation_service.py), y
- la herramienta `ver_ficha_producto` (tools.py), para cuando hay varios
  productos y el cliente pregunta por uno antes de que Victoria lo registre.

Antes la ficha no incluía el SKU ni el máximo de unidades; ahora sí: el SKU
exacto es lo que Victoria debe copiar al registrar el producto.

ADR-012: la ficha también dice CÓMO se cierra la venta de este producto y cómo es su envío. Esa es la forma
de darle a Victoria reglas distintas por producto sin tocar sus instrucciones generales.
"""
from typing import List, Optional

from src.routes.entregas.logica import texto_para_la_ficha
from src.routes.ventas.origen import es_de_cierre_manual

CIERRE_MANUAL = (
    "Cierre de la venta: MANUAL. Este producto lo gestiona el dueño (no se crea un pedido solo). Apenas el cliente "
    "muestre intención de compra (quiere comprar, pagar o pide envío) avisa al dueño con solicitar_gestion y sigue "
    "tomando sus datos; si quiere ver el producto en persona o negociar el precio, usa solicitar_gestion y despídete. "
    "Cuando tengas todos los datos usa cerrar_venta: eso le pasa el pedido al dueño, que coordina el pago y la entrega. "
    "Tú nunca das cuentas bancarias ni confirmas pagos."
)


def formatear_ficha_producto(producto: dict, entregas: Optional[List[dict]] = None) -> str:
    partes = [
        f"SKU: {producto['sku']}",
        f"Nombre: {producto['nombre']}",
        f"Descripción: {producto['descripcion']}",
        f"Precio por unidad: ${producto['precio']}",
        f"Tiempo de entrega: {producto['tiempo_entrega']}",
        f"Métodos de pago aceptados: {producto['metodos_pago_aceptados']}",
        f"Unidades máximas por pedido: {producto.get('max_unidades_por_pedido') or 1}",
    ]
    if producto.get("variantes"):
        partes.append(f"Variantes: {producto['variantes']}")
    if producto.get("preguntas_frecuentes"):
        partes.append(f"Preguntas frecuentes: {producto['preguntas_frecuentes']}")
    if producto.get("temas_no_responder"):
        partes.append(f"Temas que NO debes responder: {producto['temas_no_responder']}")
    # `entregas=None` = no se consultó (no se dice nada del envío); [] = se consultó y no tiene opciones.
    if entregas is not None:
        partes.append(texto_para_la_ficha(bool(producto.get("envio_incluido", True)), entregas))
    if es_de_cierre_manual(producto):
        partes.append(CIERRE_MANUAL)
    return "\n".join(partes)
