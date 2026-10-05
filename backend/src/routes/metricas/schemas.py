from marshmallow import Schema, fields

# Los montos se tratan como string (nunca float): Rocketfy los entrega como
# cadena decimal y el proveedor advierte explícitamente no interpretarlos
# como número en coma flotante para fines contables.


class MetricasGeneralesResponseSchema(Schema):
    """Traduce GET /api/statistics/general (sección 9 del doc del
    proveedor). Cubre PARCIALMENTE el requerimiento 6 — ver 'avisoImportante'
    agregado en el controller y ADR-003 en PROGRESS.md."""

    pedidos_hoy = fields.Int(data_key="pedidosHoy", attribute="orders_today", allow_none=True, dump_default=None)
    monto_total_pedidos_hoy = fields.Str(
        data_key="montoTotalPedidosHoy", attribute="orders_total_amount_today", allow_none=True, dump_default=None
    )
    confirmados_hoy = fields.Int(
        data_key="confirmadosHoy", attribute="confirmed_today", allow_none=True, dump_default=None
    )
    ingreso_confirmado = fields.Str(
        data_key="ingresoConfirmado", attribute="revenue_confirmed", allow_none=True, dump_default=None
    )
    ingreso_hoy = fields.Str(data_key="ingresoHoy", attribute="revenue_today", allow_none=True, dump_default=None)
    ingreso_total = fields.Str(data_key="ingresoTotal", attribute="revenue_total", allow_none=True, dump_default=None)
    ingreso_en_transito = fields.Str(
        data_key="ingresoEnTransito", attribute="revenue_transit", allow_none=True, dump_default=None
    )
    ingreso_retenido_por_novedad = fields.Str(
        data_key="ingresoRetenidoPorNovedad", attribute="revenue_incidence", allow_none=True, dump_default=None
    )
    costo_productos_en_transito = fields.Str(
        data_key="costoProductosEnTransito", attribute="transit_products_cost", allow_none=True, dump_default=None
    )


metricas_generales_response_schema = MetricasGeneralesResponseSchema()
