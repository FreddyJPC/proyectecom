"""
Carga o actualiza un producto en la base de conocimiento de ventas de
Victoria (tabla productos_bot) -- distinta del catálogo de Rocketfy
(routes/productos, para SKU/stock real). Opcionalmente vincula un
id_anuncio (referral de Meta) al producto, para que Victoria sepa de qué
producto hablar cuando el cliente llega desde un anuncio Click-to-WhatsApp.

MUY IMPORTANTE -- el SKU que cargues acá DEBE ser un SKU real, tal como
existe hoy en el catálogo de Rocketfy (verificable con
RocketfyClient.listar_productos(q="...") o con
tools/rocketfy_order_smoke_test.py) -- NUNCA un SKU inventado o de
demostración. Esta fue la causa raíz del primer bug real encontrado al
probar el cierre de ventas de Victoria (Fase 3.2, Etapa 3.2, verificación
2026-09-27): se cargó "DEMO-AURICULARES-BT" como SKU de prueba, y
cerrar_venta falló contra la Rocketfy real porque ese SKU no existía en
su catálogo -- sin importar qué tan bien lo copiara Victoria. cerrar_venta
le pasa este SKU tal cual a PedidoService.crear_y_confirmar(), que llama
a la API real de Rocketfy; un SKU que Rocketfy no reconoce nunca puede
completar una venta contraentrega.

Uso:
    .venv/bin/python tools/cargar_producto_bot.py

Requiere backend/.env con SUPABASE_DB_URL ya configurado.
"""
import sys
from decimal import Decimal, InvalidOperation

from dotenv import load_dotenv

sys.path.insert(0, ".")
load_dotenv(".env")

from src.routes.whatsapp.repository import ProductoBotRepository  # noqa: E402


def _preguntar(etiqueta: str, requerido: bool = True, default: str = None) -> str:
    while True:
        sufijo = f" [{default}]" if default else ""
        valor = input(f"{etiqueta}{sufijo}: ").strip()
        if not valor and default is not None:
            return default
        if not valor and requerido:
            print("Este dato es obligatorio.")
            continue
        return valor or None


def _preguntar_precio() -> Decimal:
    while True:
        texto = input("Precio (ej: 19.99): ").strip()
        try:
            return Decimal(texto)
        except InvalidOperation:
            print("Precio inválido, escribe un número (ej: 19.99).")


def main():
    print("=== Cargar producto en la base de conocimiento de Victoria ===")
    sku = _preguntar("SKU")

    existente = ProductoBotRepository.obtener_por_sku(sku)
    if existente:
        respuesta = input(
            f"El SKU '{sku}' ya existe (\"{existente['nombre']}\"). ¿Actualizarlo? (si/no): "
        ).strip().lower()
        if respuesta != "si":
            print("Cancelado -- no se modificó nada.")
            return

    nombre = _preguntar("Nombre")
    descripcion = _preguntar("Descripción")
    precio = _preguntar_precio()
    variantes = _preguntar("Variantes (opcional, Enter para omitir)", requerido=False)
    tiempo_entrega = _preguntar("Tiempo de entrega (ej: 2 a 4 días hábiles)")
    metodos_pago_aceptados = _preguntar(
        "Métodos de pago aceptados", requerido=False, default="contraentrega, transferencia"
    )
    preguntas_frecuentes = _preguntar("Preguntas frecuentes (opcional, Enter para omitir)", requerido=False)
    temas_no_responder = _preguntar(
        "Temas que Victoria NO debe responder (opcional, Enter para omitir)", requerido=False
    )

    kwargs = dict(
        sku=sku,
        nombre=nombre,
        descripcion=descripcion,
        precio=precio,
        tiempo_entrega=tiempo_entrega,
        metodos_pago_aceptados=metodos_pago_aceptados,
        variantes=variantes,
        preguntas_frecuentes=preguntas_frecuentes,
        temas_no_responder=temas_no_responder,
    )
    if existente:
        producto = ProductoBotRepository.actualizar(**kwargs)
        print(f"\nProducto '{sku}' actualizado.")
    else:
        producto = ProductoBotRepository.crear(**kwargs)
        print(f"\nProducto '{sku}' creado.")

    id_anuncio = _preguntar(
        "ID de anuncio (referral) a vincular (opcional, Enter para omitir)", requerido=False
    )
    if id_anuncio:
        ProductoBotRepository.vincular_anuncio(id_anuncio=id_anuncio, producto_sku=sku)
        print(f"Anuncio '{id_anuncio}' vinculado a '{sku}'.")

    print("\nProducto guardado:")
    for campo, valor in producto.items():
        print(f"  {campo}: {valor}")


if __name__ == "__main__":
    main()
