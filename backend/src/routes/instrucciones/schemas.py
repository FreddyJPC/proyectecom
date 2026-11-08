from marshmallow import EXCLUDE, Schema, fields, validate

MAX_NOTA = 200


class GuardarBorradorInputSchema(Schema):
    """PUT .../borrador: todas las secciones editables. Su contenido lo valida
    src/routes/whatsapp/instrucciones.py (quien sabe qué secciones hay y qué reglas cumplen)."""

    class Meta:
        unknown = EXCLUDE

    secciones = fields.Dict(keys=fields.Str(), values=fields.Raw(), required=True)
    nota = fields.Str(load_default=None, allow_none=True, validate=validate.Length(max=MAX_NOTA))


class PublicarInputSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    nota = fields.Str(load_default=None, allow_none=True, validate=validate.Length(max=MAX_NOTA))


class SeccionSchema(Schema):
    id = fields.Str()
    nombre = fields.Str()
    ayuda = fields.Str()
    editable = fields.Bool()
    maximo = fields.Int()
    original = fields.Str()
    vigente = fields.Str()
    borrador = fields.Str(allow_none=True)


class VersionSchema(Schema):
    id = fields.Int()
    estado = fields.Str()
    nota = fields.Str(allow_none=True)
    creado_por = fields.Str(data_key="creadoPor", allow_none=True)
    creado_en = fields.Str(data_key="creadoEn")
    publicada_en = fields.Str(data_key="publicadaEn", allow_none=True)


class InstruccionesSchema(Schema):
    secciones = fields.List(fields.Nested(SeccionSchema))
    usando = fields.Str()
    publicada = fields.Nested(VersionSchema, allow_none=True)
    borrador = fields.Nested(VersionSchema, allow_none=True)
    versiones = fields.List(fields.Nested(VersionSchema))
    maximo_total = fields.Int(data_key="maximoTotal")
    caracteres_fijos = fields.Int(data_key="caracteresFijos")


guardar_borrador_input_schema = GuardarBorradorInputSchema()
publicar_input_schema = PublicarInputSchema()
instrucciones_schema = InstruccionesSchema()
