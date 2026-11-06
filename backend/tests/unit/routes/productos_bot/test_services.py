"""
Servicio de gestión de productos con un repositorio en memoria y un cliente de
Rocketfy falso: sin base de datos ni red.
"""
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from src.integrations.rocketfy import RocketfyRequestError
from src.routes.ajustes.dto import AjustesNegocio
from src.routes.productos.exceptions import SkuNoExisteEnRocketfyError
from src.routes.productos_bot.exceptions import (
    ProductoBotNoEncontradoError,
    ProductoBotYaExisteError,
    PublicacionBloqueadaError,
    SkuInvalidoError,
    TransicionInvalidaError,
)
from src.routes.productos_bot.services import ProductosBotService

AHORA = datetime(2026, 11, 5, 21, 0, tzinfo=timezone.utc)


def _fila(**cambios):
    fila = {
        "id": 1,
        "sku": "DEMO-1",
        "nombre": "Producto Demo",
        "descripcion": "Un buen producto.",
        "precio": Decimal("24.99"),
        "variantes": None,
        "tiempo_entrega": "2 a 4 días hábiles",
        "metodos_pago_aceptados": "contraentrega",
        "preguntas_frecuentes": "¿Trae cargador? Sí.",
        "temas_no_responder": None,
        "max_unidades_por_pedido": 1,
        "estado": "borrador",
        "activo": False,
        "rocketfy_product_id": 4821,
        "costo_rocketfy": Decimal("10.00"),
        "precio_sugerido_rocketfy": Decimal("29.90"),
        "stock_ultimo": 10,
        "stock_actualizado_en": AHORA,
        "peso_kg": Decimal("0.350"),
        "imagen_url": "https://img/1.png",
        "notas_internas": None,
        "publicado_en": None,
        "publicado_por": None,
        "creado_en": AHORA,
        "actualizado_en": AHORA,
    }
    fila.update(cambios)
    return fila


class RepoEnMemoria:
    """Imita al repositorio real, incluida la regla estado <-> activo."""

    def __init__(self, filas=()):
        self.filas = {f["sku"]: dict(f) for f in filas}
        self.historial = []

    def listar(self, incluir_archivados=False):
        return [dict(f) for f in self.filas.values() if incluir_archivados or f["estado"] != "archivado"]

    def obtener(self, sku):
        return dict(self.filas[sku]) if sku in self.filas else None

    def crear_borrador(self, sku, nombre, descripcion, precio, metodos_pago_aceptados, datos_rocketfy):
        fila = _fila(
            sku=sku, nombre=nombre, descripcion=descripcion, precio=precio, tiempo_entrega="",
            metodos_pago_aceptados=metodos_pago_aceptados, estado="borrador", activo=False, **datos_rocketfy,
        )
        self.filas[sku] = fila
        return dict(fila)

    def actualizar_campos(self, sku, campos):
        self.filas[sku].update(campos)
        return dict(self.filas[sku])

    def guardar_datos_rocketfy(self, sku, datos):
        self.filas[sku].update(datos)
        return dict(self.filas[sku])

    def cambiar_estado(self, sku, estado, usuario=None):
        fila = self.filas[sku]
        fila["estado"] = estado
        fila["activo"] = estado == "activo"
        if estado == "activo":
            fila["publicado_en"] = AHORA
            fila["publicado_por"] = usuario
        return dict(fila)

    def registrar_historial(self, sku, accion, usuario, cambios=None):
        self.historial.append({"sku": sku, "accion": accion, "usuario": usuario, "cambios": cambios, "creado_en": AHORA})

    def listar_historial(self, sku, limite=20):
        return [h for h in reversed(self.historial) if h["sku"] == sku][:limite]

    def pausar_por_agotado(self, sku):
        fila = self.filas.get(sku)
        if fila is None or fila["estado"] != "activo":
            return None
        fila["estado"], fila["activo"] = "agotado", False
        return dict(fila)

    def contar_pedidos_por_sku(self, dias=30):
        return dict(getattr(self, "pedidos", {}))

    def ultima_fecha_de(self, sku, accion):
        fechas = [h["creado_en"] for h in self.historial if h["sku"] == sku and h["accion"] == accion]
        return max(fechas) if fechas else None


class RocketfyFalso:
    def __init__(self, productos=None, error=None):
        self.productos = productos if productos is not None else [self.producto()]
        self.error = error
        self.consultas = []

    @staticmethod
    def producto(**cambios):
        producto = {
            "id": 4821, "name": "Reloj deportivo", "description": "<p>Resistente al agua.</p>\n<ul><li>GPS</li></ul>",
            "sku": "DEMO-1", "stock": 137, "price": "10.00", "suggested_price": "29.90",
            "weight": "0.35", "image_url": "https://img/reloj.png",
        }
        producto.update(cambios)
        return producto

    def listar_productos(self, q=None, page=1):
        self.consultas.append(q)
        if self.error is not None:
            raise self.error
        return {"data": self.productos}


class MonitoreoFalso:
    def __init__(self, vigilados=(), falla=False):
        self.vigilados = {sku: 8 for sku in vigilados}
        self.falla = falla
        self.upserts = []

    def listar(self, solo_activos=False):
        if self.falla:
            raise RuntimeError("base caída")
        return [{"sku": sku} for sku in self.vigilados]

    def upsert(self, sku, umbral):
        self.upserts.append((sku, umbral))
        self.vigilados[sku] = umbral


