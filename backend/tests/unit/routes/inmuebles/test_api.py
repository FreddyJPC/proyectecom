"""La API de «Inmuebles» de punta a punta contra la base de pruebas: rutas, códigos HTTP y nombres en camelCase."""
import pytest
import responses

from src.app import create_app
from src.routes.whatsapp.repository import ConversacionRepository
from tests.conftest import AUTH_HEADER, mock_login_ok
from tests.helpers_db import borrar_conversaciones_de_prueba, borrar_inmuebles_de_prueba, borrar_numeros_de_prueba

CODIGO = "TEST-API-CASA"
TELEFONO = "593990001202"
NUMERO = "880000000202"


@pytest.fixture(autouse=True)
def limpiar():
    borrar_conversaciones_de_prueba(TELEFONO)
    borrar_inmuebles_de_prueba(CODIGO)
    borrar_numeros_de_prueba(NUMERO)
    yield
    borrar_conversaciones_de_prueba(TELEFONO)
    borrar_inmuebles_de_prueba(CODIGO)
    borrar_numeros_de_prueba(NUMERO)


def _cliente():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


@responses.activate
def test_ciclo_completo_de_una_propiedad_y_su_agenda():
    mock_login_ok()
    c = _cliente()
    r = c.post("/inmuebles", json={"codigo": CODIGO, "titulo": "Casa API", "precio": "85000", "mostrarPrecio": True}, headers=AUTH_HEADER)
    assert r.status_code == 201, r.get_json()
    casa = r.get_json()
    assert casa["estado"] == "borrador" and casa["precio"] == "85000.00" and casa["mostrarPrecio"] is True
    assert "Fotos o videos" in casa["faltantes"]

    r = c.put(f"/inmuebles/{casa['id']}/estado", json={"estado": "activo"}, headers=AUTH_HEADER)
    assert r.status_code == 422 and "sector" in r.get_json()["error"]

    r = c.put(f"/inmuebles/{casa['id']}", json={"sector": "Norte", "descripcion": "Linda casa", "latitud": "-2.17", "longitud": "-79.92"}, headers=AUTH_HEADER)
    assert r.status_code == 200 and r.get_json()["latitud"] == "-2.170000"
    assert c.put(f"/inmuebles/{casa['id']}/estado", json={"estado": "activo"}, headers=AUTH_HEADER).get_json()["estado"] == "activo"

    lista = c.get("/inmuebles", headers=AUTH_HEADER).get_json()
    assert any(i["codigo"] == CODIGO and i["visitasPorConfirmar"] == 0 for i in lista)

    r = c.post(f"/inmuebles/{casa['id']}/material", json={"storagePath": f"i{casa['id']}/foto.jpg"}, headers=AUTH_HEADER)
    assert r.status_code == 200 and r.get_json()["material"][0]["tipo"] == "imagen"

    r = c.post(f"/inmuebles/{casa['id']}/anuncios", json={"idAnuncio": "1200000000990202", "nombre": "Video"}, headers=AUTH_HEADER)
    assert r.status_code == 200 and r.get_json()["anuncios"][0]["idAnuncio"] == "1200000000990202"

    r = c.post("/visitas", json={"inmuebleId": casa["id"], "nombreCliente": "Pedro", "preferenciaCliente": "el sábado"}, headers=AUTH_HEADER)
    assert r.status_code == 201
    visita = r.get_json()
    assert visita["estado"] == "solicitada" and visita["inmuebleCodigo"] == CODIGO and visita["ventanaAbierta"] is False

    r = c.put(f"/visitas/{visita['id']}/confirmar", json={"fechaHora": "2026-11-28T10:00:00-05:00", "encargado": "Ana"}, headers=AUTH_HEADER)
    assert r.status_code == 200
    assert r.get_json()["fechaHora"].startswith("2026-11-28T15:00:00")  # se guarda en UTC

    aviso = c.get(f"/visitas/{visita['id']}/aviso", headers=AUTH_HEADER).get_json()["texto"]
    assert "sábado 28 de noviembre a las 10:00" in aviso and "Hola Pedro" in aviso

    r = c.post(f"/visitas/{visita['id']}/avisar", json={}, headers=AUTH_HEADER)
    assert r.status_code == 422  # sin conversación de WhatsApp: se avisa por teléfono

    agenda = c.get("/visitas?desde=2026-11-28&hasta=2026-11-28", headers=AUTH_HEADER).get_json()
    assert any(v["id"] == visita["id"] for v in agenda)
    otra_semana = c.get("/visitas?desde=2026-12-01&hasta=2026-12-02", headers=AUTH_HEADER).get_json()
    assert all(v["id"] != visita["id"] for v in otra_semana)
    assert c.get("/visitas?desde=28-11-2026", headers=AUTH_HEADER).status_code == 422

    r = c.put(f"/visitas/{visita['id']}/estado", json={"estado": "realizada"}, headers=AUTH_HEADER)
    assert r.get_json()["estado"] == "realizada"
    resumen = c.get("/visitas/resumen", headers=AUTH_HEADER).get_json()
    assert set(resumen) == {"porConfirmar", "proximas", "hoy"}


