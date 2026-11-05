class ProductoBotNoEncontradoError(Exception):
    """No hay ningún producto de ventas con ese SKU en `productos_bot`."""


class ProductoBotYaExisteError(Exception):
    """Ya hay un producto de ventas con ese SKU (borrador, activo o archivado):
    no se crea otro, se edita el que existe."""


class TransicionInvalidaError(Exception):
    """El producto no puede pasar a ese estado desde el que tiene hoy (p. ej.
    pausar uno que ya está pausado, o publicar uno archivado)."""


class SkuInvalidoError(Exception):
    """El SKU no se puede usar como identificador en la app (p. ej. trae '/')."""


class PublicacionBloqueadaError(Exception):
    """El producto no cumple lo mínimo para estar activo. `bloqueos` es la lista
    de motivos, en español, listos para mostrarle al dueño."""

    def __init__(self, bloqueos):
        super().__init__("; ".join(bloqueos))
        self.bloqueos = list(bloqueos)


class TopeDeIAAlcanzadoError(Exception):
    """Ya se usaron todos los borradores de IA permitidos hoy."""

    def __init__(self, usadas: int, tope: int):
        super().__init__(
            f"Ya usaste los {tope} borradores de IA de hoy. El contador se reinicia a medianoche "
            "(hora de Ecuador); puedes subir el tope en Ajustes de precios."
        )
        self.usadas = usadas
        self.tope = tope


class IANoDisponibleError(Exception):
    """La IA no está configurada, la clave no sirve o el proveedor está saturado."""


class IAFalloError(Exception):
    """No se pudo hablar con el proveedor de IA, o contestó algo inservible."""