class AjustesFalsos:
    """Imita a AjustesService: devuelve los ajustes que se le den, sin base de datos."""

    def __init__(self, **cambios):
        self.ajustes = AjustesNegocio(**cambios)

    def obtener_ajustes(self):
        return self.ajustes


def _servicio(filas=(), productos=None, error=None, monitoreo=None, ajustes=None):
    repo = RepoEnMemoria(filas)
    rocketfy = RocketfyFalso(productos, error)
    monitoreo = monitoreo or MonitoreoFalso()
    servicio = ProductosBotService(
        client=rocketfy, repo=repo, monitoreo_repo=monitoreo, ajustes_service=ajustes or AjustesFalsos()
    )
    return servicio, repo, rocketfy, monitoreo


class TestCrearBorrador:
    def test_copia_los_datos_de_rocketfy_y_nace_como_borrador(self):
        servicio, repo, _, _ = _servicio()

        detalle = servicio.crear_borrador("DEMO-1", "freddy@ejemplo.com")

        fila = repo.filas["DEMO-1"]
        assert (fila["estado"], fila["activo"]) == ("borrador", False)
        assert detalle.nombre == "Reloj deportivo"
        assert detalle.costo_rocketfy == "10.00"
        assert detalle.precio_sugerido_rocketfy == "29.90"
        assert detalle.stock_ultimo == 137
        assert detalle.peso_kg == "0.350"
        assert detalle.rocketfy_product_id == 4821
        assert detalle.metodos_pago == ["contraentrega"]  # solo contraentrega al arrancar
        assert detalle.max_unidades_por_pedido == 1
        assert detalle.tiempo_entrega == ""  # lo debe poner la persona

    def test_el_precio_inicial_es_el_sugerido_o_el_costo_si_no_hay(self):
        servicio, repo, _, _ = _servicio()
        servicio.crear_borrador("DEMO-1", None)
        assert repo.filas["DEMO-1"]["precio"] == Decimal("29.90")

        servicio, repo, _, _ = _servicio(productos=[RocketfyFalso.producto(suggested_price=None)])
        servicio.crear_borrador("DEMO-1", None)
        assert repo.filas["DEMO-1"]["precio"] == Decimal("10.00")

    def test_usa_el_sku_tal_como_lo_escribe_rocketfy_no_como_lo_tecleo_la_persona(self):
        servicio, repo, rocketfy, _ = _servicio()

        servicio.crear_borrador("  demo-1 ", None)

        assert "DEMO-1" in repo.filas and "demo-1" not in repo.filas
        assert rocketfy.consultas == ["demo-1"]

    def test_ignora_productos_parecidos_que_devuelve_la_busqueda(self):
        otro = RocketfyFalso.producto(sku="DEMO-10", name="Otro")
        servicio, repo, _, _ = _servicio(productos=[otro, RocketfyFalso.producto()])
        servicio.crear_borrador("DEMO-1", None)
        assert repo.filas["DEMO-1"]["nombre"] == "Reloj deportivo"

    def test_la_descripcion_de_rocketfy_se_deja_como_texto_plano(self):
        servicio, repo, _, _ = _servicio(
            productos=[RocketfyFalso.producto(description="<p>Resistente &amp; ligero.</p>\n\n<ul><li>GPS</li></ul>")]
        )
        servicio.crear_borrador("DEMO-1", None)
        assert repo.filas["DEMO-1"]["descripcion"] == "Resistente & ligero. GPS"

    def test_una_descripcion_enorme_se_recorta(self):
        servicio, repo, _, _ = _servicio(productos=[RocketfyFalso.producto(description="palabra " * 500)])
        servicio.crear_borrador("DEMO-1", None)
        descripcion = repo.filas["DEMO-1"]["descripcion"]
        assert len(descripcion) <= 1500 and descripcion.endswith("…")

    def test_deja_constancia_en_el_historial(self):
        servicio, repo, _, _ = _servicio()
        servicio.crear_borrador("DEMO-1", "freddy@ejemplo.com")
        assert repo.historial == [
            {"sku": "DEMO-1", "accion": "creado", "usuario": "freddy@ejemplo.com", "cambios": {"desde": "rocketfy"}, "creado_en": AHORA}
        ]

    def test_sku_que_no_existe_en_rocketfy_no_crea_nada(self):
        servicio, repo, _, _ = _servicio(productos=[RocketfyFalso.producto(sku="OTRO")])
        with pytest.raises(SkuNoExisteEnRocketfyError):
            servicio.crear_borrador("DEMO-1", None)
        assert repo.filas == {}

    @pytest.mark.parametrize("sku", ["", "   ", "A/B", None])
    def test_sku_invalido(self, sku):
        servicio, repo, rocketfy, _ = _servicio()
        with pytest.raises(SkuInvalidoError):
            servicio.crear_borrador(sku, None)
        assert rocketfy.consultas == []  # ni siquiera se consulta a Rocketfy

    def test_si_ya_existe_no_se_crea_otro(self):
        servicio, repo, _, _ = _servicio(filas=[_fila(estado="archivado")])
        with pytest.raises(ProductoBotYaExisteError):
            servicio.crear_borrador("demo-1", None)

    def test_un_fallo_de_rocketfy_sube_sin_crear_nada(self):
        servicio, repo, _, _ = _servicio(error=RocketfyRequestError("timeout"))
        with pytest.raises(RocketfyRequestError):
            servicio.crear_borrador("DEMO-1", None)
        assert repo.filas == {}


