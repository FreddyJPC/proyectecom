"""
«Aprendizaje de Victoria» (entrada 0.0.140): qué se guarda, que anotar nunca rompe una venta, la API de revisión y que las
intervenciones del dueño, los «Datos de envío» y el pedido manual desde una conversación quedan bien hechos.
"""
from datetime import datetime, timezone
from unittest.mock import MagicMock

import responses

from src.app import create_app
from src.config.database import get_connection
from src.routes.aprendizaje import logica
from src.routes.aprendizaje.servicio import RegistroAprendizaje, RegistroQueNoGuarda
from src.routes.conversaciones.services import ConversacionesService
from src.routes.whatsapp.repository import ConversacionRepository, LeadRepository, MensajeRepository
from tests.conftest import AUTH_HEADER, mock_login_ok
from tests.helpers_db import borrar_conversaciones_de_prueba

TEL = "593990035001"


def _client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def _conversacion_con_lead():
    borrar_conversaciones_de_prueba(TEL)
    conversacion = ConversacionRepository.crear(id_externo=TEL, telefono=TEL)
    lead = LeadRepository.obtener_o_crear(conversacion["id"], conversacion["contacto_id"], TEL)
    MensajeRepository.crear(conversacion_id=conversacion["id"], rol="cliente", contenido="¿qué temperatura hace hoy?", tipo="texto", wamid=None)
    return conversacion, lead


class TestLogica:
    def test_etapa_de_venta_sigue_el_orden_natural(self):
        assert logica.etapa_de_venta(None) == "producto"
        base = {"producto_sku": "X", "nombre_cliente": "Ana", "canton": "Quito", "provincia": "Pichincha", "direccion": "Calle 1"}
        assert logica.etapa_de_venta({"producto_sku": "X"}) == "datos"
        assert logica.etapa_de_venta({**base, "direccion": None, "tipo_entrega": "agencia"}) == "entrega"
        assert logica.etapa_de_venta(base) == "pago"
        assert logica.etapa_de_venta({**base, "metodo_pago": "transferencia"}) == "pago"
        assert logica.etapa_de_venta({**base, "metodo_pago": "contraentrega"}) == "confirmacion"
        assert logica.etapa_de_venta({**base, "metodo_pago": "contraentrega", "datos_confirmados_en": 1}) == "cierre"
        assert logica.etapa_de_venta({**base, "estado": "despachado"}) == "postventa"

    def test_extracto_recorta_y_toma_los_ultimos(self):
        filas = [{"rol": "cliente", "contenido": f"m{i}", "creado_en": datetime(2026, 11, 16, tzinfo=timezone.utc)} for i in range(12)]
        filas.append({"rol": "cliente", "contenido": "x" * 900})
        extracto = logica.extracto(filas)
        assert len(extracto) == logica.MENSAJES_DE_CONTEXTO and extracto[-1]["texto"].endswith("…")
        assert logica.ultimo_del_cliente(filas).startswith("xxx")

    def test_un_tipo_desconocido_cuenta_como_otro(self):
        assert logica.tipo_valido("inventado") == "otro" and logica.tipo_valido("sin_respuesta") == "sin_respuesta"


class TestRegistro:
    def test_arma_el_caso_con_el_mensaje_exacto_y_el_contexto(self):
        guardados = []
        mensajes = MagicMock()
        mensajes.obtener_por_conversacion.return_value = [
            {"rol": "bot", "contenido": "¡Hola! ¿En qué le ayudo?"},
            {"rol": "cliente", "contenido": "q onda tienen el modelo 3 pero en rojo??"},
        ]
        RegistroAprendizaje(mensajes=mensajes, guardar=guardados.append).anotar(
            "no_entendio", "victoria", "No entendí qué modelo", 7, lead={"id": 3, "contacto_id": 9, "producto_sku": "X"}
        )
        caso = guardados[0]
        assert caso["mensaje_cliente"] == "q onda tienen el modelo 3 pero en rojo??"
        assert caso["lead_id"] == 3 and caso["contacto_id"] == 9 and caso["etapa"] == "datos" and caso["producto_sku"] == "X"
        assert [m["rol"] for m in caso["contexto"]["mensajes"]] == ["bot", "cliente"]

    def test_si_guardar_falla_la_venta_sigue(self):
        def explota(_):
            raise RuntimeError("base caída")

        RegistroAprendizaje(guardar=explota).anotar("otro", "victoria", "x", 1)  # no lanza

    def test_en_ensayo_no_se_guarda_nada(self):
        assert RegistroQueNoGuarda().anotar("otro", "victoria", "x", 1) is None


