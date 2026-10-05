from functools import lru_cache

from src.config.settings import load_settings

from .contratos import LLMProvider
from .providers.anthropic_provider import AnthropicProvider


@lru_cache(maxsize=1)
def get_llm_client() -> LLMProvider:
    """Devuelve el proveedor de LLM activo, seleccionado por LLM_PROVIDER.
    Agregar un proveedor nuevo en el futuro es: escribir su adapter en
    providers/ implementando LLMProvider, y sumar una rama acá -- nada
    más del proyecto cambia (ver contratos.py).

    El fail-fast de la api_key del proveedor activo vive acá, no en
    Settings: Settings.anthropic_api_key se queda opcional a propósito,
    porque cualquier código que solo necesite Settings para otra cosa
    (p.ej. abrir una conexión a Postgres) no debería dejar de arrancar
    solo porque el LLM no está configurado todavía. Acá sí es correcto
    fallar duro, porque este es el único punto que de verdad necesita
    la key -- ver PROGRESS.md, Fase 3.2, para el detalle."""
    settings = load_settings()
    proveedor = settings.llm_provider

    if proveedor == "anthropic":
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY es requerida cuando LLM_PROVIDER=anthropic")
        return AnthropicProvider(api_key=settings.anthropic_api_key, modelo=settings.llm_model)

    # Cuando se agregue un proveedor nuevo en el futuro, se suma acá:
    # elif proveedor == "openai":
    #     return OpenAIProvider(api_key=settings.openai_api_key, modelo=settings.llm_model)
    # elif proveedor == "gemini":
    #     return GeminiProvider(api_key=settings.gemini_api_key, modelo=settings.llm_model)

    raise ValueError(f"Proveedor de LLM no soportado: {proveedor}")
