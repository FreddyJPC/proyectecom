"""Crea el cliente de Meta con las variables del servidor (Railway) y el dataset guardado. Sin alguno de los datos devuelve None: el trabajo no envía nada."""
import os
from typing import Callable, List, Optional, Tuple

from .client import MetaConversionesClient

# Nombres de las variables del servidor (los valores viven solo en Railway; nunca en el repositorio ni en el chat).
VARIABLE_TOKEN = "META_CAPI_TOKEN"
VARIABLE_DATASET = "META_DATASET_ID"
VARIABLE_WABA = "WHATSAPP_WABA_ID"


def _dataset_guardado() -> Optional[str]:
    # Import tardío: la capa de rutas depende de integraciones, no al revés.
    from src.routes.meta.repository import MetaRepository

    return MetaRepository.dataset_id()


def dataset_id(leer_guardado: Callable[[], Optional[str]] = _dataset_guardado) -> Optional[str]:
    """El dataset a usar: la variable del servidor si existe (respaldo manual) y, si no, el que guardó el botón «Preparar Meta»."""
    manual = (os.getenv(VARIABLE_DATASET) or "").strip()
    return manual or leer_guardado()


def token_configurado() -> bool:
    return bool((os.getenv(VARIABLE_TOKEN) or "").strip())


def cuenta_whatsapp_configurada() -> bool:
    return bool((os.getenv(VARIABLE_WABA) or "").strip())


def faltantes(dataset: Optional[str]) -> List[str]:
    ausentes = []
    if not token_configurado():
        ausentes.append(VARIABLE_TOKEN)
    if not cuenta_whatsapp_configurada():
        ausentes.append(VARIABLE_WABA)
    if not dataset:
        ausentes.append("dataset (usa «Preparar Meta» en el panel)")
    return ausentes


def get_meta_client(leer_guardado: Callable[[], Optional[str]] = _dataset_guardado) -> Tuple[Optional[MetaConversionesClient], List[str]]:
    """Devuelve (cliente, lo que falta). El cliente es None si falta algo."""
    dataset = dataset_id(leer_guardado)
    ausentes = faltantes(dataset)
    if ausentes:
        return None, ausentes
    return (
        MetaConversionesClient(
            access_token=os.environ[VARIABLE_TOKEN].strip(),
            dataset_id=dataset,
            whatsapp_business_account_id=os.environ[VARIABLE_WABA].strip(),
        ),
        [],
    )


def get_cliente_para_dataset() -> Tuple[Optional[MetaConversionesClient], List[str]]:
    """Cliente solo para pedir el dataset (no necesita tenerlo todavía): requiere el token y la cuenta de WhatsApp."""
    ausentes = [v for v, ok in ((VARIABLE_TOKEN, token_configurado()), (VARIABLE_WABA, cuenta_whatsapp_configurada())) if not ok]
    if ausentes:
        return None, ausentes
    return (
        MetaConversionesClient(
            access_token=os.environ[VARIABLE_TOKEN].strip(),
            dataset_id="",
            whatsapp_business_account_id=os.environ[VARIABLE_WABA].strip(),
        ),
        [],
    )


# ---------------------------------------------------------------------------
# API de Marketing (ADR-017): leer anuncios y gasto, y pausar. Mismo token (regla D5).
# ---------------------------------------------------------------------------
VARIABLE_CUENTA = "META_AD_ACCOUNT_ID"


def _cuenta_guardada() -> Optional[str]:
    from src.routes.meta.repository import MetaRepository  # tardío: rutas dependen de integraciones, no al revés

    return MetaRepository.cuenta_publicitaria()


def cuenta_publicitaria(leer_guardada: Callable[[], Optional[str]] = _cuenta_guardada) -> Optional[str]:
    """La guardada desde el panel («Conexión con Meta») o, si no hay, la variable del servidor (respaldo)."""
    return (leer_guardada() or "").strip() or (os.getenv(VARIABLE_CUENTA) or "").strip() or None


def get_marketing_client(leer_guardada: Callable[[], Optional[str]] = _cuenta_guardada):
    """Devuelve (cliente, lo que falta). El cliente es None si falta el token o la cuenta publicitaria."""
    from .marketing import MetaMarketingClient, normalizar_cuenta

    cuenta = cuenta_publicitaria(leer_guardada)
    ausentes = []
    if not token_configurado():
        ausentes.append(VARIABLE_TOKEN)
    if not cuenta or not normalizar_cuenta(cuenta):
        ausentes.append("cuenta publicitaria (guárdala en Conexión con Meta)")
    if ausentes:
        return None, ausentes
    return MetaMarketingClient(os.environ[VARIABLE_TOKEN].strip(), cuenta), []
