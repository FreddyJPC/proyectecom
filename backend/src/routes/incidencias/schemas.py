from marshmallow import Schema, fields


class EventoWebhookSchema(Schema):
    id = fields.Int()
    id_rocketfy = fields.Int(data_key="idRocketfy")
    shopify_order_id = fields.Int(data_key="idLocal", allow_none=True)
    status_id = fields.Int(data_key="statusId")
    status_name = fields.Str(data_key="statusName", allow_none=True)
    details = fields.Str(data_key="details", allow_none=True)
    tracking_code = fields.Str(data_key="trackingCode", allow_none=True)
    tracking_url = fields.Str(data_key="trackingUrl", allow_none=True)
    shipping_company = fields.Str(data_key="shippingCompany", allow_none=True)
    event_date = fields.DateTime(data_key="eventDate", allow_none=True)
    recibido_en = fields.DateTime(data_key="recibidoEn", allow_none=True)


class AlertaStockSchema(Schema):
    id = fields.Int()
    sku = fields.Str()
    tipo = fields.Str()
    detalle = fields.Dict()
    creado_en = fields.DateTime(data_key="creadoEn", allow_none=True)


evento_webhook_schema = EventoWebhookSchema()
alerta_stock_schema = AlertaStockSchema()