class TestBaseYApi:
    def setup_method(self):
        self.conversacion, self.lead = _conversacion_con_lead()

    def teardown_method(self):
        borrar_conversaciones_de_prueba(TEL)

    @responses.activate
    def test_se_guarda_se_lista_se_resume_y_se_revisa(self):
        RegistroAprendizaje(leads=LeadRepository, mensajes=MensajeRepository, conversaciones=ConversacionRepository).anotar(
            "fuera_de_reglas", "victoria", "Pidió 50% de descuento", self.conversacion["id"]
        )
        mock_login_ok()
        c = _client()
        lista = c.get("/aprendizaje?estado=pendiente&tipo=fuera_de_reglas", headers=AUTH_HEADER).get_json()
        caso = next(x for x in lista["casos"] if x["conversacionId"] == self.conversacion["id"])
        assert caso["mensajeCliente"] == "¿qué temperatura hace hoy?" and caso["tipoNombre"] == "Pidió algo fuera de las reglas"
        assert caso["cliente"] and caso["mensajes"][-1]["texto"] == "¿qué temperatura hace hoy?"

        resumen = c.get("/aprendizaje/resumen?dias=30", headers=AUTH_HEADER).get_json()
        assert resumen["pendientes"] >= 1 and any(t["tipo"] == "fuera_de_reglas" for t in resumen["porTipo"])
        assert {"tipo": "otro", "nombre": "Otro motivo"} in resumen["tipos"]

        r = c.patch(f"/aprendizaje/{caso['id']}", json={"estado": "resuelto", "accion": "instrucciones", "categoria": "descuentos", "nota": "Se aclaró"}, headers=AUTH_HEADER)
        assert r.status_code == 200 and r.get_json()["estado"] == "resuelto" and r.get_json()["revisadoPor"]
        r = c.patch(f"/aprendizaje/{caso['id']}", json={"estado": "pendiente"}, headers=AUTH_HEADER)
        assert r.get_json()["revisadoEn"] is None

    @responses.activate
    def test_la_api_rechaza_valores_desconocidos(self):
        mock_login_ok()
        c = _client()
        assert c.get("/aprendizaje?tipo=raro", headers=AUTH_HEADER).status_code == 422
        assert c.patch("/aprendizaje/999999999", json={"estado": "resuelto"}, headers=AUTH_HEADER).status_code == 404
        assert c.patch("/aprendizaje/1", json={"estado": "cualquiera"}, headers=AUTH_HEADER).status_code == 422

    def test_tomar_una_conversacion_que_atendia_victoria_se_anota(self):
        servicio = ConversacionesService(canales=MagicMock(), anuncio_servicio=MagicMock())
        servicio.tomar(self.conversacion["id"])
        servicio.tomar(self.conversacion["id"])  # la segunda vez ya era del dueño: no se anota otra vez
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("select tipo, origen from victoria_aprendizaje where conversacion_id = %s", (self.conversacion["id"],))
                assert cur.fetchall() == [("dueno_intervino", "dueno")]


class TestDatosDeEnvio:
    def setup_method(self):
        self.conversacion, self.lead = _conversacion_con_lead()
        LeadRepository.actualizar_datos_cliente(self.lead["id"], nombre_cliente="Ana", canton="GUAYAQUIL", provincia="GUAYAS")
        LeadRepository.actualizar_tipo_entrega(self.lead["id"], "agencia", "una por el centro")
        LeadRepository.marcar_confirmacion_pedida(self.lead["id"])
        LeadRepository.confirmar_datos(self.lead["id"])

    def teardown_method(self):
        borrar_conversaciones_de_prueba(TEL)

    @responses.activate
    def test_el_dueno_define_la_agencia_y_el_cliente_debe_volver_a_confirmar(self):
        mock_login_ok()
        c = _client()
        r = c.put(
            f"/conversaciones/{self.conversacion['id']}/datos-envio",
            json={"tipoEntrega": "agencia", "direccion": "Servientrega Centro, 9 de Octubre 100", "indicacionesEntrega": "RETIRO EN AGENCIA"},
            headers=AUTH_HEADER,
        )
        assert r.status_code == 200
        lead = LeadRepository.obtener_por_id(self.lead["id"])
        assert lead["direccion"] == "Servientrega Centro, 9 de Octubre 100" and lead["agencia_definida_en"] is not None
        assert lead["agencia_definida_por"] and lead["datos_confirmados_en"] is None
        detalle = c.get(f"/conversaciones/{self.conversacion['id']}", headers=AUTH_HEADER).get_json()
        assert detalle["lead"]["tipoEntrega"] == "agencia" and detalle["lead"]["agenciaIndicada"] == "una por el centro"
        assert detalle["lead"]["agenciaDefinidaEn"] and detalle["lead"]["indicacionesEntrega"] == "RETIRO EN AGENCIA"

    @responses.activate
    def test_una_ciudad_que_no_existe_no_se_guarda(self):
        mock_login_ok()
        r = _client().put(
            f"/conversaciones/{self.conversacion['id']}/datos-envio", json={"canton": "Ciudad Inventada XYZ"}, headers=AUTH_HEADER
        )
        assert r.status_code == 422 and LeadRepository.obtener_por_id(self.lead["id"])["canton"] == "GUAYAQUIL"

    @responses.activate
    def test_un_pedido_ya_creado_no_se_cambia(self):
        LeadRepository.actualizar_despacho(self.lead["id"], id_pedido_local=123, id_pedido_rocketfy=None)
        mock_login_ok()
        r = _client().put(f"/conversaciones/{self.conversacion['id']}/datos-envio", json={"direccion": "otra"}, headers=AUTH_HEADER)
        assert r.status_code == 409

    @responses.activate
    def test_el_pedido_manual_no_se_crea_si_la_venta_ya_tiene_pedido(self):
        LeadRepository.actualizar_despacho(self.lead["id"], id_pedido_local=123, id_pedido_rocketfy=None)
        mock_login_ok()
        r = _client().post(
            "/pedidos",
            json={
                "idLocal": 99, "nombreCliente": "Ana", "telefono": TEL, "direccion": "x", "canton": "GUAYAQUIL", "provincia": "GUAYAS",
                "total": "10.00", "lineas": [{"sku": "X", "nombre": "X", "cantidad": 1}], "conversacionId": self.conversacion["id"],
            },
            headers=AUTH_HEADER,
        )
        assert r.status_code == 409 and "ya tiene un pedido" in r.get_json()["error"]
