"""
Prueba manual de integración contra la API REAL de Rocketfy (no hay sandbox).
NO forma parte de la suite automática de pytest a propósito: crea (y luego
rechaza) un pedido real de importe bajo, siguiendo la recomendación
explícita del proveedor (checklist Anexo D, pasos 6-7).

Uso:
    .venv/bin/python tools/rocketfy_order_smoke_test.py --sku SKU-REAL --confirm

Sin --confirm solo crea el pedido (no lo confirma ni lo rechaza) para que
puedas revisarlo a mano en el panel primero.

Requiere backend/.env con ROCKETFY_ACCOUNT_EMAIL, ROCKETFY_API_TOKEN,
ROCKETFY_BASE_URL ya configurados.
"""
import argparse
import random
import sys
import time
from decimal import Decimal

from dotenv import load_dotenv

sys.path.insert(0, ".")
load_dotenv(".env")

from src.config.settings import load_settings  # noqa: E402
from src.integrations.rocketfy import RocketfyBusinessError, RocketfyClient  # noqa: E402
from src.routes.pedidos.dto import CrearPedidoInputDTO, LineaPedidoDTO  # noqa: E402
from src.routes.pedidos.services import PedidoService  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sku", required=True, help="SKU real de tu catálogo en Rocketfy, con stock > 0")
    parser.add_argument("--confirm", action="store_true", help="Además de crear, confirma el pedido")
    parser.add_argument("--reject", action="store_true", help="Tras confirmar, rechaza el pedido (limpieza)")
    args = parser.parse_args()

    settings = load_settings()
    client = RocketfyClient(settings.rocketfy_base_url, settings.rocketfy_account_email, settings.rocketfy_api_token)

    id_local = int(time.time())  # único por corrida
    print(f"id_local de prueba: {id_local}")

    dto = CrearPedidoInputDTO(
        id_local=id_local,
        nombre_cliente="PRUEBA SMOKE TEST — IGNORAR",
        telefono="0999999999",
        direccion="Direccion de prueba, no despachar",
        canton="QUITO",
        provincia="Pichincha",
        total=Decimal("1.00"),
        lineas=[LineaPedidoDTO(sku=args.sku, nombre="Prueba", cantidad=1)],
        observaciones_transportista="PEDIDO DE PRUEBA — NO DESPACHAR, será rechazado.",
    )

    service = PedidoService(client=client)

    if not args.confirm:
        payload = service._construir_payload(dto)
        respuesta = client.crear_pedido(payload)
        print("Pedido creado (SIN confirmar):", respuesta)
        print(f"Revísalo en el panel y luego recházalo, o vuelve a correr con --confirm --reject.")
        return

    try:
        resultado = service.crear_y_confirmar(dto)
        print("Resultado:", resultado)
    except RocketfyBusinessError as exc:
        print(f"Rocketfy rechazó la confirmación: {exc.message}")
        resultado = None

    if args.reject and resultado and resultado.id_rocketfy:
        confirmacion = input(
            f"¿Confirmas RECHAZAR el pedido real id_rocketfy={resultado.id_rocketfy}? (escribe 'si'): "
        )
        if confirmacion.strip().lower() == "si":
            client.rechazar_pedido(resultado.id_rocketfy)
            print("Pedido rechazado.")
        else:
            print("Cancelado — el pedido de prueba queda activo en Rocketfy, revísalo manualmente.")


if __name__ == "__main__":
    main()
