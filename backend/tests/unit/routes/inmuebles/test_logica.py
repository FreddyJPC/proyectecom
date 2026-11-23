"""Reglas puras del módulo «Inmuebles»: lo que sabe el asistente, las fechas en hora de Ecuador y la agenda."""
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from src.routes.inmuebles.logica import (
    TransicionDeVisitaInvalida,
    catalogo_para_el_asistente,
    dinero,
    faltantes,
    fecha_legible,
    ficha_para_el_asistente,
    hora_legible,
    precio_para_el_asistente,
    requisitos_para_activar,
    texto_confirmacion,
    validar_transicion,
    visitas_para_el_asistente,
)

CASA = {
    "id": 1, "codigo": "CASA-GYE-01", "titulo": "Casa de dos pisos en Guayaquil", "tipo": "casa", "operacion": "venta",
    "estado": "activo", "precio": Decimal("85000.00"), "mostrar_precio": True, "precio_negociable": None,
    "ciudad": "Guayaquil", "sector": "Norte", "direccion": "Av. Principal y calle 5", "referencia_llegada": "Frente al parque",
    "latitud": Decimal("-2.170998"), "longitud": Decimal("-79.922359"), "terreno_m2": Decimal("200.00"),
    "construccion_m2": Decimal("180.50"), "frente_m": Decimal("10.00"), "fondo_m": Decimal("20.00"), "pisos": 2,
    "habitaciones": 3, "banos": Decimal("2.5"), "parqueaderos": 1, "uso": "comercial", "descripcion": "Casa amplia.",
    "caracteristicas": None, "servicios": "Agua, luz", "documentacion": "Escrituras al día", "preguntas_frecuentes": None,
    "temas_no_responder": None, "horarios_visita": "Lunes a sábado de 9:00 a 17:00", "encargado_visitas": "Don Luis",
}


class TestFechasEnEcuador:
    def test_la_hora_del_cliente_es_la_de_ecuador(self):
        # 2026-11-29 15:30 UTC = domingo 29 de noviembre, 10:30 en Ecuador
        momento = datetime(2026, 11, 29, 15, 30, tzinfo=timezone.utc)
        assert fecha_legible(momento) == "domingo 29 de noviembre"
        assert hora_legible(momento) == "10:30"

    def test_cerca_de_medianoche_cambia_el_dia(self):
        # 2026-11-30 03:00 UTC = 29 de noviembre a las 22:00 en Ecuador
        momento = datetime(2026, 11, 30, 3, 0, tzinfo=timezone.utc)
        assert "29 de noviembre" in fecha_legible(momento)
        assert hora_legible(momento) == "22:00"


def test_dinero_nunca_es_float():
    assert dinero(Decimal("85000")) == "$85,000.00"
    assert dinero("1234.5") == "$1,234.50"


class TestFicha:
    def test_la_ficha_trae_lo_que_el_asistente_puede_decir(self):
        ficha = ficha_para_el_asistente(CASA, cantidad_material=4)
        assert "CASA-GYE-01" in ficha
        assert "10 m de frente por 20 m de fondo" in ficha
        assert "Baños: 2,5" in ficha
        assert "Construcción: 180,5 m²" in ficha
        assert "enviar_ubicacion" in ficha and "4 (usa enviar_material" in ficha
        assert "Don Luis" not in ficha  # quién enseña la casa es interno

    def test_precio_oculto_por_defecto(self):
        texto = precio_para_el_asistente({**CASA, "mostrar_precio": False})
        assert "NO lo digas" in texto and "85" not in texto

    def test_precio_visible_y_negociable(self):
        texto = precio_para_el_asistente({**CASA, "precio_negociable": True})
        assert "$85,000.00" in texto and "conversable" in texto and "pasar_al_dueno" in texto

    def test_precio_final(self):
        assert "precio final" in precio_para_el_asistente({**CASA, "precio_negociable": False})

    def test_alquiler_es_al_mes(self):
        assert "al mes" in precio_para_el_asistente({**CASA, "operacion": "alquiler"})

    def test_vendida_no_agenda(self):
        assert "YA SE VENDIÓ" in ficha_para_el_asistente({**CASA, "estado": "vendido"})

    def test_sin_fotos_no_las_promete(self):
        assert "no los prometas" in ficha_para_el_asistente(CASA, 0)

    def test_catalogo_corto(self):
        texto = catalogo_para_el_asistente([CASA, {**CASA, "codigo": "LOCAL-1", "titulo": "Local", "tipo": "local", "mostrar_precio": False}])
        assert "CASA-GYE-01: Casa de dos pisos" in texto and "$85,000.00" in texto
        assert "LOCAL-1: Local (Local comercial, Norte, Guayaquil)" in texto
        assert catalogo_para_el_asistente([]) == "(no hay propiedades disponibles en este momento)"