@responses.activate
def test_errores_claros():
    mock_login_ok()
    c = _cliente()
    assert c.get("/inmuebles/999999999", headers=AUTH_HEADER).status_code == 404
    r = c.post("/inmuebles", json={"codigo": "x", "titulo": "Casa"}, headers=AUTH_HEADER)
    assert r.status_code == 422  # código muy corto
    r = c.post("/inmuebles", json={"codigo": CODIGO, "titulo": "Casa", "tipo": "castillo"}, headers=AUTH_HEADER)
    assert r.status_code == 422
    assert c.post("/inmuebles", json={"codigo": CODIGO, "titulo": "Casa"}, headers=AUTH_HEADER).status_code == 201
    assert c.post("/inmuebles", json={"codigo": CODIGO, "titulo": "Otra"}, headers=AUTH_HEADER).status_code == 409
    assert c.put("/visitas/999999999/confirmar", json={"fechaHora": "2026-11-28T10:00:00-05:00"}, headers=AUTH_HEADER).status_code == 404
    # Una fecha sin zona horaria se rechaza: la hora siempre se manda con su zona (Ecuador, -05:00).
    assert c.put("/visitas/1/confirmar", json={"fechaHora": "2026-11-28T10:00:00"}, headers=AUTH_HEADER).status_code == 422


@responses.activate
def test_numeros_y_asistente_de_una_conversacion():
    mock_login_ok()
    c = _cliente()
    r = c.put("/numeros-whatsapp", json={"phoneNumberId": NUMERO, "nombre": "Casa Guayaquil", "asistente": "inmuebles"}, headers=AUTH_HEADER)
    assert r.status_code == 200 and r.get_json()["asistente"] == "inmuebles"
    numeros = c.get("/numeros-whatsapp", headers=AUTH_HEADER).get_json()
    assert any(n["phoneNumberId"] == NUMERO and n["esPrincipal"] is False for n in numeros)
    assert c.delete(f"/numeros-whatsapp/{NUMERO}", headers=AUTH_HEADER).status_code == 200

    casa = c.post("/inmuebles", json={"codigo": CODIGO, "titulo": "Casa"}, headers=AUTH_HEADER).get_json()
    conversacion = ConversacionRepository.crear(id_externo=TELEFONO)
    r = c.put(f"/inmuebles/conversaciones/{conversacion['id']}/asistente", json={"asistente": "inmuebles", "inmuebleId": casa["id"]}, headers=AUTH_HEADER)
    assert r.status_code == 200
    detalle = c.get(f"/conversaciones/{conversacion['id']}", headers=AUTH_HEADER).get_json()
    assert detalle["conversacion"]["asistente"] == "inmuebles" and detalle["conversacion"]["inmuebleTitulo"] == "Casa"
    lista = c.get("/conversaciones?asistente=inmuebles", headers=AUTH_HEADER).get_json()
    fila = next(i for i in lista["items"] if i["id"] == conversacion["id"])
    assert fila["asistente"] == "inmuebles" and fila["productoInteres"] == "Casa"
