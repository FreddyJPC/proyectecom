from marshmallow import EXCLUDE, Schema, fields, validate


class LineaPedidoSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    sku = fields.Str(required=True, validate=validate.Length(min=1))
    nombre = fields.Str(required=True, validate=validate.Length(min=1))
    cantidad = fields.Int(required=True, validate=validate.Range(min=1))


class CrearPedidoInputSchema(Schema):
    """Validación de entrada para crear+confirmar un pedido. camelCase
    externo -> snake_case interno, mismo patrón que logistica/transportistas."""

    class Meta:
        unknown = EXCLUDE

    id_local = fields.Int(data_key="idLocal", required=True)
    nombre_cliente = fields.Str(data_key="nombreCliente", required=True, validate=validate.Length(min=1))
    telefono = fields.Str(data_key="telefono", required=True, validate=validate.Length(min=1))
    direccion = fields.Str(data_key="direccion", required=True, validate=validate.Length(min=1))
    direccion_2 = fields.Str(data_key="direccion2", load_default="")
    canton = fields.Str(data_key="canton", required=True, validate=validate.Length(min=1))
    provincia = fields.Str(data_key="provincia", required=True, validate=validate.Length(min=1))
    total = fields.Decimal(data_key="total", required=True, places=2, as_string=False)
    lineas = fields.List(
        fields.Nested(LineaPedidoSchema), data_key="lineas", required=True, validate=validate.Length(min=1)
    )
    email = fields.Str(data_key="email", allow_none=True, load_default=None)
    codigo_postal = fields.Str(data_key="codigoPostal", allow_none=True, load_default=None)
    no_contra_entrega = fields.Bool(data_key="noContraEntrega", load_default=False)
    observaciones_transportista = fields.Str(data_key="observacionesTransportista", load_default="")
    tienda_id = fields.Int(data_key="tiendaId", allow_none=True, load_default=None)
    ip = fields.Str(data_key="ip", allow_none=True, load_default=None)
    latitud = fields.Float(data_key="latitud", allow_none=True, load_default=None)
    longitud = fields.Float(data_key="longitud", allow_none=True, load_default=None)


class ModificarPedidoInputSchema(Schema):
    """Todos los campos son opcionales: solo se aplican los enviados."""

    class Meta:
        unknown = EXCLUDE

    nombre_cliente = fields.Str(data_key="nombreCliente", allow_none=True, load_default=None)
    email = fields.Str(data_key="email", allow_none=True, load_default=None)
    telefono = fields.Str(data_key="telefono", allow_none=True, load_default=None)
    direccion = fields.Str(data_key="direccion", allow_none=True, load_default=None)
    direccion_2 = fields.Str(data_key="direccion2", allow_none=True, load_default=None)
    canton = fields.Str(data_key="canton", allow_none=True, load_default=None)
    provincia = fields.Str(data_key="provincia", allow_none=True, load_default=None)
    codigo_postal = fields.Str(data_key="codigoPostal", allow_none=True, load_default=None)


class PedidoResponseSchema(Schema):
    id_local = fields.Int(data_key="idLocal")
    id_rocketfy = fields.Int(data_key="idRocketfy", allow_none=True)
    estado_local = fields.Str(data_key="estadoLocal")
    status_id_rocketfy = fields.Int(data_key="statusIdRocketfy", allow_none=True)
    mensaje_error = fields.Str(data_key="mensajeError", allow_none=True)
    creado_en = fields.Str(data_key="creadoEn", allow_none=True)
    confirmado_en = fields.Str(data_key="confirmadoEn", allow_none=True)
    actualizado_en = fields.Str(data_key="actualizadoEn", allow_none=True)


class PedidoResumenSchema(Schema):
    """Fase 2 - Etapa 2 del frontend: una fila del listado de pedidos."""

    id_local = fields.Int(data_key="idLocal")
    id_rocketfy = fields.Int(data_key="idRocketfy", allow_none=True)
    estado_local = fields.Str(data_key="estadoLocal")
    status_id_rocketfy = fields.Int(data_key="statusIdRocketfy", allow_none=True)
    nombre_cliente = fields.Str(data_key="nombreCliente")
    telefono = fields.Str(data_key="telefono")
    canton = fields.Str(data_key="canton")
    provincia = fields.Str(data_key="provincia")
    total = fields.Decimal(data_key="total", places=2, as_string=True)
    creado_en = fields.Str(data_key="creadoEn", allow_none=True)
    actualizado_en = fields.Str(data_key="actualizadoEn", allow_none=True)


class PedidoDetalleSchema(Schema):
    """Fase 2 - Etapa 2 del frontend: vista de detalle de un pedido."""

    id_local = fields.Int(data_key="idLocal")
    id_rocketfy = fields.Int(data_key="idRocketfy", allow_none=True)
    estado_local = fields.Str(data_key="estadoLocal")
    status_id_rocketfy = fields.Int(data_key="statusIdRocketfy", allow_none=True)
    mensaje_error = fields.Str(data_key="mensajeError", allow_none=True)
    nombre_cliente = fields.Str(data_key="nombreCliente")
    telefono = fields.Str(data_key="telefono")
    direccion = fields.Str(data_key="direccion")
    direccion_2 = fields.Str(data_key="direccion2")
    canton = fields.Str(data_key="canton")
    provincia = fields.Str(data_key="provincia")
    codigo_postal = fields.Str(data_key="codigoPostal", allow_none=True)
    total = fields.Decimal(data_key="total", places=2, as_string=True)
    no_contra_entrega = fields.Bool(data_key="noContraEntrega")
    observaciones_transportista = fields.Str(data_key="observacionesTransportista")
    lineas = fields.List(fields.Nested(LineaPedidoSchema), data_key="lineas")
    creado_en = fields.Str(data_key="creadoEn", allow_none=True)
    confirmado_en = fields.Str(data_key="confirmadoEn", allow_none=True)
    actualizado_en = fields.Str(data_key="actualizadoEn", allow_none=True)


crear_pedido_input_schema = CrearPedidoInputSchema()
modificar_pedido_input_schema = ModificarPedidoInputSchema()
pedido_response_schema = PedidoResponseSchema()
pedido_resumen_schema = PedidoResumenSchema()
pedido_detalle_schema = PedidoDetalleSchema()
