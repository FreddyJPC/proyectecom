from marshmallow import EXCLUDE, Schema, fields


class GuardarParametroInputSchema(Schema):
    """PUT: viaja solo el valor. Su tipo y su rango los valida el catálogo
    (src/config/parametros/catalogo.py), que es quien sabe de qué parámetro se trata."""

    class Meta:
        unknown = EXCLUDE

    valor = fields.Raw(required=True, allow_none=False)


class OpcionSchema(Schema):
    valor = fields.Str()
    etiqueta = fields.Str()
    nota = fields.Str()


class ParametroSchema(Schema):
    clave = fields.Str()
    nombre = fields.Str()
    para_que_sirve = fields.Str(data_key="paraQueSirve")
    tipo = fields.Str()
    valor = fields.Raw()
    origen = fields.Str()
    valor_original = fields.Raw(data_key="valorOriginal")
    valor_app = fields.Raw(data_key="valorApp", allow_none=True)
    variable_servidor = fields.Str(data_key="variableServidor", allow_none=True)
    valor_servidor = fields.Raw(data_key="valorServidor", allow_none=True)
    minimo = fields.Int(allow_none=True)
    maximo = fields.Int(allow_none=True)
    largo_maximo = fields.Int(data_key="largoMaximo", allow_none=True)
    unidad = fields.Str()
    aplica = fields.Str()
    sensible = fields.Bool()
    aviso = fields.Str()
    opciones = fields.List(fields.Nested(OpcionSchema))
    avisos = fields.List(fields.Str())
    actualizado_por = fields.Str(data_key="actualizadoPor", allow_none=True)
    actualizado_en = fields.Str(data_key="actualizadoEn", allow_none=True)


class GrupoSchema(Schema):
    clave = fields.Str()
    nombre = fields.Str()
    descripcion = fields.Str()
    parametros = fields.List(fields.Nested(ParametroSchema))


class ParametrosRespuestaSchema(Schema):
    grupos = fields.List(fields.Nested(GrupoSchema))


class CambioSchema(Schema):
    clave = fields.Str()
    nombre = fields.Str()
    valor_anterior = fields.Str(data_key="valorAnterior", allow_none=True)
    valor_nuevo = fields.Str(data_key="valorNuevo", allow_none=True)
    usuario = fields.Str(allow_none=True)
    creado_en = fields.Str(data_key="creadoEn")


guardar_input_schema = GuardarParametroInputSchema()
parametro_schema = ParametroSchema()
respuesta_schema = ParametrosRespuestaSchema()
cambio_schema = CambioSchema(many=True)