class TestFaltantes:
    def test_ficha_completa(self):
        assert faltantes(CASA, 3) == []

    def test_ficha_vacia(self):
        vacia = {"codigo": "X", "titulo": "X", "tipo": "casa"}
        falta = faltantes(vacia, 0)
        assert "Ubicación en el mapa (para mandar el pin)" in falta and "Fotos o videos" in falta and "Habitaciones" in falta

    def test_un_terreno_no_pide_habitaciones(self):
        terreno = {**CASA, "tipo": "terreno", "habitaciones": None, "banos": None}
        assert "Habitaciones" not in faltantes(terreno, 1)

    def test_requisitos_para_publicar(self):
        assert requisitos_para_activar(CASA) == []
        assert requisitos_para_activar({"titulo": "Casa"}) == ["el sector o la dirección", "la descripción"]


class TestTransiciones:
    @pytest.mark.parametrize("actual,nuevo", [
        ("solicitada", "confirmada"), ("solicitada", "cancelada"), ("confirmada", "confirmada"), ("confirmada", "realizada"),
        ("confirmada", "no_asistio"), ("cancelada", "solicitada"), ("realizada", "no_asistio"),
    ])
    def test_permitidas(self, actual, nuevo):
        validar_transicion(actual, nuevo)

    @pytest.mark.parametrize("actual,nuevo", [("solicitada", "realizada"), ("solicitada", "no_asistio"), ("realizada", "solicitada")])
    def test_prohibidas(self, actual, nuevo):
        with pytest.raises(TransicionDeVisitaInvalida):
            validar_transicion(actual, nuevo)


def test_texto_de_confirmacion_en_hora_de_ecuador():
    visita = {"nombre_cliente": "María José Pérez", "fecha_hora": datetime(2026, 11, 28, 15, 0, tzinfo=timezone.utc)}
    plantilla = "Hola {nombre}, su visita a {inmueble} quedó confirmada para el {fecha} a las {hora}. Referencia: {referencia}."
    texto = texto_confirmacion(plantilla, visita, CASA)
    assert texto == (
        "Hola María, su visita a Casa de dos pisos en Guayaquil quedó confirmada para el sábado 28 de noviembre a las 10:00. "
        "Referencia: Frente al parque."
    )


def test_texto_de_confirmacion_sin_nombre():
    visita = {"nombre_cliente": None, "fecha_hora": datetime(2026, 11, 28, 15, 0, tzinfo=timezone.utc)}
    assert texto_confirmacion("Hola {nombre}, listo.", visita, CASA) == "Hola, listo."


def test_visitas_para_el_asistente():
    texto = visitas_para_el_asistente([
        {"inmueble_codigo": "CASA-GYE-01", "estado": "confirmada", "fecha_hora": datetime(2026, 11, 28, 15, 0, tzinfo=timezone.utc)},
        {"inmueble_codigo": "LOCAL-1", "estado": "solicitada", "preferencia_cliente": "el lunes", "fecha_hora": None},
    ])
    assert "confirmada, el sábado 28 de noviembre a las 10:00" in texto
    assert "falta confirmar día y hora (pidió: el lunes)" in texto
    assert visitas_para_el_asistente([]) == "(todavía no ha pedido ninguna visita)"
