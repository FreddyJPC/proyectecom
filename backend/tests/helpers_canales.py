"""Ayudantes de pruebas para el registro de canales de mensajería (ADR-014)."""
from src.integrations.canales import CanalWhatsApp, RegistroCanales


def registro_de_whatsapp(cliente) -> RegistroCanales:
    """Un registro cuyo único canal es WhatsApp, servido por `cliente` (un falso o un MagicMock). Así las pruebas siguen
    comprobando lo que el cliente de WhatsApp recibe (`enviar_texto(telefono=…, mensaje=…)`) pasando por el adaptador real."""
    return RegistroCanales({"whatsapp": CanalWhatsApp(cliente)})
