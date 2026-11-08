from typing import Optional


class StockInsuficienteError(Exception):
    """El producto propio no tiene las unidades pedidas. `disponible`: lo que quedaba (None si no se sabe)."""

    def __init__(self, disponible: Optional[int] = None):
        super().__init__(f"Stock insuficiente (disponible: {disponible}).")
        self.disponible = disponible


class VentaYaRegistradaError(Exception):
    """Ese lead ya había cerrado una venta: no se registra dos veces."""

    def __init__(self, lead_id: int):
        super().__init__(f"El lead {lead_id} ya tiene una venta registrada.")
        self.lead_id = lead_id
