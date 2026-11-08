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


class AtenderInputSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    nota = fields.Str(load_default=None, allow_none=True, validate=validate.Length(max=500))


solicitud_schema = SolicitudSchema()
atender_input_schema = AtenderInputSchema()
