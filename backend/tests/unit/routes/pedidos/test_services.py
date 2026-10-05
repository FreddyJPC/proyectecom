from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from src.catalogs.ecuador_locations import EcuadorLocationsCatalog
from src.integrations.rocketfy import RocketfyBusinessError, RocketfyRequestError
from src.routes.pedidos.dto import CrearPedidoInputDTO, LineaPedidoDTO, ModificarPedidoInputDTO
from src.routes.pedidos.exceptions import (
    PedidoEnEstadoAmbiguoError,
    PedidoIncompletoError,
    PedidoNoEncontradoError,
    PedidoSinIdRocketfyError,
    RecaudoMinimoNoAlcanzadoError,
    UbicacionNoResueltaError,
)
from src.routes.pedidos.services import PedidoService


class FakePedidoRepository:
    """Repositorio en memoria: mismo contrato que PedidoRepository (raw SQL
    sobre Supabase), sin tocar una base real — así el test de la lógica de
    negocio de PedidoService no depende de infraestructura."""

    def __init__(self):
        self.tabla = {}

    def obtener(self, id_local):
        return self.tabla.get(id_local)

    def upsert_pendiente(self, id_local, payload_creacion):
        self.tabla[id_local] = {
            "id_local": id_local,
            "id_rocketfy": None,
            "estado_local": "pendiente_creacion",
            "status_id_rocketfy": None,
            "mensaje_error": None,
            "payload_creacion": payload_creacion,
            "creado_en": None,
            "confirmado_en": None,
            "actualizado_en": None,
        }

    def marcar_creado(self, id_local, id_rocketfy, estado_local):
        row = self.tabla[id_local]
        row["id_rocketfy"] = id_rocketfy
        row["estado_local"] = estado_local

    def marcar_error_creacion(self, id_local, mensaje):
        row = self.tabla[id_local]
        row["estado_local"] = "error"
        row["mensaje_error"] = mensaje

    def marcar_confirmado(self, id_local):
        row = self.tabla[id_local]
        row["estado_local"] = "confirmado"
        row["mensaje_error"] = None

    def marcar_error_confirmacion(self, id_local, mensaje):
        self.tabla[id_local]["mensaje_error"] = mensaje

    def actualizar_datos_contacto(self, id_local, campos):
        self.tabla[id_local]["payload_creacion"] = {**self.tabla[id_local]["payload_creacion"], **campos}

    def marcar_rechazado(self, id_local):
        self.tabla[id_local]["estado_local"] = "rechazado"

    def listar(self, estado=None, limit=20, offset=0):
        filas = list(self.tabla.values())
        if estado:
            filas = [f for f in filas if f["estado_local"] == estado]
        filas.sort(key=lambda f: f["id_local"], reverse=True)
        return filas[offset : offset + limit]

    def contar(self, estado=None):
        if estado:
            return sum(1 for f in self.tabla.values() if f["estado_local"] == estado)
        return len(self.tabla)


@pytest.fixture
def catalogo_real():
    return EcuadorLocationsCatalog()


def _dto(
    id_local=100245,
    canton="QUITO",
    provincia="Pichincha",
    n_lineas=1,
    total=Decimal("49.90"),
    no_contra_entrega=False,
):
    lineas = [LineaPedidoDTO(sku=f"SKU-{i}", nombre=f"Producto {i}", cantidad=1) for i in range(n_lineas)]
    return CrearPedidoInputDTO(
        id_local=id_local,
        nombre_cliente="Maria Fernanda Salazar",
        telefono="0991234567",
        direccion="Av. Amazonas N34-120",
        canton=canton,
        provincia=provincia,
        total=total,
        lineas=lineas,
        no_contra_entrega=no_contra_entrega,
    )


