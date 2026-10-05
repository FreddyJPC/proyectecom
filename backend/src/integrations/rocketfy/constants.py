from decimal import Decimal
from enum import IntEnum


class RocketfyStatus(IntEnum):
    """status_id oficial de Rocketfy (Anexo A). Programar siempre contra el
    valor numérico, nunca contra status_name: el texto puede cambiar y el
    estado puede retroceder (7 -> 6 -> 7 -> 8 es válido)."""

    NUEVO = 1
    CONFIRMADO_PENDIENTE_PREPARACION = 2
    RECHAZADO = 3
    PREPARADO = 4
    ENVIADO = 5
    EN_RUTA = 6
    NOVEDAD = 7
    ENTREGADO = 8
    DEVUELTO_EN_TRANSITO = 9
    DEVUELTO_RECEPCIONADO = 10
    PENDIENTE_CONFIRMACION = 11
    APLAZADO = 12
    CARRITO_ABANDONADO = 13
    NO_CONFIRMABLE = 14
    DUPLICADO = 15
    RECOGIDA_EN_AGENCIA = 23


MENSAJE_MANTENIMIENTO = "mantenimiento"

# Recaudo mínimo para CONFIRMAR un pedido contraentrega (not_COD=0). No está
# documentado por Rocketfy (el doc solo describe el mensaje de error con un
# importe variable) -- se confirmó con un pedido real de prueba el
# 2026-09-06 (PROGRESS.md, entrada 0.0.13). No aplica a pedidos prepagados
# (no_contra_entrega=True / not_COD=1). Si Rocketfy cambia este valor, la
# API seguirá rechazando la confirmación igual -- esto solo evita el viaje
# redondo y avisa antes.
RECAUDO_MINIMO_CONTRAENTREGA = Decimal("10.00")

# status_id que consideramos "cerrados" para efectos de reconciliación: un
# pedido en uno de estos estados ya no necesita seguir monitoreándose.
ESTADOS_TERMINALES = {
    RocketfyStatus.RECHAZADO,
    RocketfyStatus.ENTREGADO,
    RocketfyStatus.DEVUELTO_RECEPCIONADO,
    RocketfyStatus.DUPLICADO,
}