class TestEditar:
    def test_guarda_solo_lo_que_cambia_y_deja_historial_con_antes_y_despues(self):
        servicio, repo, _, _ = _servicio(filas=[_fila()])

        detalle = servicio.editar(
            "DEMO-1", {"precio": Decimal("27.50"), "nombre": "Producto Demo", "tiempo_entrega": "3 días"}, "ana@ejemplo.com"
        )

        assert repo.filas["DEMO-1"]["precio"] == Decimal("27.50")
        assert detalle.precio == "27.50"
        assert repo.historial[-1]["accion"] == "editado"
        assert repo.historial[-1]["usuario"] == "ana@ejemplo.com"
        assert repo.historial[-1]["cambios"] == {
            "precio": [Decimal("24.99"), Decimal("27.50")],
            "tiempo_entrega": ["2 a 4 días hábiles", "3 días"],
        }  # "nombre" no cambió: no aparece

    def test_sin_cambios_reales_no_escribe_ni_deja_historial(self):
        servicio, repo, _, _ = _servicio(filas=[_fila()])
        servicio.editar("DEMO-1", {"nombre": "Producto Demo", "precio": Decimal("24.99")}, None)
        assert repo.historial == []

    def test_los_valores_largos_se_recortan_en_el_historial(self):
        servicio, repo, _, _ = _servicio(filas=[_fila()])
        servicio.editar("DEMO-1", {"descripcion": "x" * 1000}, None)
        nuevo = repo.historial[-1]["cambios"]["descripcion"][1]
        assert len(nuevo) == 300 and nuevo.endswith("…")
        assert len(repo.filas["DEMO-1"]["descripcion"]) == 1000  # lo guardado queda completo

    def test_un_producto_archivado_no_se_edita(self):
        servicio, _, _, _ = _servicio(filas=[_fila(estado="archivado")])
        with pytest.raises(TransicionInvalidaError):
            servicio.editar("DEMO-1", {"nombre": "Otro"}, None)

    def test_sku_inexistente(self):
        servicio, _, _, _ = _servicio()
        with pytest.raises(ProductoBotNoEncontradoError):
            servicio.editar("NO-EXISTE", {"nombre": "Otro"}, None)

    def test_a_un_producto_activo_no_se_le_puede_borrar_lo_obligatorio(self):
        servicio, repo, _, _ = _servicio(filas=[_fila(estado="activo", activo=True)])
        with pytest.raises(PublicacionBloqueadaError) as error:
            servicio.editar("DEMO-1", {"descripcion": ""}, None)
        assert any("descripción" in b for b in error.value.bloqueos)
        assert repo.filas["DEMO-1"]["descripcion"] == "Un buen producto."  # no se guardó
        assert repo.historial == []

    def test_a_un_producto_activo_no_se_le_baja_el_precio_bajo_el_piso(self):
        servicio, _, _, _ = _servicio(filas=[_fila(estado="activo", activo=True)])
        with pytest.raises(PublicacionBloqueadaError):
            servicio.editar("DEMO-1", {"precio": Decimal("5.00")}, None)

    def test_un_borrador_si_puede_quedar_incompleto(self):
        servicio, repo, _, _ = _servicio(filas=[_fila()])
        servicio.editar("DEMO-1", {"descripcion": ""}, None)
        assert repo.filas["DEMO-1"]["descripcion"] == ""

    def test_un_problema_anterior_no_bloquea_otras_ediciones_de_un_producto_activo(self):
        # Ya activo y sin stock/precio bajo el costo por un cambio de Rocketfy: editar el texto sigue siendo posible.
        fila = _fila(estado="activo", activo=True, costo_rocketfy=Decimal("30.00"), stock_ultimo=0)
        servicio, repo, _, _ = _servicio(filas=[fila])
        servicio.editar("DEMO-1", {"preguntas_frecuentes": "Nueva pregunta"}, None)
        assert repo.filas["DEMO-1"]["preguntas_frecuentes"] == "Nueva pregunta"


class TestActualizarDesdeRocketfy:
    def test_refresca_los_datos_y_anota_el_historial_si_cambio_el_costo(self):
        servicio, repo, _, _ = _servicio(
            filas=[_fila()], productos=[RocketfyFalso.producto(price="12.50", stock=3)]
        )

        detalle = servicio.actualizar_desde_rocketfy("DEMO-1", "ana@ejemplo.com")

        assert detalle.costo_rocketfy == "12.50"
        assert detalle.stock_ultimo == 3
        assert repo.historial[-1]["accion"] == "actualizado_rocketfy"
        assert repo.historial[-1]["cambios"] == {"costo_rocketfy": ["10.00", "12.50"]}

    def test_si_solo_cambia_el_stock_no_se_llena_el_historial(self):
        servicio, repo, _, _ = _servicio(filas=[_fila()], productos=[RocketfyFalso.producto(stock=1)])
        servicio.actualizar_desde_rocketfy("DEMO-1", None)
        assert repo.historial == []
        assert repo.filas["DEMO-1"]["stock_ultimo"] == 1

    def test_no_toca_los_campos_de_ventas(self):
        servicio, repo, _, _ = _servicio(filas=[_fila(precio=Decimal("33.00"))])
        servicio.actualizar_desde_rocketfy("DEMO-1", None)
        assert repo.filas["DEMO-1"]["precio"] == Decimal("33.00")
        assert repo.filas["DEMO-1"]["nombre"] == "Producto Demo"

    def test_si_el_sku_ya_no_existe_en_rocketfy(self):
        servicio, _, _, _ = _servicio(filas=[_fila()], productos=[])
        with pytest.raises(SkuNoExisteEnRocketfyError):
            servicio.actualizar_desde_rocketfy("DEMO-1", None)