class TestFlujoExitoso:
    def test_crea_y_confirma_de_punta_a_punta(self, catalogo_real):
        client = MagicMock()
        client.crear_pedido.return_value = {"id": 9315702, "products_stock": [{"id": 4821, "stock": 137}]}
        client.confirmar_pedido.return_value = {"ok": 1}
        repo = FakePedidoRepository()
        service = PedidoService(client=client, catalogo=catalogo_real, repo=repo)

        resultado = service.crear_y_confirmar(_dto())

        assert resultado.estado_local == "confirmado"
        assert resultado.id_rocketfy == 9315702
        client.crear_pedido.assert_called_once()
        client.confirmar_pedido.assert_called_once_with(order_id=9315702)

    def test_payload_enviado_usa_decimal_dos_cifras_y_json_de_lineas(self, catalogo_real):
        import json

        client = MagicMock()
        client.crear_pedido.return_value = {"id": 1, "products_stock": [{"id": 1, "stock": 5}]}
        client.confirmar_pedido.return_value = {"ok": 1}
        repo = FakePedidoRepository()
        service = PedidoService(client=client, catalogo=catalogo_real, repo=repo)

        service.crear_y_confirmar(_dto())

        payload = client.crear_pedido.call_args.args[0]
        assert payload["total"] == "49.90"
        assert payload["city"] == "QUITO"
        lineas_enviadas = json.loads(payload["order_details"])
        assert lineas_enviadas == [{"sku": "SKU-0", "name": "Producto 0", "quantity": 1}]
        assert payload["carrier_observations"] == ""  # enviado siempre, aunque vacío


class TestIdempotencia:
    def test_pedido_ya_confirmado_es_no_op(self, catalogo_real):
        client = MagicMock()
        repo = FakePedidoRepository()
        repo.tabla[100245] = {
            "id_local": 100245, "id_rocketfy": 9315702, "estado_local": "confirmado",
            "status_id_rocketfy": None, "mensaje_error": None,
            "creado_en": None, "confirmado_en": None, "actualizado_en": None,
        }
        service = PedidoService(client=client, catalogo=catalogo_real, repo=repo)

        resultado = service.crear_y_confirmar(_dto())

        assert resultado.estado_local == "confirmado"
        client.crear_pedido.assert_not_called()
        client.confirmar_pedido.assert_not_called()

    def test_estado_ambiguo_bloquea_reintento_automatico(self, catalogo_real):
        client = MagicMock()
        repo = FakePedidoRepository()
        repo.tabla[100245] = {
            "id_local": 100245, "id_rocketfy": None, "estado_local": "pendiente_creacion",
            "status_id_rocketfy": None, "mensaje_error": None,
            "creado_en": None, "confirmado_en": None, "actualizado_en": None,
        }
        service = PedidoService(client=client, catalogo=catalogo_real, repo=repo)

        with pytest.raises(PedidoEnEstadoAmbiguoError):
            service.crear_y_confirmar(_dto())
        client.crear_pedido.assert_not_called()

    def test_timeout_al_crear_deja_estado_ambiguo(self, catalogo_real):
        client = MagicMock()
        client.crear_pedido.side_effect = RocketfyRequestError("timeout simulado")
        repo = FakePedidoRepository()
        service = PedidoService(client=client, catalogo=catalogo_real, repo=repo)

        with pytest.raises(RocketfyRequestError):
            service.crear_y_confirmar(_dto())

        assert repo.tabla[100245]["estado_local"] == "pendiente_creacion"
        # Segundo intento: bloqueado, no se reintenta a ciegas
        with pytest.raises(PedidoEnEstadoAmbiguoError):
            service.crear_y_confirmar(_dto())
        client.crear_pedido.assert_called_once()

    def test_error_405_al_crear_permite_reintento_limpio(self, catalogo_real):
        client = MagicMock()
        client.crear_pedido.side_effect = RocketfyBusinessError("Error interno al crear el pedido", code=405)
        repo = FakePedidoRepository()
        service = PedidoService(client=client, catalogo=catalogo_real, repo=repo)

        with pytest.raises(RocketfyBusinessError):
            service.crear_y_confirmar(_dto())
        assert repo.tabla[100245]["estado_local"] == "error"

        # Reintento: esta vez Rocketfy sí crea el pedido
        client.crear_pedido.side_effect = None
        client.crear_pedido.return_value = {"id": 55, "products_stock": [{"id": 1, "stock": 1}]}
        client.confirmar_pedido.return_value = {"ok": 1}

        resultado = service.crear_y_confirmar(_dto())
        assert resultado.estado_local == "confirmado"
        assert client.crear_pedido.call_count == 2

    def test_rechazo_al_confirmar_permite_reintentar_solo_confirmacion(self, catalogo_real):
        client = MagicMock()
        client.crear_pedido.return_value = {"id": 9315702, "products_stock": [{"id": 1, "stock": 1}]}
        client.confirmar_pedido.side_effect = RocketfyBusinessError(
            "No es posible confirmar este pedido con la transportadora seleccionada "
            "ya que no tiene cobertura a: Quilanga",
            code=401,
        )
        repo = FakePedidoRepository()
        service = PedidoService(client=client, catalogo=catalogo_real, repo=repo)

        with pytest.raises(RocketfyBusinessError):
            service.crear_y_confirmar(_dto())

        fila = repo.tabla[100245]
        assert fila["estado_local"] == "creado"  # NO se marca como rechazado
        assert "cobertura" in fila["mensaje_error"].lower()
        assert fila["id_rocketfy"] == 9315702

        # Reintento tras "corregir": no debe volver a llamar crear_pedido
        client.confirmar_pedido.side_effect = None
        client.confirmar_pedido.return_value = {"ok": 1}
        resultado = service.crear_y_confirmar(_dto())

        assert resultado.estado_local == "confirmado"
        client.crear_pedido.assert_called_once()  # sigue habiendo sido llamado solo una vez
        assert client.confirmar_pedido.call_count == 2


