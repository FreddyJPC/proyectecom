class LeadNoEncontradoError(Exception):
    """No existe un lead con ese id."""


class ContactoNoEncontradoError(Exception):
    """No existe un contacto con ese id."""


class DatosInvalidosError(Exception):
    """Un valor no sirve (temperatura desconocida, motivo de pérdida fuera del catálogo…). El mensaje se le muestra a la persona."""


class OtroLeadAbiertoError(Exception):
    """El contacto ya tiene OTRO lead abierto: solo puede haber uno a la vez, así que este no se puede reabrir."""


class VentaYaCerradaError(Exception):
    """La etapa del lead (venta cerrada o cancelada) manda sobre la temperatura: no se puede contradecir a mano."""