class TestPublicar:
    def test_publica_un_borrador_completo(self):
        servicio, repo, _, _ = _servicio(filas=[_fila()])

        detalle = servicio.publicar("DEMO-1", "ana@ejemplo.com")

        assert detalle.estado == "activo"
        assert repo.filas["DEMO-1"]["activo"] is True
        assert detalle.publicado_por == "ana@ejemplo.com"
        assert repo.historial[-1]["accion"] == "publicado"
        assert repo.historial[-1]["cambios"] == {"estado": ["borrador", "activo"]}

    def test_antes_de_publicar_refresca_los_datos_en_vivo_de_rocketfy(self):
        servicio, repo, _, _ = _servicio(filas=[_fila(stock_ultimo=0)], productos=[RocketfyFalso.producto(stock=40, price="11.00")])

        servicio.publicar("DEMO-1", None)

        assert repo.filas["DEMO-1"]["stock_ultimo"] == 40  # el 0 guardado era viejo
        assert repo.filas["DEMO-1"]["costo_rocketfy"] == Decimal("11.00")

    def test_al_publicar_agrega_el_producto_a_vigilados(self):
        servicio, _, _, monitoreo = _servicio(filas=[_fila()])
        servicio.publicar("DEMO-1", None)
        assert monitoreo.upserts == [("DEMO-1", 5)]

    def test_no_pisa_el_umbral_de_un_producto_ya_vigilado(self):
        servicio, _, _, monitoreo = _servicio(filas=[_fila()], monitoreo=MonitoreoFalso(vigilados=["DEMO-1"]))
        servicio.publicar("DEMO-1", None)
        assert monitoreo.upserts == []
        assert monitoreo.vigilados["DEMO-1"] == 8

    def test_si_falla_vigilar_la_publicacion_sigue(self):
        servicio, repo, _, _ = _servicio(filas=[_fila()], monitoreo=MonitoreoFalso(falla=True))
        servicio.publicar("DEMO-1", None)
        assert repo.filas["DEMO-1"]["estado"] == "activo"

    @pytest.mark.parametrize(
        "cambios, fragmento",
        [
            ({"descripcion": ""}, "descripción"),
            ({"tiempo_entrega": ""}, "tiempo de entrega"),
            ({"metodos_pago_aceptados": ""}, "método de pago"),
            ({"precio": Decimal("5.00")}, "por debajo del mínimo"),
        ],
    )
    def test_un_borrador_incompleto_no_se_publica_y_queda_igual(self, cambios, fragmento):
        servicio, repo, _, monitoreo = _servicio(filas=[_fila(**cambios)])

        with pytest.raises(PublicacionBloqueadaError) as error:
            servicio.publicar("DEMO-1", None)

        assert any(fragmento in b for b in error.value.bloqueos), error.value.bloqueos
        assert (repo.filas["DEMO-1"]["estado"], repo.filas["DEMO-1"]["activo"]) == ("borrador", False)
        assert monitoreo.upserts == []
        assert repo.historial == []

    def test_sin_stock_en_vivo_no_se_publica(self):
        servicio, repo, _, _ = _servicio(filas=[_fila()], productos=[RocketfyFalso.producto(stock=0)])
        with pytest.raises(PublicacionBloqueadaError) as error:
            servicio.publicar("DEMO-1", None)
        assert any("stock" in b for b in error.value.bloqueos)
        assert repo.filas["DEMO-1"]["estado"] == "borrador"

    def test_si_el_sku_ya_no_existe_en_rocketfy_no_se_publica(self):
        servicio, repo, _, _ = _servicio(filas=[_fila()], productos=[])
        with pytest.raises(PublicacionBloqueadaError) as error:
            servicio.publicar("DEMO-1", None)
        assert any("no existe" in b for b in error.value.bloqueos)

    def test_si_rocketfy_no_responde_no_se_publica_a_ciegas(self):
        servicio, repo, _, _ = _servicio(filas=[_fila()], error=RocketfyRequestError("timeout"))
        with pytest.raises(RocketfyRequestError):
            servicio.publicar("DEMO-1", None)
        assert repo.filas["DEMO-1"]["estado"] == "borrador"

    @pytest.mark.parametrize("estado", ["activo", "pausado", "agotado", "archivado"])
    def test_publicar_solo_desde_borrador_o_listo(self, estado):
        servicio, _, _, _ = _servicio(filas=[_fila(estado=estado, activo=estado == "activo")])
        with pytest.raises(TransicionInvalidaError):
            servicio.publicar("DEMO-1", None)

    def test_desde_listo_tambien_se_puede_publicar(self):
        servicio, repo, _, _ = _servicio(filas=[_fila(estado="listo")])
        servicio.publicar("DEMO-1", None)
        assert repo.filas["DEMO-1"]["estado"] == "activo"


