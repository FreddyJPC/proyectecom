class ConversacionNoEncontradaError(Exception):
    """No existe una conversación con ese id."""


class VentanaMensajeriaCerradaError(Exception):
    """La ventana de servicio (24 h desde el último mensaje del cliente) está
    cerrada -- Meta rechaza cualquier texto libre en ese caso, solo acepta
    plantillas aprobadas (fuera de alcance por ahora). La ventana gratuita
    de los anuncios no cambia esto: es un beneficio de costo, no un permiso."""


class EnvioWhatsAppFallidoError(Exception):
    """El mensaje ya quedó guardado localmente (rol='humano') pero el
    envío real a WhatsApp falló -- el dueño necesita saber que
    probablemente el cliente no lo recibió."""


class ArchivoNoDisponibleError(Exception):
    """El mensaje no tiene archivo, o Meta ya no lo entrega."""
