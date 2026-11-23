"""Esquemas de entrada y salida de la API de «Inmuebles» (camelCase hacia el frontend; el dinero viaja como string)."""
from marshmallow import EXCLUDE, Schema, fields, validate

from .logica import ESTADOS_INMUEBLE, ESTADOS_VISITA, OPERACIONES, TIPOS, USOS


def _texto(maximo: int, **kw):
    return fields.Str(allow_none=True, validate=validate.Length(max=maximo), **kw)


def _decimal(maximo, **kw):
    return fields.Decimal(allow_none=True, as_string=True, validate=validate.Range(min=0, max=maximo), **kw)


class InmuebleInput(Schema):
    """Todos los campos son opcionales: al editar se manda solo lo que cambió."""

    class Meta:
        unknown = EXCLUDE

    codigo = fields.Str(validate=[validate.Length(min=2, max=30), validate.Regexp(r"^[A-Za-z0-9 _-]+$", error="Solo letras, números y guiones.")])
    titulo = fields.Str(validate=validate.Length(min=3, max=120))
    tipo = fields.Str(validate=validate.OneOf(TIPOS))
    operacion = fields.Str(validate=validate.OneOf(OPERACIONES))
    precio = _decimal(100_000_000)
    mostrar_precio = fields.Bool(data_key="mostrarPrecio")
    precio_negociable = fields.Bool(allow_none=True, data_key="precioNegociable")
    ciudad = _texto(80)
    sector = _texto(120)
    direccion = _texto(250)
    referencia_llegada = _texto(600, data_key="referenciaLlegada")
    latitud = fields.Decimal(allow_none=True, as_string=True, validate=validate.Range(min=-90, max=90))
    longitud = fields.Decimal(allow_none=True, as_string=True, validate=validate.Range(min=-180, max=180))
    terreno_m2 = _decimal(10_000_000, data_key="terrenoM2")
    construccion_m2 = _decimal(1_000_000, data_key="construccionM2")
    frente_m = _decimal(100_000, data_key="frenteM")
    fondo_m = _decimal(100_000, data_key="fondoM")
    pisos = fields.Int(allow_none=True, validate=validate.Range(min=0, max=200))
    habitaciones = fields.Int(allow_none=True, validate=validate.Range(min=0, max=200))
    banos = _decimal(200)
    parqueaderos = fields.Int(allow_none=True, validate=validate.Range(min=0, max=500))
    uso = fields.Str(allow_none=True, validate=validate.OneOf(USOS))
    descripcion = _texto(3000)
    caracteristicas = _texto(2000)
    servicios = _texto(1000)
    documentacion = _texto(1000)
    preguntas_frecuentes = _texto(5000, data_key="preguntasFrecuentes")
    temas_no_responder = _texto(1500, data_key="temasNoResponder")
    horarios_visita = _texto(500, data_key="horariosVisita")
    encargado_visitas = _texto(120, data_key="encargadoVisitas")
    notas_internas = _texto(2000, data_key="notasInternas")


class EstadoInput(Schema):
    class Meta:
        unknown = EXCLUDE

    estado = fields.Str(required=True, validate=validate.OneOf(ESTADOS_INMUEBLE))


class MaterialInput(Schema):
    class Meta:
        unknown = EXCLUDE

    storage_path = fields.Str(required=True, data_key="storagePath", validate=validate.Length(min=3, max=200))


class OrdenInput(Schema):
    class Meta:
        unknown = EXCLUDE

    ids = fields.List(fields.Int(strict=True), required=True, validate=validate.Length(max=100))


class AnuncioInput(Schema):
    class Meta:
        unknown = EXCLUDE

    id_anuncio = fields.Str(required=True, data_key="idAnuncio", validate=validate.Length(min=5, max=40))
    nombre = _texto(120)


class MaterialSchema(Schema):
    id = fields.Int()
    url = fields.Str()
    storage_path = fields.Str(data_key="storagePath")
    orden = fields.Int()
    tipo = fields.Str()


class AnuncioSchema(Schema):
    id_anuncio = fields.Str(data_key="idAnuncio")
    nombre = fields.Str(allow_none=True)
    creado_en = fields.DateTime(data_key="creadoEn")


class _InmuebleBase(Schema):
    id = fields.Int()
    codigo = fields.Str()
    titulo = fields.Str()
    tipo = fields.Str()
    operacion = fields.Str()
    estado = fields.Str()
    precio = fields.Decimal(as_string=True, allow_none=True)
    mostrar_precio = fields.Bool(data_key="mostrarPrecio")
    precio_negociable = fields.Bool(allow_none=True, data_key="precioNegociable")
    ciudad = fields.Str(allow_none=True)
    sector = fields.Str(allow_none=True)
    direccion = fields.Str(allow_none=True)
    habitaciones = fields.Int(allow_none=True)
    banos = fields.Decimal(as_string=True, allow_none=True)
    terreno_m2 = fields.Decimal(as_string=True, allow_none=True, data_key="terrenoM2")
    construccion_m2 = fields.Decimal(as_string=True, allow_none=True, data_key="construccionM2")
    actualizado_en = fields.DateTime(data_key="actualizadoEn")


class InmuebleResumenSchema(_InmuebleBase):
    portada_url = fields.Str(allow_none=True, data_key="portadaUrl")
    portada_path = fields.Str(allow_none=True, data_key="portadaPath")
    visitas_por_confirmar = fields.Int(data_key="visitasPorConfirmar")
    visitas_proximas = fields.Int(data_key="visitasProximas")