class TestPausarReanudarArchivarRestaurar:
    def test_pausar_un_producto_activo(self):
        servicio, repo, _, _ = _servicio(filas=[_fila(estado="activo", activo=True)])

        detalle = servicio.pausar("DEMO-1", "ana@ejemplo.com")

        assert detalle.estado == "pausado"
        assert repo.filas["DEMO-1"]["activo"] is False  # Victoria deja de verlo
        assert repo.historial[-1]["accion"] == "pausado"

    @pytest.mark.parametrize("estado", ["borrador", "pausado", "archivado"])
    def test_solo_se_pausa_lo_activo(self, estado):
        servicio, _, _, _ = _servicio(filas=[_fila(estado=estado)])
        with pytest.raises(TransicionInvalidaError):
            servicio.pausar("DEMO-1", None)

    def test_reanudar_un_producto_pausado_vuelve_a_verificar_con_rocketfy(self):
        servicio, repo, _, _ = _servicio(filas=[_fila(estado="pausado")])
        detalle = servicio.reanudar("DEMO-1", None)
        assert detalle.estado == "activo"
        assert repo.historial[-1]["accion"] == "reanudado"

    def test_no_se_reanuda_un_producto_sin_stock(self):
        servicio, repo, _, _ = _servicio(filas=[_fila(estado="agotado")], productos=[RocketfyFalso.producto(stock=0)])
        with pytest.raises(PublicacionBloqueadaError):
            servicio.reanudar("DEMO-1", None)
        assert repo.filas["DEMO-1"]["estado"] == "agotado"

    @pytest.mark.parametrize("estado", ["borrador", "activo", "archivado"])
    def test_reanudar_solo_desde_pausado_o_agotado(self, estado):
        servicio, _, _, _ = _servicio(filas=[_fila(estado=estado, activo=estado == "activo")])
        with pytest.raises(TransicionInvalidaError):
            servicio.reanudar("DEMO-1", None)

    def test_archivar_un_producto_activo_lo_saca_de_circulacion(self):
        servicio, repo, _, _ = _servicio(filas=[_fila(estado="activo", activo=True)])
        servicio.archivar("DEMO-1", None)
        assert (repo.filas["DEMO-1"]["estado"], repo.filas["DEMO-1"]["activo"]) == ("archivado", False)

    def test_archivar_dos_veces_es_un_error(self):
        servicio, _, _, _ = _servicio(filas=[_fila(estado="archivado")])
        with pytest.raises(TransicionInvalidaError):
            servicio.archivar("DEMO-1", None)

    def test_restaurar_devuelve_un_borrador_nunca_uno_activo(self):
        servicio, repo, _, _ = _servicio(filas=[_fila(estado="archivado")])
        detalle = servicio.restaurar("DEMO-1", None)
        assert detalle.estado == "borrador"
        assert repo.filas["DEMO-1"]["activo"] is False

    def test_restaurar_solo_lo_archivado(self):
        servicio, _, _, _ = _servicio(filas=[_fila()])
        with pytest.raises(TransicionInvalidaError):
            servicio.restaurar("DEMO-1", None)

    def test_ninguna_accion_sobre_un_sku_inexistente(self):
        servicio, _, _, _ = _servicio()
        for accion in (servicio.publicar, servicio.pausar, servicio.reanudar, servicio.archivar, servicio.restaurar):
            with pytest.raises(ProductoBotNoEncontradoError):
                accion("NO-EXISTE", None)


class TestListarYDetalle:
    def test_la_lista_oculta_los_archivados_salvo_que_se_pidan(self):
        servicio, _, _, _ = _servicio(filas=[_fila(), _fila(sku="VIEJO", estado="archivado")])
        assert [p.sku for p in servicio.listar()] == ["DEMO-1"]
        assert sorted(p.sku for p in servicio.listar(incluir_archivados=True)) == ["DEMO-1", "VIEJO"]

    def test_el_dinero_viaja_como_texto_con_dos_decimales(self):
        servicio, _, _, _ = _servicio(filas=[_fila(precio=Decimal("24.9"), costo_rocketfy=None)])
        resumen = servicio.listar()[0]
        assert resumen.precio == "24.90"
        assert resumen.costo_rocketfy is None

    def test_el_detalle_incluye_verificacion_con_lo_ultimo_guardado_e_historial(self):
        servicio, repo, rocketfy, _ = _servicio(filas=[_fila(descripcion="", stock_ultimo=2)])
        repo.registrar_historial("DEMO-1", "creado", "ana@ejemplo.com", {"desde": "rocketfy"})

        detalle = servicio.obtener_detalle("DEMO-1")

        assert any("descripción" in b for b in detalle.verificacion.bloqueos)
        assert any("pocas unidades" in a for a in detalle.verificacion.avisos)
        assert [h.accion for h in detalle.historial] == ["creado"]
        assert rocketfy.consultas == []  # el detalle no llama a la red

    def test_detalle_de_un_sku_inexistente(self):
        servicio, _, _, _ = _servicio()
        with pytest.raises(ProductoBotNoEncontradoError):
            servicio.obtener_detalle("NO-EXISTE")