class TestValidacionDeUbicacion:
    def test_canton_inexistente_no_llama_a_rocketfy(self, catalogo_real):
        client = MagicMock()
        repo = FakePedidoRepository()
        service = PedidoService(client=client, catalogo=catalogo_real, repo=repo)

        with pytest.raises(UbicacionNoResueltaError):
            service.crear_y_confirmar(_dto(canton="Quito Norte"))  # ejemplo textual del doc: no existe

        client.crear_pedido.assert_not_called()
        assert 100245 not in repo.tabla


class TestRecaudoMinimoContraentrega:
    def test_contraentrega_bajo_el_minimo_no_llama_a_rocketfy(self, catalogo_real):
        client = MagicMock()
        repo = FakePedidoRepository()
        service = PedidoService(client=client, catalogo=catalogo_real, repo=repo)

        with pytest.raises(RecaudoMinimoNoAlcanzadoError):
            service.crear_y_confirmar(_dto(total=Decimal("1.00")))

        client.crear_pedido.assert_not_called()
        assert 100245 not in repo.tabla

    def test_prepagado_bajo_diez_dolares_si_se_crea(self, catalogo_real):
        client = MagicMock()
        client.crear_pedido.return_value = {"id": 9315702, "products_stock": [{"id": 1, "stock": 5}]}
        client.confirmar_pedido.return_value = {"ok": 1}
        repo = FakePedidoRepository()
        service = PedidoService(client=client, catalogo=catalogo_real, repo=repo)

        resultado = service.crear_y_confirmar(_dto(total=Decimal("1.00"), no_contra_entrega=True))

        assert resultado.estado_local == "confirmado"
        client.crear_pedido.assert_called_once()

    def test_contraentrega_justo_en_el_minimo_si_se_crea(self, catalogo_real):
        client = MagicMock()
        client.crear_pedido.return_value = {"id": 9315702, "products_stock": [{"id": 1, "stock": 5}]}
        client.confirmar_pedido.return_value = {"ok": 1}
        repo = FakePedidoRepository()
        service = PedidoService(client=client, catalogo=catalogo_real, repo=repo)

        resultado = service.crear_y_confirmar(_dto(total=Decimal("10.00")))

        assert resultado.estado_local == "confirmado"
        client.crear_pedido.assert_called_once()


class TestProductsStockIncompleto:
    def test_menos_lineas_de_stock_que_enviadas_marca_incompleto(self, catalogo_real):
        client = MagicMock()
        client.crear_pedido.return_value = {"id": 9315702, "products_stock": [{"id": 1, "stock": 5}]}
        repo = FakePedidoRepository()
        service = PedidoService(client=client, catalogo=catalogo_real, repo=repo)

        with pytest.raises(PedidoIncompletoError):
            service.crear_y_confirmar(_dto(n_lineas=2))  # 2 líneas enviadas, solo 1 en products_stock

        assert repo.tabla[100245]["estado_local"] == "incompleto"
        client.confirmar_pedido.assert_not_called()


