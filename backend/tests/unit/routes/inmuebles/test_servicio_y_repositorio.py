"""
Módulo «Inmuebles» contra la base de pruebas (nunca la de producción): fichas, material, anuncios, agenda, números del negocio
y la clave nueva de las conversaciones (una por número del negocio).
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from src.config.database import get_connection
from src.routes.inmuebles.repository import NumeroWhatsappRepository, VisitaRepository
from src.routes.inmuebles.ruteo import RuteoDeAsistente
from src.routes.inmuebles.servicio import (
    DatosInvalidosError,
    InmuebleNoEncontradoError,
    InmueblesServicio,
    VentanaCerradaError,
    VisitasServicio,
)
from src.routes.whatsapp.repository import ConversacionRepository, MensajeRepository
from tests.helpers_db import borrar_conversaciones_de_prueba, borrar_inmuebles_de_prueba, borrar_numeros_de_prueba

CODIGO = "TEST-CASA-01"
CODIGO_2 = "TEST-LOCAL-02"
TELEFONO = "593990001101"
NUMERO_CASA = "880000000001"
ANUNCIO = "1200000000990001"

FICHA = {
    "codigo": "test casa 01", "titulo": "Casa de prueba", "tipo": "casa", "sector": "Norte", "ciudad": "Guayaquil",
    "descripcion": "Casa amplia de dos pisos.", "latitud": "-2.170998", "longitud": "-79.922359", "precio": "85000.00",
}


@pytest.fixture(autouse=True)
def limpiar():
    def _limpiar():
        borrar_conversaciones_de_prueba(TELEFONO)
        borrar_inmuebles_de_prueba(CODIGO, CODIGO_2)
        borrar_numeros_de_prueba(NUMERO_CASA)
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("delete from anuncios_productos where id_anuncio = %s", (ANUNCIO,))
    _limpiar()
    yield
    _limpiar()


def _servicio():
    return InmueblesServicio()


class TestFichas:
    def test_crear_normaliza_el_codigo_y_nace_en_borrador(self):
        inmueble = _servicio().crear(dict(FICHA, estado="activo"))
        assert inmueble["codigo"] == CODIGO
        assert inmueble["estado"] == "borrador"
        assert inmueble["carpeta"] == f"i{inmueble['id']}"
        assert "Fotos o videos" in inmueble["faltantes"]

    def test_codigo_repetido(self):
        from src.routes.inmuebles.repository import CodigoDeInmuebleRepetidoError

        _servicio().crear(dict(FICHA))
        with pytest.raises(CodigoDeInmuebleRepetidoError):
            _servicio().crear(dict(FICHA, titulo="Otra"))

    def test_latitud_sin_longitud_se_rechaza(self):
        with pytest.raises(DatosInvalidosError):
            _servicio().crear({"codigo": CODIGO, "titulo": "Casa", "latitud": "-2.1"})

    def test_publicar_pide_lo_minimo(self):
        inmueble = _servicio().crear({"codigo": CODIGO, "titulo": "Casa sin datos"})
        with pytest.raises(DatosInvalidosError, match="sector o la dirección"):
            _servicio().cambiar_estado(inmueble["id"], "activo")
        _servicio().actualizar(inmueble["id"], {"sector": "Norte", "descripcion": "Linda"})
        assert _servicio().cambiar_estado(inmueble["id"], "activo")["estado"] == "activo"
        # Publicada, no se le puede borrar lo mínimo.
        with pytest.raises(DatosInvalidosError):
            _servicio().actualizar(inmueble["id"], {"descripcion": "  "})

    def test_el_estado_no_se_cambia_por_la_edicion(self):
        inmueble = _servicio().crear(dict(FICHA))
        assert _servicio().actualizar(inmueble["id"], {"estado": "activo", "pisos": 2})["estado"] == "borrador"

    def test_inexistente(self):
        with pytest.raises(InmuebleNoEncontradoError):
            _servicio().detalle(999999999)


class TestMaterial:
    def test_solo_rutas_de_su_carpeta(self, monkeypatch):
        inmueble = _servicio().crear(dict(FICHA))
        carpeta = inmueble["carpeta"]
        with pytest.raises(DatosInvalidosError):
            _servicio().agregar_material(inmueble["id"], "p1/foto.jpg", None)  # carpeta de un producto
        with pytest.raises(DatosInvalidosError):
            _servicio().agregar_material(inmueble["id"], f"{carpeta}/video.mov", None)  # WhatsApp no acepta .mov
        detalle = _servicio().agregar_material(inmueble["id"], f"{carpeta}/a.jpg", "freddy")
        detalle = _servicio().agregar_material(inmueble["id"], f"{carpeta}/b.mp4", "freddy")
        assert [m["tipo"] for m in detalle["material"]] == ["imagen", "video"]
        assert detalle["material"][0]["url"].endswith(f"/storage/v1/object/public/productos/{carpeta}/a.jpg")
        ids = [m["id"] for m in detalle["material"]]
        detalle = _servicio().ordenar_material(inmueble["id"], list(reversed(ids)))
        assert [m["storage_path"] for m in detalle["material"]] == [f"{carpeta}/b.mp4", f"{carpeta}/a.jpg"]
        with pytest.raises(DatosInvalidosError):
            _servicio().ordenar_material(inmueble["id"], ids[:1])
        assert len(_servicio().quitar_material(inmueble["id"], ids[0])["material"]) == 1


class TestAnuncios:
    def test_vincular_y_rutear(self):
        inmueble = _servicio().crear(dict(FICHA))
        detalle = _servicio().vincular_anuncio(inmueble["id"], ANUNCIO, "Video casa")
        assert detalle["anuncios"][0]["id_anuncio"] == ANUNCIO
        assert RuteoDeAsistente().decidir(None, ANUNCIO) == ("inmuebles", inmueble["id"])
        _servicio().desvincular_anuncio(inmueble["id"], ANUNCIO)
        assert RuteoDeAsistente().decidir(None, ANUNCIO) == ("ventas", None)

    def test_un_anuncio_de_un_producto_no_se_puede_vincular(self):
        from src.routes.inmuebles.repository import AnuncioInmuebleRepository

        class AnunciosConProducto(AnuncioInmuebleRepository):
            @staticmethod
            def es_anuncio_de_producto(id_anuncio):
                return True

        servicio = InmueblesServicio(anuncios=AnunciosConProducto())
        inmueble = servicio.crear(dict(FICHA))
        with pytest.raises(DatosInvalidosError, match="producto"):
            servicio.vincular_anuncio(inmueble["id"], ANUNCIO, None)
        assert AnuncioInmuebleRepository.es_anuncio_de_producto(ANUNCIO) is False  # la consulta real responde

    def test_el_id_del_anuncio_son_numeros(self):
        inmueble = _servicio().crear(dict(FICHA))
        with pytest.raises(DatosInvalidosError):
            _servicio().vincular_anuncio(inmueble["id"], "abc", None)


class TestNumerosYConversaciones:
    def test_un_numero_asignado_a_inmuebles(self):
        _servicio().guardar_numero({"phone_number_id": NUMERO_CASA, "nombre": "Casa", "asistente": "inmuebles"})
        assert NumeroWhatsappRepository.asistente_de(NUMERO_CASA) == "inmuebles"
        assert RuteoDeAsistente().decidir(NUMERO_CASA, None) == ("inmuebles", None)
        assert RuteoDeAsistente().decidir(None, None) == ("ventas", None)
        _servicio().guardar_numero({"phone_number_id": NUMERO_CASA, "nombre": "Casa", "asistente": "inmuebles", "activo": False})
        assert NumeroWhatsappRepository.asistente_de(NUMERO_CASA) is None

    def test_datos_del_numero(self):
        with pytest.raises(DatosInvalidosError):
            _servicio().guardar_numero({"phone_number_id": "abc", "nombre": "x", "asistente": "inmuebles"})
        with pytest.raises(DatosInvalidosError):
            _servicio().guardar_numero({"phone_number_id": NUMERO_CASA, "nombre": "", "asistente": "inmuebles"})

    def test_una_conversacion_por_numero_del_negocio(self):
        de_victoria = ConversacionRepository.crear(id_externo=TELEFONO)
        de_la_casa = ConversacionRepository.crear(
            id_externo=TELEFONO, numero_negocio=NUMERO_CASA, asistente="inmuebles"
        )
        assert de_victoria["id"] != de_la_casa["id"]
        assert de_victoria["contacto_id"] == de_la_casa["contacto_id"]  # la misma persona
        assert ConversacionRepository.obtener_por_canal("whatsapp", TELEFONO)["id"] == de_victoria["id"]
        assert ConversacionRepository.obtener_por_canal("whatsapp", TELEFONO, NUMERO_CASA)["id"] == de_la_casa["id"]
        assert de_la_casa["asistente"] == "inmuebles" and de_victoria["asistente"] == "ventas"
        # «Crear o traer»: repetir no duplica.
        assert ConversacionRepository.crear(id_externo=TELEFONO, numero_negocio=NUMERO_CASA)["id"] == de_la_casa["id"]

    def test_el_dueno_cambia_el_asistente(self):
        inmueble = _servicio().crear(dict(FICHA))
        conversacion = ConversacionRepository.crear(id_externo=TELEFONO)
        _servicio().fijar_asistente_de_conversacion(conversacion["id"], "inmuebles", inmueble["id"])
        assert ConversacionRepository.obtener_por_id(conversacion["id"])["inmueble_id"] == inmueble["id"]
        _servicio().fijar_asistente_de_conversacion(conversacion["id"], "ventas", inmueble["id"])
        fila = ConversacionRepository.obtener_por_id(conversacion["id"])
        assert fila["asistente"] == "ventas" and fila["inmueble_id"] is None


class TestAgenda:
    def _con_pedido(self):
        inmueble = _servicio().crear(dict(FICHA, encargado_visitas="Don Luis"))
        conversacion = ConversacionRepository.crear(id_externo=TELEFONO, asistente="inmuebles", inmueble_id=inmueble["id"])
        visita = VisitaRepository.crear({
            "inmueble_id": inmueble["id"], "conversacion_id": conversacion["id"], "nombre_cliente": "María Pérez",
            "estado": "solicitada", "preferencia_cliente": "el sábado en la mañana",
        })
        return inmueble, conversacion, visita

    def test_confirmar_reprogramar_y_cerrar(self):
        _, _, visita = self._con_pedido()
        agenda = VisitasServicio(canales=MagicMock())
        sabado = datetime(2026, 11, 28, 15, 0, tzinfo=timezone.utc)
        confirmada = agenda.confirmar(visita["id"], sabado, None, "Lleva la llave")
        assert confirmada["estado"] == "confirmada" and confirmada["encargado"] == "Don Luis"
        assert confirmada["fecha_hora"] == sabado and confirmada["notas"] == "Lleva la llave"
        assert "28 de noviembre a las 10:00" in agenda.texto_de_aviso(visita["id"])
        domingo = sabado + timedelta(days=1)
        assert agenda.confirmar(visita["id"], domingo, "Ana", None)["encargado"] == "Ana"
        assert agenda.cambiar_estado(visita["id"], "realizada")["estado"] == "realizada"
        with pytest.raises(DatosInvalidosError):
            agenda.cambiar_estado(visita["id"], "solicitada")

    def test_no_se_marca_realizada_sin_confirmar(self):
        _, _, visita = self._con_pedido()
        with pytest.raises(DatosInvalidosError):
            VisitasServicio().cambiar_estado(visita["id"], "realizada")
        with pytest.raises(DatosInvalidosError):
            VisitasServicio().texto_de_aviso(visita["id"])

    def test_cancelar_guarda_el_motivo(self):
        _, _, visita = self._con_pedido()
        cancelada = VisitasServicio().cambiar_estado(visita["id"], "cancelada", "Ya compró otra")
        assert cancelada["motivo_cancelacion"] == "Ya compró otra"

    def test_una_sola_visita_abierta_por_conversacion(self):
        import psycopg2

        inmueble, conversacion, _ = self._con_pedido()
        with pytest.raises(psycopg2.errors.UniqueViolation):
            VisitaRepository.crear({"inmueble_id": inmueble["id"], "conversacion_id": conversacion["id"], "estado": "solicitada"})

    def test_visita_manual_con_fecha_queda_confirmada(self):
        inmueble = _servicio().crear(dict(FICHA, encargado_visitas="Don Luis"))
        visita = VisitasServicio().crear_manual({
            "inmueble_id": inmueble["id"], "nombre_cliente": "Pedro", "telefono": "0991112233",
            "fecha_hora": datetime(2026, 12, 1, 20, 0, tzinfo=timezone.utc),
        })
        assert visita["estado"] == "confirmada" and visita["creada_por"] == "dueno" and visita["encargado"] == "Don Luis"
        assert visita["ventana_abierta"] is False  # sin conversación de WhatsApp

    def test_avisar_al_cliente_dentro_de_las_24_horas(self):
        _, conversacion, visita = self._con_pedido()
        MensajeRepository.crear(conversacion["id"], "cliente", "Quiero ir el sábado", "texto", "wamid.test-visita-1")
        canal = MagicMock()
        canales = MagicMock()
        canales.para_conversacion.return_value = canal
        agenda = VisitasServicio(canales=canales)
        agenda.confirmar(visita["id"], datetime(2026, 11, 28, 15, 0, tzinfo=timezone.utc), None, None)
        avisada = agenda.avisar_cliente(visita["id"])
        assert avisada["avisado_cliente_en"] is not None
        canal.enviar_texto.assert_called_once()
        assert canal.enviar_texto.call_args.args[0] == TELEFONO
        assert "sábado 28 de noviembre a las 10:00" in canal.enviar_texto.call_args.args[1]
        ultimo = MensajeRepository.obtener_por_conversacion(conversacion["id"])[-1]
        assert ultimo["rol"] == "humano" and "confirmada" in ultimo["contenido"]

    def test_fuera_de_las_24_horas_no_se_puede_avisar(self):
        _, conversacion, visita = self._con_pedido()
        agenda = VisitasServicio(canales=MagicMock())
        agenda.confirmar(visita["id"], datetime(2026, 11, 28, 15, 0, tzinfo=timezone.utc), None, None)
        with pytest.raises(VentanaCerradaError):
            agenda.avisar_cliente(visita["id"])  # el cliente nunca escribió: no hay ventana

    def test_la_agenda_filtra_por_dia_y_muestra_las_por_confirmar(self):
        inmueble, _, visita = self._con_pedido()
        otra = VisitasServicio().crear_manual({
            "inmueble_id": inmueble["id"], "nombre_cliente": "Lejana", "fecha_hora": datetime(2027, 3, 1, 15, 0, tzinfo=timezone.utc),
        })
        desde = datetime(2026, 11, 23, tzinfo=timezone.utc)
        hasta = datetime(2026, 12, 31, tzinfo=timezone.utc)
        ids = [v["id"] for v in VisitasServicio().listar(desde=desde, hasta=hasta, inmueble_id=inmueble["id"])]
        assert visita["id"] in ids  # sin fecha todavía: siempre a la vista
        assert otra["id"] not in ids
        resumen = VisitasServicio().resumen()
        assert resumen["por_confirmar"] >= 1
