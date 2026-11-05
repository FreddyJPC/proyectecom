"""
Ficha de venta de un producto, tal como la lee Victoria. Un solo formateador
compartido por dos caminos:

- el contexto del system prompt cuando ya se sabe de qué producto habla la
  conversación (conversation_service.py), y
- la herramienta `ver_ficha_producto` (tools.py), para cuando hay varios
  productos y el cliente pregunta por uno antes de que Victoria lo registre.

Antes la ficha no incluía el SKU ni el máximo de unidades; ahora sí: el SKU
exacto es lo que Victoria debe copiar al registrar el producto.
"""


def formatear_ficha_producto(producto: dict) -> str:
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
    return "\n".join(partes)
