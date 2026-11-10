from flask import jsonify, request
from marshmallow import EXCLUDE, Schema, ValidationError, fields, validate

from . import cuentas_bancarias_bp
from .repository import CuentaBancariaRepository, CuentaYaExisteError


class CuentaSchema(Schema):
    id = fields.Int()
    banco = fields.Str()
    tipo_cuenta = fields.Str(data_key="tipoCuenta")
    numero = fields.Str()
    titular = fields.Str()
    identificacion = fields.Str(allow_none=True)
    activa = fields.Bool()
    orden = fields.Int()


def _texto(max_largo: int, **kw):
    return fields.Str(validate=validate.Length(min=1, max=max_largo), **kw)


class CrearCuentaInput(Schema):
    class Meta:
        unknown = EXCLUDE

    banco = _texto(60, required=True)
    tipo_cuenta = _texto(60, required=True, data_key="tipoCuenta")
    numero = _texto(40, required=True)
    titular = _texto(120, required=True)
    identificacion = fields.Str(allow_none=True, validate=validate.Length(max=30))
    activa = fields.Bool(load_default=True)
    orden = fields.Int(allow_none=True, validate=validate.Range(min=0, max=1000))


class EditarCuentaInput(Schema):
    class Meta:
        unknown = EXCLUDE

    banco = _texto(60)
    tipo_cuenta = _texto(60, data_key="tipoCuenta")
    numero = _texto(40)
    titular = _texto(120)
    identificacion = fields.Str(allow_none=True, validate=validate.Length(max=30))
    activa = fields.Bool()
    orden = fields.Int(validate=validate.Range(min=0, max=1000))


_salida = CuentaSchema()


def _limpiar(datos: dict) -> dict:
    """Quita espacios sobrantes; una identificación vacía es «sin identificación»."""
    limpio = {}
    for clave, valor in datos.items():
        if isinstance(valor, str):
            valor = valor.strip()
            if clave == "identificacion":
                valor = valor or None
            elif not valor:
                raise ValidationError({clave: ["No puede estar vacío."]})
        limpio[clave] = valor
    return limpio


@cuentas_bancarias_bp.get("")
def listar_cuentas():
    return jsonify(_salida.dump(CuentaBancariaRepository.listar(), many=True)), 200


@cuentas_bancarias_bp.post("")
def crear_cuenta():
    try:
        datos = _limpiar(CrearCuentaInput().load(request.get_json(force=True, silent=True) or {}))
    except ValidationError as exc:
        return jsonify(error="Datos inválidos.", detalle=exc.messages), 422
    try:
        cuenta = CuentaBancariaRepository.crear(
            datos["banco"], datos["tipo_cuenta"], datos["numero"], datos["titular"],
            datos.get("identificacion"), datos.get("activa", True), datos.get("orden"),
        )
    except CuentaYaExisteError as exc:
        return jsonify(error=str(exc)), 409
    return jsonify(_salida.dump(cuenta)), 201


@cuentas_bancarias_bp.patch("/<int:cuenta_id>")
def editar_cuenta(cuenta_id: int):
    try:
        datos = _limpiar(EditarCuentaInput().load(request.get_json(force=True, silent=True) or {}))
    except ValidationError as exc:
        return jsonify(error="Datos inválidos.", detalle=exc.messages), 422
    try:
        cuenta = CuentaBancariaRepository.actualizar(cuenta_id, datos)
    except CuentaYaExisteError as exc:
        return jsonify(error=str(exc)), 409
    if cuenta is None:
        return jsonify(error=f"No existe la cuenta {cuenta_id}."), 404
    return jsonify(_salida.dump(cuenta)), 200


@cuentas_bancarias_bp.delete("/<int:cuenta_id>")
def borrar_cuenta(cuenta_id: int):
    if not CuentaBancariaRepository.borrar(cuenta_id):
        return jsonify(error=f"No existe la cuenta {cuenta_id}."), 404
    return jsonify(status="ok"), 200
