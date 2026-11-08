from marshmallow import EXCLUDE, Schema, fields, validate


class SolicitudSchema(Schema):
    id = fields.Int()
    conversacion_id = fields.Int(data_key="conversacionId")
    tipo = fields.Str()
    tipo_etiqueta = fields.Str(data_key="tipoEtiqueta")
    detalle = fields.Str(allow_none=True)
    estado = fields.Str()
    nota_atencion = fields.Str(data_key="notaAtencion", allow_none=True)
    atendida_por = fields.Str(data_key="atendidaPor", allow_none=True)
    creada_en = fields.Str(data_key="creadaEn", allow_none=True)
    atendida_en = fields.Str(data_key="atendidaEn", allow_none=True)
    telefono = fields.Str(allow_none=True)
    nombre_cliente = fields.Str(data_key="nombreCliente", allow_none=True)
    direccion = fields.Str(allow_none=True)
    canton = fields.Str(allow_none=True)
    provincia = fields.Str(allow_none=True)
    producto = fields.Str(allow_none=True)
    variante = fields.Str(allow_none=True)
    cantidad = fields.Int(allow_none=True)
    metodo_pago = fields.Str(data_key="metodoPago", allow_none=True)
    entrega = fields.Str(allow_none=True)
    total = fields.Str(allow_none=True)
    proveedor = fields.Str(allow_none=True)
    tiene_pedido = fields.Bool(data_key="tienePedido")
    # La venta ligada (solo si ya hay un pedido cerrado) y lo que se puede hacer con ella.
    venta_id = fields.Int(data_key="ventaId", allow_none=True)
    venta_estado = fields.Str(data_key="ventaEstado", allow_none=True)
    venta_cobrada_en = fields.Str(data_key="ventaCobradaEn", allow_none=True)
    venta_cobrada_por = fields.Str(data_key="ventaCobradaPor", allow_none=True)
    venta_nota_cobro = fields.Str(data_key="ventaNotaCobro", allow_none=True)
    venta_cancelada_en = fields.Str(data_key="ventaCanceladaEn", allow_none=True)
    venta_cancelada_por = fields.Str(data_key="ventaCanceladaPor", allow_none=True)
    venta_motivo_cancelacion = fields.Str(data_key="ventaMotivoCancelacion", allow_none=True)
    puede_cobrar = fields.Bool(data_key="puedeCobrar")
    puede_deshacer_cobro = fields.Bool(data_key="puedeDeshacerCobro")
    puede_cancelar = fields.Bool(data_key="puedeCancelar")


class AtenderInputSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    nota = fields.Str(load_default=None, allow_none=True, validate=validate.Length(max=500))


solicitud_schema = SolicitudSchema()
atender_input_schema = AtenderInputSchema()
