from marshmallow import EXCLUDE, Schema, ValidationError, fields, post_load, validate, validates_schema

from .verificacion import METODOS_PAGO_VALIDOS

# Todo lo que se escribe aquí termina en el system prompt de Victoria, que se
# envía completo en CADA mensaje: por eso hay límites de largo.
MAX_NOMBRE = 120
MAX_DESCRIPCION = 1500
MAX_VARIANTES = 300
MAX_TIEMPO_ENTREGA = 200
MAX_FAQ = 3000
MAX_TEMAS = 1000
MAX_NOTAS = 2000
MAX_UNIDADES_POR_PEDIDO = 20

_CAMPOS_OPCIONALES_QUE_SE_VACIAN = ("variantes", "preguntas_frecuentes", "temas_no_responder", "notas_internas")


class CrearProductoBotInputSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    sku = fields.Str(required=True, validate=validate.Length(min=1, max=100))


class EditarProductoBotInputSchema(Schema):
    """Solo se editan los campos que vengan en el cuerpo (PATCH). Las claves
    del resultado ya son los nombres de columna de `productos_bot`."""

    class Meta:
        unknown = EXCLUDE

    nombre = fields.Str(validate=validate.Length(min=1, max=MAX_NOMBRE))
    descripcion = fields.Str(validate=validate.Length(max=MAX_DESCRIPCION))
    precio = fields.Decimal(places=2, as_string=False)
    variantes = fields.Str(allow_none=True, validate=validate.Length(max=MAX_VARIANTES))
    tiempo_entrega = fields.Str(data_key="tiempoEntrega", validate=validate.Length(max=MAX_TIEMPO_ENTREGA))
    metodos_pago_aceptados = fields.List(
        fields.Str(validate=validate.OneOf(METODOS_PAGO_VALIDOS)),
        data_key="metodosPago",
        validate=validate.Length(min=1),
    )
    preguntas_frecuentes = fields.Str(
        data_key="preguntasFrecuentes", allow_none=True, validate=validate.Length(max=MAX_FAQ)
    )
    temas_no_responder = fields.Str(
        data_key="temasNoResponder", allow_none=True, validate=validate.Length(max=MAX_TEMAS)
    )
    max_unidades_por_pedido = fields.Int(
        data_key="maxUnidadesPorPedido", validate=validate.Range(min=1, max=MAX_UNIDADES_POR_PEDIDO)
    )
    notas_internas = fields.Str(data_key="notasInternas", allow_none=True, validate=validate.Length(max=MAX_NOTAS))
    # Precio de la competencia que el dueño anota a mano (opcional; null lo borra).
    precio_competencia = fields.Decimal(data_key="precioCompetencia", places=2, as_string=False, allow_none=True)

    @validates_schema
    def _precio_positivo(self, data, **kwargs):
        precio = data.get("precio")
        if precio is not None and precio <= 0:
            raise ValidationError("El precio debe ser mayor que cero.", "precio")
        competencia = data.get("precio_competencia")
        if competencia is not None and competencia <= 0:
            raise ValidationError("El precio de la competencia debe ser mayor que cero.", "precioCompetencia")

    @post_load
    def _normalizar(self, data, **kwargs):
        for clave, valor in list(data.items()):
            if isinstance(valor, str):
                data[clave] = valor.strip()
        for clave in _CAMPOS_OPCIONALES_QUE_SE_VACIAN:
            if clave in data and not data[clave]:
                data[clave] = None
        if "metodos_pago_aceptados" in data:
            unicos = []
            for metodo in data["metodos_pago_aceptados"]:
                if metodo not in unicos:
                    unicos.append(metodo)
            data["metodos_pago_aceptados"] = ", ".join(unicos)
        return data


class VerificacionSchema(Schema):
    bloqueos = fields.List(fields.Str())
    avisos = fields.List(fields.Str())


class HistorialSchema(Schema):
    accion = fields.Str()
    usuario = fields.Str(allow_none=True)
    cambios = fields.Dict(allow_none=True)
    creado_en = fields.Str(data_key="creadoEn", allow_none=True)