class TestPisoConElEnvioDelDueno:
    """El envío estimado solo bloquea cuando el dueño ya confirmó sus ajustes."""

    def test_con_ajustes_de_partida_no_bloquea_por_el_envio(self):
        # costo $10 + envío de partida $5 = $15 > precio $12, pero nadie confirmó el envío.
        servicio, repo, _, _ = _servicio(
            [_fila(precio=Decimal("12.00"))], productos=[RocketfyFalso.producto()], ajustes=AjustesFalsos(confirmado=False)
        )
        assert servicio.publicar("DEMO-1", None).estado == "activo"

    def test_con_ajustes_confirmados_bloquea_si_no_cubre_costo_mas_envio(self):
        servicio, repo, _, _ = _servicio(
            [_fila(precio=Decimal("12.00"))], productos=[RocketfyFalso.producto()], ajustes=AjustesFalsos(confirmado=True)
        )
        with pytest.raises(PublicacionBloqueadaError) as error:
            servicio.publicar("DEMO-1", None)
        assert "envío estimado ($5.00)" in error.value.bloqueos[0]
        assert repo.filas["DEMO-1"]["estado"] == "borrador"

    def test_la_ficha_muestra_el_bloqueo_con_ajustes_confirmados(self):
        servicio, _, _, _ = _servicio([_fila(precio=Decimal("12.00"))], ajustes=AjustesFalsos(confirmado=True))
        assert len(servicio.obtener_detalle("DEMO-1").verificacion.bloqueos) == 1

    def test_editar_un_producto_activo_bloquea_si_el_nuevo_precio_no_cubre_el_envio_confirmado(self):
        servicio, repo, _, _ = _servicio(
            [_fila(estado="activo", activo=True)], ajustes=AjustesFalsos(confirmado=True)
        )
        with pytest.raises(PublicacionBloqueadaError):
            servicio.editar("DEMO-1", {"precio": Decimal("12.00")}, None)
        assert repo.filas["DEMO-1"]["precio"] == Decimal("24.99")

    def test_un_producto_activo_que_ya_estaba_bajo_el_piso_no_bloquea_otras_ediciones(self):
        servicio, repo, _, _ = _servicio(
            [_fila(estado="activo", activo=True, precio=Decimal("12.00"))], ajustes=AjustesFalsos(confirmado=True)
        )
        servicio.editar("DEMO-1", {"nombre": "Otro nombre"}, None)
        assert repo.filas["DEMO-1"]["nombre"] == "Otro nombre"


class TestRecomendarPrecio:
    def test_devuelve_los_tres_niveles_del_ejemplo_del_plan_como_texto(self):
        servicio, _, _, _ = _servicio([_fila()], ajustes=AjustesFalsos(confirmado=True))

        r = servicio.recomendar_precio("DEMO-1")

        assert r.ajustes_confirmados is True
        assert (r.costo, r.piso, r.precio_sugerido, r.envio_estimado) == ("10.00", "15.00", "29.90", "5.00")
        assert [(n.clave, n.precio, n.ganancia, n.margen_pct) for n in r.niveles] == [
            ("minimo", "20.99", "5.99", "28.5"),
            ("recomendado", "23.99", "8.99", "37.5"),
            ("premium", "29.90", "14.90", "49.8"),
        ]
        assert r.evaluacion is None

    def test_evalua_el_precio_que_se_esta_tecleando(self):
        servicio, _, _, _ = _servicio([_fila()], ajustes=AjustesFalsos(confirmado=True))

        r = servicio.recomendar_precio("DEMO-1", precio=Decimal("12.00"))

        assert (r.evaluacion.precio, r.evaluacion.ganancia, r.evaluacion.bajo_piso) == ("12.00", "-3.00", True)
        assert any("no se podrá publicar" in a for a in r.avisos)

    def test_no_guarda_nada(self):
        servicio, repo, _, _ = _servicio([_fila()])
        servicio.recomendar_precio("DEMO-1", precio=Decimal("12.00"))
        assert repo.historial == [] and repo.filas["DEMO-1"]["precio"] == Decimal("24.99")

    def test_usa_la_competencia_guardada_o_la_que_se_pase(self):
        servicio, _, _, _ = _servicio([_fila(precio_competencia=Decimal("15.00"))], ajustes=AjustesFalsos(confirmado=True))
        assert servicio.recomendar_precio("DEMO-1").precio_competencia == "15.00"
        assert servicio.recomendar_precio("DEMO-1", competencia=Decimal("40.00")).precio_competencia == "40.00"

    def test_sin_competencia_guardada_es_none(self):
        servicio, _, _, _ = _servicio([_fila()])
        assert servicio.recomendar_precio("DEMO-1").precio_competencia is None

    def test_sin_costo_no_hay_niveles(self):
        servicio, _, _, _ = _servicio([_fila(costo_rocketfy=None)])
        r = servicio.recomendar_precio("DEMO-1", precio=Decimal("24.99"))
        assert r.niveles == [] and r.evaluacion is None and r.costo is None
        assert any("Actualizar desde Rocketfy" in a for a in r.avisos)

    def test_sku_inexistente(self):
        servicio, _, _, _ = _servicio()
        with pytest.raises(ProductoBotNoEncontradoError):
            servicio.recomendar_precio("NO-EXISTE")


class TestPrecioDeLaCompetenciaEnLaFicha:
    def test_se_edita_y_queda_en_el_historial(self):
        servicio, repo, _, _ = _servicio([_fila()])

        detalle = servicio.editar("DEMO-1", {"precio_competencia": Decimal("22.50")}, "ana@ejemplo.com")

        assert detalle.precio_competencia == "22.50"
        assert repo.historial[-1]["cambios"] == {"precio_competencia": [None, Decimal("22.50")]}

    def test_se_puede_borrar(self):
        servicio, _, _, _ = _servicio([_fila(precio_competencia=Decimal("22.50"))])
        assert servicio.editar("DEMO-1", {"precio_competencia": None}, None).precio_competencia is None



