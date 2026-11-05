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