class InmuebleDetalleSchema(_InmuebleBase):
    referencia_llegada = fields.Str(allow_none=True, data_key="referenciaLlegada")
    latitud = fields.Decimal(as_string=True, allow_none=True)
    longitud = fields.Decimal(as_string=True, allow_none=True)
    frente_m = fields.Decimal(as_string=True, allow_none=True, data_key="frenteM")
    fondo_m = fields.Decimal(as_string=True, allow_none=True, data_key="fondoM")
    pisos = fields.Int(allow_none=True)
    parqueaderos = fields.Int(allow_none=True)
    uso = fields.Str(allow_none=True)
    descripcion = fields.Str(allow_none=True)
    caracteristicas = fields.Str(allow_none=True)
    servicios = fields.Str(allow_none=True)
    documentacion = fields.Str(allow_none=True)
    preguntas_frecuentes = fields.Str(allow_none=True, data_key="preguntasFrecuentes")
    temas_no_responder = fields.Str(allow_none=True, data_key="temasNoResponder")
    horarios_visita = fields.Str(allow_none=True, data_key="horariosVisita")
    encargado_visitas = fields.Str(allow_none=True, data_key="encargadoVisitas")
    notas_internas = fields.Str(allow_none=True, data_key="notasInternas")
    creado_en = fields.DateTime(data_key="creadoEn")
    material = fields.List(fields.Nested(MaterialSchema))
    anuncios = fields.List(fields.Nested(AnuncioSchema))
    faltantes = fields.List(fields.Str())
    carpeta = fields.Str()


class VisitaSchema(Schema):
    id = fields.Int()
    inmueble_id = fields.Int(data_key="inmuebleId")
    inmueble_titulo = fields.Str(data_key="inmuebleTitulo")
    inmueble_codigo = fields.Str(data_key="inmuebleCodigo")
    conversacion_id = fields.Int(allow_none=True, data_key="conversacionId")
    nombre_cliente = fields.Str(allow_none=True, data_key="nombreCliente")
    telefono = fields.Str(allow_none=True)
    estado = fields.Str()
    preferencia_cliente = fields.Str(allow_none=True, data_key="preferenciaCliente")
    personas = fields.Int(allow_none=True)
    fecha_hora = fields.DateTime(allow_none=True, data_key="fechaHora")
    encargado = fields.Str(allow_none=True)
    notas = fields.Str(allow_none=True)
    motivo_cancelacion = fields.Str(allow_none=True, data_key="motivoCancelacion")
    creada_por = fields.Str(data_key="creadaPor")
    creado_en = fields.DateTime(data_key="creadoEn")
    confirmada_en = fields.DateTime(allow_none=True, data_key="confirmadaEn")
    avisado_cliente_en = fields.DateTime(allow_none=True, data_key="avisadoClienteEn")
    ventana_abierta = fields.Bool(data_key="ventanaAbierta")
    ventana_expira_en = fields.DateTime(allow_none=True, data_key="ventanaExpiraEn")


class VisitaCrearInput(Schema):
    class Meta:
        unknown = EXCLUDE

    inmueble_id = fields.Int(required=True, data_key="inmuebleId")
    nombre_cliente = _texto(120, data_key="nombreCliente")
    telefono = _texto(30)
    preferencia_cliente = _texto(300, data_key="preferenciaCliente")
    personas = fields.Int(allow_none=True, validate=validate.Range(min=1, max=50))
    # Con zona horaria (el frontend manda la hora de Ecuador con -05:00). Sin fecha, la visita queda «por confirmar».
    fecha_hora = fields.AwareDateTime(allow_none=True, data_key="fechaHora")
    encargado = _texto(120)
    notas = _texto(1000)


class VisitaConfirmarInput(Schema):
    class Meta:
        unknown = EXCLUDE

    fecha_hora = fields.AwareDateTime(required=True, data_key="fechaHora")
    encargado = _texto(120)
    notas = _texto(1000)


class VisitaEstadoInput(Schema):
    class Meta:
        unknown = EXCLUDE

    estado = fields.Str(required=True, validate=validate.OneOf(ESTADOS_VISITA))
    motivo = _texto(300)


class VisitaNotasInput(Schema):
    class Meta:
        unknown = EXCLUDE

    notas = _texto(1000)
    encargado = _texto(120)


class AvisarInput(Schema):
    class Meta:
        unknown = EXCLUDE

    texto = _texto(1000)


class NumeroSchema(Schema):
    phone_number_id = fields.Str(data_key="phoneNumberId")
    nombre = fields.Str()
    telefono_visible = fields.Str(allow_none=True, data_key="telefonoVisible")
    asistente = fields.Str()
    activo = fields.Bool()
    es_principal = fields.Bool(data_key="esPrincipal")


class NumeroInput(Schema):
    class Meta:
        unknown = EXCLUDE

    phone_number_id = fields.Str(required=True, data_key="phoneNumberId", validate=validate.Length(min=5, max=30))
    nombre = fields.Str(required=True, validate=validate.Length(min=1, max=80))
    telefono_visible = _texto(30, data_key="telefonoVisible")
    asistente = fields.Str(required=True, validate=validate.OneOf(("ventas", "inmuebles")))
    activo = fields.Bool(load_default=True)


class AsistenteConversacionInput(Schema):
    class Meta:
        unknown = EXCLUDE

    asistente = fields.Str(required=True, validate=validate.OneOf(("ventas", "inmuebles")))
    inmueble_id = fields.Int(allow_none=True, data_key="inmuebleId")