class TestAvisosDeLaListaDeVerificacion:
    """Plan de gestión de productos, sección 9: margen bajo y «no hubo una simulación completa»."""

    @staticmethod
    def _avisos(servicio, sku="DEMO-1"):
        return servicio.obtener_detalle(sku).verificacion.avisos

    def test_sin_compra_de_prueba_avisa_en_borrador_y_en_listo(self):
        for estado in ("borrador", "listo"):
            servicio, _, _, _ = _servicio([_fila(estado=estado)])
            assert any("Todavía no probaste una compra completa" in a for a in self._avisos(servicio))

    def test_no_avisa_en_productos_ya_publicados(self):
        for estado in ("activo", "pausado", "agotado"):
            servicio, _, _, _ = _servicio([_fila(estado=estado, activo=estado == "activo")])
            assert not any("compra de prueba" in a or "compra completa" in a for a in self._avisos(servicio))

    def test_con_una_compra_de_prueba_hecha_ya_no_avisa(self):
        servicio, repo, _, _ = _servicio([_fila()])
        repo.registrar_historial("DEMO-1", "simulacion_completa", "ana@ejemplo.com")
        assert not any("compra completa" in a or "compra de prueba" in a for a in self._avisos(servicio))

    def test_si_se_edito_la_ficha_despues_de_la_prueba_avisa_que_conviene_repetirla(self):
        servicio, repo, _, _ = _servicio([_fila()])
        repo.registrar_historial("DEMO-1", "simulacion_completa", None)
        repo.historial[-1]["creado_en"] = AHORA
        repo.registrar_historial("DEMO-1", "editado", None, {"precio": ["20.00", "24.99"]})
        repo.historial[-1]["creado_en"] = datetime(2026, 11, 5, 22, 0, tzinfo=timezone.utc)
        assert any("Cambiaste la ficha después de tu última compra de prueba" in a for a in self._avisos(servicio))

    def test_una_edicion_anterior_a_la_prueba_no_cuenta(self):
        servicio, repo, _, _ = _servicio([_fila()])
        repo.registrar_historial("DEMO-1", "editado", None, {})
        repo.historial[-1]["creado_en"] = datetime(2026, 11, 5, 20, 0, tzinfo=timezone.utc)
        repo.registrar_historial("DEMO-1", "simulacion_completa", None)
        assert not any("Cambiaste la ficha" in a or "compra completa" in a for a in self._avisos(servicio))

    def test_margen_bajo_el_minimo_avisa_solo_con_ajustes_confirmados(self):
        # costo 10, envío 5 -> con precio 18 la ganancia es 3.00 = 16.7 %, menor que el 25 % mínimo
        fila = _fila(precio=Decimal("18.00"), costo_rocketfy=Decimal("10.00"))
        confirmado, _, _, _ = _servicio([fila], ajustes=AjustesFalsos(confirmado=True))
        de_partida, _, _, _ = _servicio([fila], ajustes=AjustesFalsos(confirmado=False))
        assert any("Tu margen (16.7 %) está por debajo del mínimo que definiste (25.00 %)" in a for a in self._avisos(confirmado))
        assert not any("margen" in a.lower() for a in self._avisos(de_partida))

    def test_con_margen_suficiente_no_avisa(self):
        servicio, _, _, _ = _servicio([_fila(precio=Decimal("39.99"))], ajustes=AjustesFalsos(confirmado=True))
        assert not any("margen" in a.lower() for a in self._avisos(servicio))

    def test_si_vendes_a_perdida_lo_dice_con_el_monto(self):
        servicio, _, _, _ = _servicio([_fila(precio=Decimal("12.00"))], ajustes=AjustesFalsos(confirmado=True))
        assert any("pierdes $3.00 por unidad" in a for a in self._avisos(servicio))

    def test_sin_costo_no_hay_margen_que_avisar(self):
        servicio, _, _, _ = _servicio([_fila(costo_rocketfy=None)], ajustes=AjustesFalsos(confirmado=True))
        assert not any("margen" in a.lower() for a in self._avisos(servicio))

    def test_si_falla_el_calculo_la_ficha_se_muestra_igual(self):
        servicio, repo, _, _ = _servicio([_fila()])

        def roto(*args, **kwargs):
            raise RuntimeError("base caída")

        repo.ultima_fecha_de = roto
        detalle = servicio.obtener_detalle("DEMO-1")
        assert detalle.sku == "DEMO-1"

    def test_si_se_uso_la_ia_para_redactar_avisa_que_hay_que_verificar(self):
        servicio, repo, _, _ = _servicio([_fila()])
        assert not any("redactó con IA" in a for a in self._avisos(servicio))
        repo.registrar_historial("DEMO-1", "redactado_ia", None, {"campos": ["nombre"]})
        assert any("Parte de la ficha se redactó con IA" in a for a in self._avisos(servicio))

    def test_el_aviso_de_la_ia_no_sale_en_productos_ya_publicados(self):
        servicio, repo, _, _ = _servicio([_fila(estado="activo", activo=True)])
        repo.registrar_historial("DEMO-1", "redactado_ia", None, {"campos": ["nombre"]})
        assert not any("redactó con IA" in a for a in self._avisos(servicio))


