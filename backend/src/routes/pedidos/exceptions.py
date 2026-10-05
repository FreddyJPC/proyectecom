class PedidoEnEstadoAmbiguoError(Exception):
    """Un intento anterior de crear este pedido en Rocketfy quedó sin
    confirmación de éxito o fracaso (timeout u otro error de red — no un
    error de negocio con respuesta clara). Por advertencia explícita del
    proveedor ("no la reintente a ciegas"), no se reintenta /orders/create
    automáticamente: requiere revisión manual."""


class UbicacionNoResueltaError(Exception):
    """La provincia/cantón no existe en el catálogo cerrado de Rocketfy
    (docs/rocket-cantones-ecuador.csv). Se valida ANTES de llamar a la API
    para no repetir el fallo tardío de la sección 4.2 del doc del proveedor."""


class RecaudoMinimoNoAlcanzadoError(Exception):
    """El pedido es contraentrega (no_contra_entrega=False) y su total es
    menor al recaudo mínimo que exige Rocketfy para poder confirmarlo (ver
    RECAUDO_MINIMO_CONTRAENTREGA). Se valida ANTES de crear el pedido para
    no gastar el viaje redondo a Rocketfy y avisar de inmediato."""


class PedidoIncompletoError(Exception):
    """Rocketfy creó el pedido pero products_stock no trae una entrada por
    cada SKU simple enviado — probablemente algún SKU no existe en su
    catálogo y esa línea se descartó en silencio (sección 4.3 del doc)."""


class PedidoNoEncontradoError(Exception):
    """No existe un pedido local con ese id_local."""


class PedidoSinIdRocketfyError(Exception):
    """El pedido local todavía no tiene id_rocketfy asignado (nunca se creó
    en Rocketfy, o quedó en un estado que lo impide) — no hay nada que
    modificar o rechazar del lado de Rocketfy todavía."""
