class RocketfyError(Exception):
    """Excepción base para cualquier fallo de la integración con Rocketfy."""


class RocketfyAuthError(RocketfyError):
    """Credenciales inválidas, acceso API no habilitado o KYC sin verificar (401/400)."""


class RocketfyRequestError(RocketfyError):
    """Error de red, timeout o respuesta no-JSON. No es un error de negocio."""


class RocketfyBusinessError(RocketfyError):
    """Respuesta ok=0 de Rocketfy: error de negocio (sin cobertura, saldo
    insuficiente, cantón no resuelto, ya confirmado, etc.). El mensaje viene
    tal cual lo redactó Rocketfy — ver tabla de la sección 5.1 de su doc para
    interpretarlo."""

    def __init__(self, message: str, code=None, raw: dict = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.raw = raw or {}
