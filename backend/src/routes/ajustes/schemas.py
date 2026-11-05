from decimal import Decimal

from marshmallow import EXCLUDE, Schema, ValidationError, fields, validate, validates_schema

# Topes de cordura (no reglas de negocio): evitan un cero de más al teclear.
# Son Decimal a propósito: comparar un Decimal con un float (99.99) falla por la
# representación binaria del float.
MAX_DINERO = Decimal("1000")
MAX_PORCENTAJE = Decimal("99.99")
CERO = Decimal("0")
MAX_TOPE_REDACCIONES = 200
MAX_TOPE_PRUEBAS = 1000
REDONDEOS = ("terminado_99", "ninguno")


class GuardarAjustesInputSchema(Schema):
    """PUT: viajan los seis ajustes completos. Las claves del resultado ya son
    los nombres de columna de `ajustes_negocio`."""

    class Meta:
        unknown = EXCLUDE

    margen_minimo_pct = fields.Decimal(
        data_key="margenMinimoPct", required=True, places=2, as_string=False,
        validate=validate.Range(min=CERO, max=MAX_PORCENTAJE),
    )
    margen_objetivo_pct = fields.Decimal(
        data_key="margenObjetivoPct", required=True, places=2, as_string=False,
        validate=validate.Range(min=CERO, max=MAX_PORCENTAJE),
    )
    envio_estimado = fields.Decimal(
        data_key="envioEstimado", required=True, places=2, as_string=False,
        validate=validate.Range(min=CERO, max=MAX_DINERO),
    )
    otros_costos_fijos = fields.Decimal(
        data_key="otrosCostosFijos", required=True, places=2, as_string=False,
        validate=validate.Range(min=CERO, max=MAX_DINERO),
    )
    otros_costos_pct = fields.Decimal(
        data_key="otrosCostosPct", required=True, places=2, as_string=False,
        validate=validate.Range(min=CERO, max=MAX_PORCENTAJE),
    )
    redondeo = fields.Str(required=True, validate=validate.OneOf(REDONDEOS))
    # Opcional: si no viene, se conserva el tope guardado (ver COLUMNAS_OPCIONALES).
    # strict: solo enteros (sin esto, 2.5 se convertiría en 2 sin avisar).
    tope_redacciones_dia = fields.Int(
        data_key="topeRedaccionesDia", strict=True, validate=validate.Range(min=1, max=MAX_TOPE_REDACCIONES)
    )
    tope_pruebas_dia = fields.Int(
        data_key="topePruebasDia", strict=True, validate=validate.Range(min=1, max=MAX_TOPE_PRUEBAS)
    )

    @validates_schema
    def _coherencia(self, data, **kwargs):
        minimo, objetivo = data.get("margen_minimo_pct"), data.get("margen_objetivo_pct")
        otros = data.get("otros_costos_pct")
        if minimo is not None and objetivo is not None and objetivo < minimo:
            raise ValidationError("El margen objetivo no puede ser menor que el mínimo.", "margenObjetivoPct")
        if objetivo is not None and otros is not None and objetivo + otros >= 100:
            raise ValidationError(
                "El margen objetivo más los otros costos en porcentaje deben sumar menos de 100 %.",
                "otrosCostosPct",
            )


class CalibracionEnvioSchema(Schema):
    observaciones = fields.Int()
    minimo = fields.Str()
    mediana = fields.Str()
    maximo = fields.Str()


class AjustesRespuestaSchema(Schema):
    margen_minimo_pct = fields.Str(data_key="margenMinimoPct")
    margen_objetivo_pct = fields.Str(data_key="margenObjetivoPct")
    envio_estimado = fields.Str(data_key="envioEstimado")
    otros_costos_fijos = fields.Str(data_key="otrosCostosFijos")
    otros_costos_pct = fields.Str(data_key="otrosCostosPct")
    redondeo = fields.Str()
    tope_redacciones_dia = fields.Int(data_key="topeRedaccionesDia")
    tope_pruebas_dia = fields.Int(data_key="topePruebasDia")
    confirmado = fields.Bool()
    actualizado_por = fields.Str(data_key="actualizadoPor", allow_none=True)
    actualizado_en = fields.Str(data_key="actualizadoEn", allow_none=True)
    calibracion_envio = fields.Nested(CalibracionEnvioSchema, data_key="calibracionEnvio", allow_none=True)


guardar_input_schema = GuardarAjustesInputSchema()
respuesta_schema = AjustesRespuestaSchema()
