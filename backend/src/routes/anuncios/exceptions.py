from typing import Optional


class AnuncioInvalidoError(Exception):
    """El identificador del anuncio no sirve (vacío, con espacios o demasiado largo)."""


class ProductoNoExisteError(Exception):
    def __init__(self, sku: str):
        super().__init__(f"No existe el producto {sku}.")
        self.sku = sku


class AnuncioYaVinculadoError(Exception):
    """Ese anuncio ya está vinculado a OTRO producto: hay que confirmar que se quiere cambiar."""

    def __init__(self, id_anuncio: str, sku_actual: str, nombre_actual: Optional[str] = None):
        super().__init__(f"El anuncio {id_anuncio} ya está vinculado a {nombre_actual or sku_actual}.")
        self.id_anuncio = id_anuncio
        self.sku_actual = sku_actual
        self.nombre_actual = nombre_actual


class AnuncioNoVinculadoError(Exception):
    def __init__(self, id_anuncio: str):
        super().__init__(f"El anuncio {id_anuncio} no está vinculado a ningún producto.")
        self.id_anuncio = id_anuncio
