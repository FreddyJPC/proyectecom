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


class SinPedidoEnCursoError(Exception):
    """Se quiso confirmar un pago, pero la conversación no tiene un pedido por transferencia pendiente."""


class ArchivoNoDisponibleError(Exception):
    """El mensaje no tiene archivo, o Meta ya no lo entrega."""


class PedidoYaCerradoError(Exception):
    """Se quiso cambiar los datos de envío de un pedido que ya se creó o se pasó al dueño: ya no tiene efecto."""


class DatosEnvioInvalidosError(ValueError):
    """La ciudad o la provincia no coinciden con el catálogo de entregas. `sugerencias`: nombres parecidos."""

    def __init__(self, mensaje: str, sugerencias=None):
        super().__init__(mensaje)
        self.sugerencias = list(sugerencias or [])
