from marshmallow import EXCLUDE, Schema, fields, validate


class UltimoMensajeSchema(Schema):
    rol = fields.Str()
    contenido = fields.Str()
    creado_en = fields.Str(data_key="creadoEn", allow_none=True)


class ConversacionResumenSchema(Schema):
    id = fields.Int()
    telefono = fields.Str()
    nombre_cliente = fields.Str(data_key="nombreCliente", allow_none=True)
    origen = fields.Str()
    estado = fields.Str()
    producto_interes = fields.Str(data_key="productoInteres", allow_none=True)
    sin_revisar = fields.Bool(data_key="sinRevisar")
    ultimo_mensaje = fields.Nested(UltimoMensajeSchema, data_key="ultimoMensaje", allow_none=True)
    creada_en = fields.Str(data_key="creadaEn", allow_none=True)
    actualizada_en = fields.Str(data_key="actualizadaEn", allow_none=True)


class TotalesPorFiltroRapidoSchema(Schema):
    escaladas = fields.Int()
    escaladas_sin_revisar = fields.Int(data_key="escaladasSinRevisar")
    esperando_pago = fields.Int(data_key="esperandoPago")


class ListaConversacionesSchema(Schema):
    items = fields.List(fields.Nested(ConversacionResumenSchema))
    total = fields.Int()
    page = fields.Int()
    page_size = fields.Int(data_key="pageSize")
    totales_por_filtro_rapido = fields.Nested(TotalesPorFiltroRapidoSchema, data_key="totalesPorFiltroRapido")


class LeadSchema(Schema):
    nombre_cliente = fields.Str(data_key="nombreCliente", allow_none=True)
    direccion = fields.Str(allow_none=True)
    canton = fields.Str(allow_none=True)
    provincia = fields.Str(allow_none=True)
    producto_sku = fields.Str(data_key="productoSku", allow_none=True)
    producto_nombre = fields.Str(data_key="productoNombre", allow_none=True)
    producto_variante = fields.Str(data_key="productoVariante", allow_none=True)
    # as_string=True: misma convención de moneda que pedidos/schemas.py
    # (nunca float en el wire tampoco, aunque el ejemplo del encargo
    # mostraba un número -- las convenciones obligatorias explícitas
    # pesan más que un ejemplo ilustrativo).
    total = fields.Decimal(places=2, as_string=True, allow_none=True)
    metodo_pago = fields.Str(data_key="metodoPago", allow_none=True)
    estado_pago = fields.Str(data_key="estadoPago", allow_none=True)
    estado = fields.Str(allow_none=True)
    id_pedido_local = fields.Int(data_key="idPedidoLocal", allow_none=True)
    id_pedido_rocketfy = fields.Int(data_key="idPedidoRocketfy", allow_none=True)


class ConversacionDetalleSchema(Schema):
    id = fields.Int()
    telefono = fields.Str()
    origen = fields.Str()
    estado = fields.Str()
    id_anuncio = fields.Str(data_key="idAnuncio", allow_none=True)
    notas_internas = fields.Str(data_key="notasInternas", allow_none=True)
    ventana_abierta = fields.Bool(data_key="ventanaAbierta")
    ventana_expira_en = fields.Str(data_key="ventanaExpiraEn", allow_none=True)
    creada_en = fields.Str(data_key="creadaEn", allow_none=True)
    actualizada_en = fields.Str(data_key="actualizadaEn", allow_none=True)


class MensajeSchema(Schema):
    id = fields.Int()
    rol = fields.Str()
    contenido = fields.Str()
    tipo = fields.Str()
    creado_en = fields.Str(data_key="creadoEn", allow_none=True)


class DetalleCompletoSchema(Schema):
    conversacion = fields.Nested(ConversacionDetalleSchema)
    lead = fields.Nested(LeadSchema, allow_none=True)
    mensajes = fields.List(fields.Nested(MensajeSchema))


class EnviarMensajeInputSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    contenido = fields.Str(required=True, validate=validate.Length(min=1))


class NotasInputSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    notas_internas = fields.Str(data_key="notasInternas", allow_none=True, load_default=None)


conversacion_lista_schema = ListaConversacionesSchema()
conversacion_detalle_schema = DetalleCompletoSchema()
mensaje_schema = MensajeSchema()
enviar_mensaje_input_schema = EnviarMensajeInputSchema()
notas_input_schema = NotasInputSchema()