def _pedido_creado(repo: FakePedidoRepository, id_local=100245, id_rocketfy=9315702, **payload_extra):
    payload = {
        "id_local": id_local, "nombre_cliente": "Maria", "telefono": "0991234567",
        "direccion": "Av. Amazonas", "canton": "QUITO", "provincia": "Pichincha",
    }
    payload.update(payload_extra)
    repo.tabla[id_local] = {
        "id_local": id_local, "id_rocketfy": id_rocketfy, "estado_local": "creado",
        "status_id_rocketfy": None, "mensaje_error": None, "payload_creacion": payload,
        "creado_en": None, "confirmado_en": None, "actualizado_en": None,
    }


class TestModificar:
    def test_pedido_inexistente_lanza_no_encontrado(self, catalogo_real):
        service = PedidoService(client=MagicMock(), catalogo=catalogo_real, repo=FakePedidoRepository())
        with pytest.raises(PedidoNoEncontradoError):
            service.modificar(999, ModificarPedidoInputDTO(telefono="0999999999"))

    def test_pedido_sin_id_rocketfy_no_llama_a_rocketfy(self, catalogo_real):
        client = MagicMock()
        repo = FakePedidoRepository()
        repo.upsert_pendiente(100245, {"canton": "QUITO", "provincia": "Pichincha"})
        service = PedidoService(client=client, catalogo=catalogo_real, repo=repo)

        with pytest.raises(PedidoSinIdRocketfyError):
            service.modificar(100245, ModificarPedidoInputDTO(telefono="0999999999"))
        client.modificar_pedido.assert_not_called()

    def test_modifica_solo_los_campos_enviados(self, catalogo_real):
        client = MagicMock()
        repo = FakePedidoRepository()
        _pedido_creado(repo)
        service = PedidoService(client=client, catalogo=catalogo_real, repo=repo)

        service.modificar(100245, ModificarPedidoInputDTO(telefono="0999999999"))

        client.modificar_pedido.assert_called_once_with({"order_id": 9315702, "phone": "0999999999"})
        assert repo.tabla[100245]["payload_creacion"]["telefono"] == "0999999999"
        assert repo.tabla[100245]["payload_creacion"]["direccion"] == "Av. Amazonas"  # no tocado

    def test_cambiar_canton_valido_se_envia_y_actualiza_cache_local(self, catalogo_real):
        client = MagicMock()
        repo = FakePedidoRepository()
        _pedido_creado(repo)
        service = PedidoService(client=client, catalogo=catalogo_real, repo=repo)

        service.modificar(100245, ModificarPedidoInputDTO(canton="GUAYAQUIL", provincia="Guayas"))

        client.modificar_pedido.assert_called_once_with(
            {"order_id": 9315702, "city": "GUAYAQUIL", "province": "Guayas"}
        )
        assert repo.tabla[100245]["payload_creacion"]["canton"] == "GUAYAQUIL"

    def test_cambiar_a_canton_inexistente_no_llama_a_rocketfy(self, catalogo_real):
        client = MagicMock()
        repo = FakePedidoRepository()
        _pedido_creado(repo)
        service = PedidoService(client=client, catalogo=catalogo_real, repo=repo)

        with pytest.raises(UbicacionNoResueltaError):
            service.modificar(100245, ModificarPedidoInputDTO(canton="Quito Norte"))
        client.modificar_pedido.assert_not_called()

    def test_cambiar_solo_canton_completa_provincia_desde_el_payload_guardado(self, catalogo_real):
        # El pedido ya tenía provincia="Pichincha"; si solo se cambia el
        # cantón, hay que validar la combinación completa (nuevo cantón +
        # provincia YA guardada), no solo el cantón suelto.
        client = MagicMock()
        repo = FakePedidoRepository()
        _pedido_creado(repo, canton="QUITO", provincia="Pichincha")
        service = PedidoService(client=client, catalogo=catalogo_real, repo=repo)

        with pytest.raises(UbicacionNoResueltaError):
            service.modificar(100245, ModificarPedidoInputDTO(canton="Quito Norte"))

    def test_rechazo_de_rocketfy_no_actualiza_cache_local(self, catalogo_real):
        client = MagicMock()
        client.modificar_pedido.side_effect = RocketfyBusinessError(
            "No es posible modificar los datos de un pedido ya confirmado/preparado", code=401
        )
        repo = FakePedidoRepository()
        _pedido_creado(repo)
        service = PedidoService(client=client, catalogo=catalogo_real, repo=repo)

        with pytest.raises(RocketfyBusinessError):
            service.modificar(100245, ModificarPedidoInputDTO(telefono="0999999999"))
        assert repo.tabla[100245]["payload_creacion"]["telefono"] == "0991234567"  # no cambió


