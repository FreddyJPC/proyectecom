"""
Verificación del login del frontend (Fase 2 - Etapa 1).

No se valida el JWT localmente (evita depender del formato exacto de firma
de Supabase, que ya tuvo dos generaciones: secreto compartido HS256 y
llaves asimétricas nuevas). En su lugar se le pregunta a Supabase mismo si
el token es válido -- una sola llamada HTTP, aceptable para un panel de
un solo usuario administrador. Si el volumen de requests lo justifica más
adelante, se puede cambiar a verificación local vía JWKS sin tocar el
resto de la app (la interfaz pública de este módulo no cambiaría).
"""
from typing import Optional

import requests

from .settings import Settings


def verificar_token(token: str, settings: Settings) -> Optional[dict]:
    """Devuelve el usuario de Supabase si el token es válido, None si no."""
    try:
        resp = requests.get(
            f"{settings.supabase_url}/auth/v1/user",
            headers={"Authorization": f"Bearer {token}", "apikey": settings.supabase_anon_key},
            timeout=5,
        )
    except requests.RequestException:
        return None

    if resp.status_code != 200:
        return None

    return resp.json()
