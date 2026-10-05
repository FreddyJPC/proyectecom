class ConversacionNoEncontradaError(Exception):
    """No existe una conversación con ese id."""


class VentanaMensajeriaCerradaError(Exception):
    """La ventana de mensajería (24h de servicio, o 72h si es FEP) está
    cerrada -- Meta rechaza cualquier texto libre en ese caso, solo
    acepta plantillas aprobadas (fuera de alcance de esta entrega)."""


class EnvioWhatsAppFallidoError(Exception):
    """El mensaje ya quedó guardado localmente (rol='humano') pero el
    envío real a WhatsApp falló -- el dueño necesita saber que
    probablemente el cliente no lo recibió."""
