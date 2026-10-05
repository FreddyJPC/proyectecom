class WhatsAppError(Exception):
    """Excepción base para cualquier fallo de la integración con WhatsApp Cloud API."""


class WhatsAppAuthError(WhatsAppError):
    """Credenciales inválidas o token expirado (401). Los tokens temporales
    de la Cloud API vencen -- requiere regenerar desde developers.facebook.com,
    no reintentable tal cual."""


class WhatsAppRequestError(WhatsAppError):
    """Error de red, timeout, o error de servidor (5xx / sin JSON).
    Reintentable con cautela."""


class WhatsAppBusinessError(WhatsAppError):
    """Meta rechazó el mensaje por una regla de negocio (400) -- plantilla
    no aprobada, número inválido, fuera de la ventana de 24h sin plantilla,
    etc. No reintentable tal cual, hay que corregir el dato."""

    def __init__(self, message: str, code=None, raw: dict = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.raw = raw or {}
