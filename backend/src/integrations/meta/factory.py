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
