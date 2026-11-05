from typing import List


class AjustesInvalidosError(Exception):
    """La base rechazó los ajustes (una restricción CHECK). Normalmente la
    validación de entrada lo atrapa antes; esto es la red de seguridad."""

    def __init__(self, mensajes: List[str]):
        super().__init__("; ".join(mensajes))
        self.mensajes = mensajes