class TestRechazar:
    def test_pedido_inexistente_lanza_no_encontrado(self, catalogo_real):
        service = PedidoService(client=MagicMock(), catalogo=catalogo_real, repo=FakePedidoRepository())
        with pytest.raises(PedidoNoEncontradoError):
            service.rechazar(999)

    def test_pedido_sin_id_rocketfy_no_llama_a_rocketfy(self, catalogo_real):
        client = MagicMock()
        repo = FakePedidoRepository()
        repo.upsert_pendiente(100245, {"canton": "QUITO", "provincia": "Pichincha"})
        service = PedidoService(client=client, catalogo=catalogo_real, repo=repo)

        with pytest.raises(PedidoSinIdRocketfyError):
            service.rechazar(100245)
        client.rechazar_pedido.assert_not_called()

    def test_rechazo_exitoso_marca_estado_local(self, catalogo_real):
        client = MagicMock()
        repo = FakePedidoRepository()
        _pedido_creado(repo)
        service = PedidoService(client=client, catalogo=catalogo_real, repo=repo)

        resultado = service.rechazar(100245)

        client.rechazar_pedido.assert_called_once_with(9315702)
        assert resultado.estado_local == "rechazado"

    def test_etiqueta_ya_impresa_no_cambia_estado_local(self, catalogo_real):
        client = MagicMock()
        client.rechazar_pedido.side_effect = RocketfyBusinessError(
            "No es posible rechazar un pedido con etiqueta YA IMPRESA", code=401
        )
        repo = FakePedidoRepository()
        _pedido_creado(repo)
        service = PedidoService(client=client, catalogo=catalogo_real, repo=repo)

        with pytest.raises(RocketfyBusinessError):
            service.rechazar(100245)
        assert repo.tabla[100245]["estado_local"] == "creado"  # no cambió


class TestListar:
    def test_devuelve_resumen_con_datos_de_contacto(self, catalogo_real):
        repo = FakePedidoRepository()
        _pedido_creado(repo, id_local=1, total="49.90")
        service = PedidoService(client=MagicMock(), catalogo=catalogo_real, repo=repo)

        resultado = service.listar()

        assert resultado["total"] == 1
        item = resultado["items"][0]
        assert item.id_local == 1
        assert item.nombre_cliente == "Maria"
        assert item.total == Decimal("49.90")

    def test_filtra_por_estado(self, catalogo_real):
        repo = FakePedidoRepository()
        _pedido_creado(repo, id_local=1)
        _pedido_creado(repo, id_local=2)
        repo.marcar_rechazado(2)
        service = PedidoService(client=MagicMock(), catalogo=catalogo_real, repo=repo)

        resultado = service.listar(estado="rechazado")

        assert resultado["total"] == 1
        assert resultado["items"][0].id_local == 2

    def test_pagina_respeta_page_size(self, catalogo_real):
        repo = FakePedidoRepository()
        for i in range(1, 4):
            _pedido_creado(repo, id_local=i)
        service = PedidoService(client=MagicMock(), catalogo=catalogo_real, repo=repo)

        pagina_1 = service.listar(page=1, page_size=2)
        pagina_2 = service.listar(page=2, page_size=2)

        assert pagina_1["total"] == 3
        assert len(pagina_1["items"]) == 2
        assert len(pagina_2["items"]) == 1


class TestObtenerDetalle:
    def test_pedido_inexistente_lanza_no_encontrado(self, catalogo_real):
        service = PedidoService(client=MagicMock(), catalogo=catalogo_real, repo=FakePedidoRepository())

        with pytest.raises(PedidoNoEncontradoError):
            service.obtener_detalle(100245)

    def test_devuelve_todos_los_datos_guardados_al_crear(self, catalogo_real):
        repo = FakePedidoRepository()
        _pedido_creado(
            repo,
            total="49.90",
            lineas=[{"sku": "SKU-1", "nombre": "Producto", "cantidad": 2}],
        )
        service = PedidoService(client=MagicMock(), catalogo=catalogo_real, repo=repo)

        detalle = service.obtener_detalle(100245)

        assert detalle.nombre_cliente == "Maria"
        assert detalle.total == Decimal("49.90")
        assert detalle.lineas == [LineaPedidoDTO(sku="SKU-1", nombre="Producto", cantidad=2)]