class TestListaConPedidosYMargen:
    @staticmethod
    def _lista(filas, pedidos=None, ajustes=None):
        servicio, repo, _, _ = _servicio(filas, ajustes=ajustes or AjustesFalsos(confirmado=True))
        repo.pedidos = pedidos or {}
        return {r.sku: r for r in servicio.listar()}

    def test_trae_los_pedidos_de_los_ultimos_30_dias_por_sku(self):
        lista = self._lista([_fila(sku="A-1"), _fila(sku="B-2")], pedidos={"A-1": 7})
        assert (lista["A-1"].pedidos_30d, lista["B-2"].pedidos_30d) == (7, 0)

    def test_el_sku_se_busca_sin_distinguir_mayusculas(self):
        assert self._lista([_fila(sku="aud-1")], pedidos={"AUD-1": 3})["aud-1"].pedidos_30d == 3

    def test_si_falla_el_conteo_la_lista_se_muestra_igual(self):
        servicio, repo, _, _ = _servicio([_fila()])

        def roto(dias=30):
            raise RuntimeError("base caída")

        repo.contar_pedidos_por_sku = roto
        assert servicio.listar()[0].pedidos_30d == 0

    def test_margen_en_riesgo_en_un_producto_que_se_vende(self):
        # costo 22 + envío 5 con precio 34.90: ganancia 7.90 = 22.6 %, bajo el 25 % mínimo
        lista = self._lista([_fila(estado="activo", activo=True, precio=Decimal("34.90"), costo_rocketfy=Decimal("22.00"))])
        assert lista["DEMO-1"].margen_en_riesgo is True

    @pytest.mark.parametrize("estado", ["listo", "activo", "pausado", "agotado"])
    def test_la_insignia_sale_en_estos_estados(self, estado):
        fila = _fila(estado=estado, activo=estado == "activo", precio=Decimal("34.90"), costo_rocketfy=Decimal("22.00"))
        assert self._lista([fila])["DEMO-1"].margen_en_riesgo is True

    @pytest.mark.parametrize("estado", ["borrador", "archivado"])
    def test_no_sale_en_borradores_ni_archivados(self, estado):
        fila = _fila(estado=estado, activo=False, precio=Decimal("34.90"), costo_rocketfy=Decimal("22.00"))
        ajustes = AjustesNegocio(confirmado=True)
        assert ProductosBotService._tiene_margen_en_riesgo(fila, ajustes) is False

    def test_con_margen_sano_no_hay_insignia(self):
        fila = _fila(estado="activo", activo=True, precio=Decimal("34.90"), costo_rocketfy=Decimal("10.00"))
        assert self._lista([fila])["DEMO-1"].margen_en_riesgo is False

    def test_con_ajustes_sin_confirmar_no_hay_insignia(self):
        fila = _fila(estado="activo", activo=True, precio=Decimal("34.90"), costo_rocketfy=Decimal("22.00"))
        assert self._lista([fila], ajustes=AjustesFalsos(confirmado=False))["DEMO-1"].margen_en_riesgo is False

    def test_sin_costo_no_se_puede_evaluar(self):
        fila = _fila(estado="activo", activo=True, costo_rocketfy=None)
        assert self._lista([fila])["DEMO-1"].margen_en_riesgo is False

    def test_si_fallan_los_ajustes_la_lista_se_muestra_igual(self):
        class AjustesRotos:
            def obtener_ajustes(self):
                raise RuntimeError("base caída")

        servicio, _, _, _ = _servicio([_fila(estado="activo", activo=True)], ajustes=AjustesRotos())
        assert servicio.listar()[0].margen_en_riesgo is False


class TestImagenDeRocketfy:
    """La API real devuelve `/storage/...` (ruta relativa): hay que completarla para que sirva."""

    def test_al_capturar_los_datos_de_rocketfy_la_ruta_relativa_se_completa(self, monkeypatch):
        monkeypatch.setenv("ROCKETFY_BASE_URL", "https://rocket-e.com/api")
        datos = ProductosBotService._datos_de_rocketfy({"id": 1, "image_url": "/storage/products/4193/foto.jpg"})
        assert datos["imagen_url"] == "https://rocket-e.com/storage/products/4193/foto.jpg"

    @pytest.mark.parametrize("valor, esperado", [(None, None), ("", None), ("https://cdn.x/a.png", "https://cdn.x/a.png"), ("javascript:alert(1)", None)])
    def test_otros_valores(self, valor, esperado):
        assert ProductosBotService._datos_de_rocketfy({"id": 1, "image_url": valor})["imagen_url"] == esperado

    def test_una_ficha_que_aun_guarda_la_ruta_relativa_se_muestra_completa(self, monkeypatch):
        # Lo guardado antes de este arreglo sigue sirviendo sin esperar a la próxima sincronización.
        monkeypatch.setenv("ROCKETFY_BASE_URL", "https://rocket-e.com/api")
        servicio, _, _, _ = _servicio([_fila(imagen_url="/storage/products/4193/foto.jpg")])
        assert servicio.obtener_detalle("DEMO-1").imagen_url == "https://rocket-e.com/storage/products/4193/foto.jpg"
        assert servicio.listar()[0].imagen_url == "https://rocket-e.com/storage/products/4193/foto.jpg"
