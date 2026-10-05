class LLMError(Exception):
    """Excepción base para cualquier fallo de la integración con un LLM,
    sin importar el proveedor detrás (mismo patrón que RocketfyError /
    WhatsAppError en las otras integraciones)."""


class LLMAuthError(LLMError):
    """Credenciales inválidas o faltantes, sin importar el proveedor."""


class LLMRequestError(LLMError):
    """Error de red, timeout, o error de servidor del proveedor."""


class LLMRateLimitError(LLMError):
    """Se alcanzó el límite de rate limit -- reintentable con backoff."""
