from flask import jsonify

from src.catalogs.ecuador_locations import get_catalog

from . import catalogos_bp


@catalogos_bp.get("/ubicaciones")
def listar_provincias():
    catalogo = get_catalog()
    return jsonify(provincias=catalogo.listar_provincias()), 200


@catalogos_bp.get("/ubicaciones/<provincia>/cantones")
def listar_cantones(provincia: str):
    catalogo = get_catalog()
    cantones = catalogo.listar_cantones(provincia)
    if not cantones:
        return jsonify(error=f"Provincia '{provincia}' no existe en el catálogo."), 404
    return jsonify(provincia=provincia, cantones=cantones), 200