class ProductoBotResumenSchema(Schema):
    sku = fields.Str()
    nombre = fields.Str()
    estado = fields.Str()
    precio = fields.Str()
    costo_rocketfy = fields.Str(data_key="costoRocketfy", allow_none=True)
    stock_ultimo = fields.Int(data_key="stockUltimo", allow_none=True)
    max_unidades_por_pedido = fields.Int(data_key="maxUnidadesPorPedido")
    imagen_url = fields.Str(data_key="imagenUrl", allow_none=True)
    publicado_en = fields.Str(data_key="publicadoEn", allow_none=True)
    actualizado_en = fields.Str(data_key="actualizadoEn", allow_none=True)


class ProductoBotDetalleSchema(Schema):
    sku = fields.Str()
    nombre = fields.Str()
    estado = fields.Str()
    precio = fields.Str()
    costo_rocketfy = fields.Str(data_key="costoRocketfy", allow_none=True)
    precio_sugerido_rocketfy = fields.Str(data_key="precioSugeridoRocketfy", allow_none=True)
    stock_ultimo = fields.Int(data_key="stockUltimo", allow_none=True)
    stock_actualizado_en = fields.Str(data_key="stockActualizadoEn", allow_none=True)
    peso_kg = fields.Str(data_key="pesoKg", allow_none=True)
    imagen_url = fields.Str(data_key="imagenUrl", allow_none=True)
    rocketfy_product_id = fields.Int(data_key="rocketfyProductId", allow_none=True)
    descripcion = fields.Str()
    variantes = fields.Str(allow_none=True)
    tiempo_entrega = fields.Str(data_key="tiempoEntrega")
    metodos_pago = fields.List(fields.Str(), data_key="metodosPago")
    preguntas_frecuentes = fields.Str(data_key="preguntasFrecuentes", allow_none=True)
    temas_no_responder = fields.Str(data_key="temasNoResponder", allow_none=True)
    max_unidades_por_pedido = fields.Int(data_key="maxUnidadesPorPedido")
    notas_internas = fields.Str(data_key="notasInternas", allow_none=True)
    publicado_en = fields.Str(data_key="publicadoEn", allow_none=True)
    publicado_por = fields.Str(data_key="publicadoPor", allow_none=True)
    creado_en = fields.Str(data_key="creadoEn", allow_none=True)
    actualizado_en = fields.Str(data_key="actualizadoEn", allow_none=True)
    verificacion = fields.Nested(VerificacionSchema)
    precio_competencia = fields.Str(data_key="precioCompetencia", allow_none=True)
    historial = fields.List(fields.Nested(HistorialSchema))


class NivelPrecioSchema(Schema):
    clave = fields.Str()
    nombre = fields.Str()
    precio = fields.Str()
    ganancia = fields.Str()
    margen_pct = fields.Str(data_key="margenPct")


class EvaluacionPrecioSchema(Schema):
    precio = fields.Str()
    ganancia = fields.Str()
    margen_pct = fields.Str(data_key="margenPct")
    bajo_piso = fields.Bool(data_key="bajoPiso")
    bajo_margen_minimo = fields.Bool(data_key="bajoMargenMinimo")


class RecomendacionPrecioSchema(Schema):
    ajustes_confirmados = fields.Bool(data_key="ajustesConfirmados")
    costo = fields.Str(allow_none=True)
    piso = fields.Str()
    envio_estimado = fields.Str(data_key="envioEstimado")
    otros_costos_fijos = fields.Str(data_key="otrosCostosFijos")
    otros_costos_pct = fields.Str(data_key="otrosCostosPct")
    margen_minimo_pct = fields.Str(data_key="margenMinimoPct")
    margen_objetivo_pct = fields.Str(data_key="margenObjetivoPct")
    precio_sugerido = fields.Str(data_key="precioSugerido", allow_none=True)
    precio_competencia = fields.Str(data_key="precioCompetencia", allow_none=True)
    niveles = fields.List(fields.Nested(NivelPrecioSchema))
    evaluacion = fields.Nested(EvaluacionPrecioSchema, allow_none=True)
    avisos = fields.List(fields.Str())


crear_input_schema = CrearProductoBotInputSchema()
editar_input_schema = EditarProductoBotInputSchema()
resumen_lista_schema = ProductoBotResumenSchema(many=True)
detalle_schema = ProductoBotDetalleSchema()
recomendacion_precio_schema = RecomendacionPrecioSchema()
