from src.catalogs.ecuador_locations import EcuadorLocationsCatalog, get_catalog


def test_carga_832_cantones_y_24_provincias():
    catalogo = EcuadorLocationsCatalog()
    assert len(catalogo) == 832
    assert len(catalogo.listar_provincias()) == 24


def test_resuelve_ignorando_mayusculas_y_tildes():
    # Ejemplo textual de la sección 4.2 del doc del proveedor
    catalogo = EcuadorLocationsCatalog()
    r1 = catalogo.resolver("Pichincha", "QUITO")
    r2 = catalogo.resolver("pichincha", "quito")
    assert r1 is not None
    assert r2 is not None
    assert r1.city_id == r2.city_id


def test_no_resuelve_canton_inexistente():
    # Ejemplo textual de la sección 4.2: "Quito Norte" no existe en el catálogo
    catalogo = EcuadorLocationsCatalog()
    assert catalogo.resolver("Pichincha", "Quito Norte") is None


def test_no_resuelve_provincia_inexistente():
    catalogo = EcuadorLocationsCatalog()
    assert catalogo.resolver("Provincia Inventada", "Quito") is None


def test_listar_cantones_de_una_provincia():
    catalogo = EcuadorLocationsCatalog()
    cantones = catalogo.listar_cantones("Pichincha")
    assert "QUITO" in cantones
    assert cantones == sorted(cantones)


def test_get_catalog_devuelve_singleton_cacheado():
    a = get_catalog()
    b = get_catalog()
    assert a is b
