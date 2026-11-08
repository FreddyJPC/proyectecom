from flask import jsonify, request
from marshmallow import EXCLUDE, Schema, ValidationError, fields, validate

from . import categorias_bp
from .repository import CategoriaRepository, CategoriaYaExisteError


class CategoriaSchema(Schema):
    id = fields.Int()
    nombre = fields.Str()
    activo = fields.Bool()
    productos = fields.Int()


class CrearCategoriaInput(Schema):
    class Meta:
        unknown = EXCLUDE

    nombre = fields.Str(required=True, validate=validate.Length(min=1, max=60))


class EditarCategoriaInput(Schema):
    class Meta:
        unknown = EXCLUDE

    nombre = fields.Str(validate=validate.Length(min=1, max=60))
    activo = fields.Bool()


_salida = CategoriaSchema()


@categorias_bp.get("")
def listar_categorias():
    incluir = request.args.get("incluirInactivas", "false").lower() == "true"
    return jsonify(_salida.dump(CategoriaRepository.listar(incluir), many=True)), 200


@categorias_bp.post("")
def crear_categoria():
    try:
        datos = CrearCategoriaInput().load(request.get_json(force=True, silent=True) or {})
    except ValidationError as exc:
        return jsonify(error="Datos inválidos.", detalle=exc.messages), 422
    nombre = datos["nombre"].strip()
    if not nombre:
        return jsonify(error="Datos inválidos.", detalle={"nombre": ["El nombre no puede estar vacío."]}), 422
    try:
        categoria = CategoriaRepository.crear(nombre)
    except CategoriaYaExisteError as exc:
        return jsonify(error=str(exc)), 409
    return jsonify(_salida.dump({**categoria, "productos": 0})), 201


@categorias_bp.patch("/<int:categoria_id>")
def editar_categoria(categoria_id: int):
    try:
        datos = EditarCategoriaInput().load(request.get_json(force=True, silent=True) or {})
    except ValidationError as exc:
        return jsonify(error="Datos inválidos.", detalle=exc.messages), 422
    nombre = datos["nombre"].strip() if "nombre" in datos else None
    if nombre == "":
        return jsonify(error="Datos inválidos.", detalle={"nombre": ["El nombre no puede estar vacío."]}), 422
    try:
        categoria = CategoriaRepository.actualizar(categoria_id, nombre, datos.get("activo"))
    except CategoriaYaExisteError as exc:
        return jsonify(error=str(exc)), 409
    if categoria is None:
        return jsonify(error=f"No existe la categoría {categoria_id}."), 404
    completa = next((c for c in CategoriaRepository.listar(incluir_inactivas=True) if c["id"] == categoria_id), categoria)
    return jsonify(_salida.dump({"productos": 0, **completa})), 200
