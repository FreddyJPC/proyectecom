"""Crea el cliente de Meta con las variables del servidor (Railway). Sin alguna de ellas devuelve None: el trabajo no envía nada."""
import os
from typing import List, Optional, Tuple

from .client import MetaConversionesClient

# Nombres de las variables del servidor (los valores viven solo en Railway; nunca en el repositorio ni en el chat).
VARIABLE_TOKEN = "META_CAPI_TOKEN"
VARIABLE_DATASET = "META_DATASET_ID"
VARIABLE_WABA = "WHATSAPP_WABA_ID"


def faltantes() -> List[str]:
    return [v for v in (VARIABLE_TOKEN, VARIABLE_DATASET, VARIABLE_WABA) if not (os.getenv(v) or "").strip()]


def get_meta_client() -> Tuple[Optional[MetaConversionesClient], List[str]]:
    """Devuelve (cliente, variables que faltan). El cliente es None si falta alguna."""
    ausentes = faltantes()
    if ausentes:
        return None, ausentes
    return (
        MetaConversionesClient(
            access_token=os.environ[VARIABLE_TOKEN].strip(),
            dataset_id=os.environ[VARIABLE_DATASET].strip(),
            whatsapp_business_account_id=os.environ[VARIABLE_WABA].strip(),
        ),
        [],
    )
