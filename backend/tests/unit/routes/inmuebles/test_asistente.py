"""
El asistente de inmuebles con una IA falsa y repositorios en memoria: qué herramientas usa, qué manda al cliente (siempre datos
de la ficha, nunca de la IA) y que no toca nada de la tienda (leads, pedidos).
"""
from decimal import Decimal
from unittest.mock import MagicMock

from src.integrations.llm.contratos import LlamadaHerramienta, LLMProvider, RespuestaLLM, texto_del_system
from src.routes.inmuebles.asistente import AsistenteInmueblesService, presentacion
from src.routes.inmuebles.herramientas import HerramientasInmuebles

CASA = {
    "id": 7, "codigo": "CASA-GYE-01", "titulo": "Casa en Guayaquil", "tipo": "casa", "operacion": "venta", "estado": "activo",
    "precio": Decimal("85000.00"), "mostrar_precio": False, "precio_negociable": None, "ciudad": "Guayaquil", "sector": "Norte",
    "direccion": "Av. Principal", "referencia_llegada": "Frente al parque", "latitud": Decimal("-2.170998"),
    "longitud": Decimal("-79.922359"), "habitaciones": 3, "banos": Decimal("2"), "descripcion": "Casa amplia.",
    "horarios_visita": "Sábados de 9 a 13",
}


class LLMFalso(LLMProvider):
    def __init__(self, respuestas):
        self._respuestas = list(respuestas)
        self.systems = []

    def generar_respuesta(self, system, mensajes, herramientas, max_tokens=1024):
        self.systems.append(texto_del_system(system))
        self.herramientas = [h.nombre for h in herramientas]
        return self._respuestas.pop(0)


def _texto(texto):
    return RespuestaLLM(texto=texto, llamadas_herramientas=[], razon_de_parada="fin")


def _usa(nombre, entrada, texto=""):
    return RespuestaLLM(texto=texto, llamadas_herramientas=[LlamadaHerramienta(id=f"t-{nombre}", nombre=nombre, entrada=entrada)], razon_de_parada="necesita_herramientas")


class Conversaciones:
    def __init__(self, conversacion):
        self.c = dict(conversacion)
        self.escaladas = []

    def obtener_por_id(self, _id):
        return dict(self.c)

    def fijar_asistente(self, _id, asistente, inmueble_id=None):
        self.c["asistente"], self.c["inmueble_id"] = asistente, inmueble_id

    def marcar_escalada(self, _id):
        self.escaladas.append(_id)
        self.c["estado"] = "escalada"


class Mensajes:
    def __init__(self, filas):
        self.filas = list(filas)

    def obtener_por_conversacion(self, _id):
        return list(self.filas)

    def crear(self, conversacion_id, rol, contenido, tipo="texto", wamid=None, creado_en=None, **_):
        fila = {"id": len(self.filas) + 1, "conversacion_id": conversacion_id, "rol": rol, "contenido": contenido, "tipo": tipo, "creado_en": None}
        self.filas.append(fila)
        return fila

    def contar_fotos(self, conversacion_id, codigo):
        return sum(1 for f in self.filas if f["tipo"] in ("imagen", "video") and f"({codigo})" in f["contenido"])


class Inmuebles:
    def __init__(self, *activos):
        self.activos = list(activos)

    def obtener(self, inmueble_id):
        return next((i for i in self.activos if i["id"] == inmueble_id), None)

    def obtener_por_codigo(self, codigo):
        return next((i for i in self.activos if i["codigo"].lower() == codigo.lower()), None)

    def listar_activos(self):
        return [i for i in self.activos if i["estado"] == "activo"]


class Material:
    def __init__(self, archivos=()):
        self.archivos = list(archivos)

    def listar(self, inmueble_id):
        return list(self.archivos)


class Visitas:
    def __init__(self):
        self.filas = []

    def de_conversacion(self, _id):
        return list(self.filas)

    def abierta_de(self, conversacion_id, inmueble_id):
        return next((v for v in self.filas if v["estado"] in ("solicitada", "confirmada")), None)

    def crear(self, datos):
        fila = {"id": len(self.filas) + 1, "inmueble_codigo": "CASA-GYE-01", **datos}
        self.filas.append(fila)
        return fila

    def actualizar(self, visita_id, cambios):
        fila = next(v for v in self.filas if v["id"] == visita_id)
        fila.update(cambios)
        return fila


CONVERSACION = {
    "id": 1, "contacto_id": 10, "canal": "whatsapp", "id_externo": "593990001101", "telefono": "593990001101",
    "nombre_perfil": "María", "estado": "activa", "asistente": "inmuebles", "inmueble_id": None, "numero_negocio": "880000000001",
}


def _armar(respuestas, *inmuebles, material=(), historial=None):
    conversaciones = Conversaciones(CONVERSACION)
    mensajes = Mensajes(historial or [{"id": 1, "rol": "cliente", "contenido": "Hola, info de la casa", "tipo": "texto", "creado_en": None}])
    canal = MagicMock()
    canales = MagicMock()
    canales.para_conversacion.return_value = canal
    telegram = MagicMock()
    inmuebles_repo = Inmuebles(*(inmuebles or (CASA,)))
    visitas = Visitas()
    herramientas = HerramientasInmuebles(
        inmuebles=inmuebles_repo, material=Material(material), visitas=visitas, conversaciones=conversaciones,
        mensajes=mensajes, canales=canales, telegram=telegram,
    )
    llm = LLMFalso(respuestas)
    servicio = AsistenteInmueblesService(
        llm_client=llm, conversacion_repo=conversaciones, mensaje_repo=mensajes, ejecutor=herramientas,
        inmuebles=inmuebles_repo, material=Material(material), visitas=visitas, max_turnos_herramientas=4,
        max_mensajes_historial=20,
    )
    return servicio, llm, conversaciones, mensajes, canal, telegram, visitas


def test_presentacion_sin_nombre_y_con_nombre():
    assert "No te presentas con un nombre" in presentacion("Sin nombre", "el propietario")
    assert "Te llamas Sofía" in presentacion("Sofía", "el propietario")


def test_una_sola_propiedad_activa_queda_asignada_y_su_ficha_va_en_las_instrucciones():
    servicio, llm, conversaciones, mensajes, *_ = _armar([_texto("Hola, con gusto. ¿Qué le gustaría saber?")])
    assert servicio.procesar_turno(1) == "Hola, con gusto. ¿Qué le gustaría saber?"
    assert conversaciones.c["inmueble_id"] == 7
    system = llm.systems[0]
    assert "CASA-GYE-01" in system and "Frente al parque" in system
    assert "NO lo digas" in system  # el precio está oculto en esta ficha
    assert "Victoria" not in system and "AzoShop" not in system
    assert llm.herramientas == ["enviar_ubicacion", "enviar_material", "solicitar_visita", "pasar_al_dueno"]
    assert mensajes.filas[-1]["rol"] == "bot"


def test_con_varias_propiedades_pregunta_cual():
    local = {**CASA, "id": 8, "codigo": "LOCAL-01", "titulo": "Local comercial", "tipo": "local"}
    servicio, llm, conversaciones, *_ = _armar([_texto("¿Por cuál propiedad nos escribe?")], CASA, local)
    servicio.procesar_turno(1)
    assert conversaciones.c["inmueble_id"] is None
    assert "Pregúntale con amabilidad cuál le interesa" in llm.systems[0] and "LOCAL-01" in llm.systems[0]


def test_la_ubicacion_sale_de_la_ficha_como_pin():
    servicio, _, _, mensajes, canal, *_ = _armar([
        _usa("enviar_ubicacion", {"codigo": "casa-gye-01"}),
        _texto("Le envié la ubicación. Queda frente al parque."),
    ])
    assert servicio.procesar_turno(1) == "Le envié la ubicación. Queda frente al parque."
    canal.enviar_ubicacion.assert_called_once_with("593990001101", -2.170998, -79.922359, "Casa en Guayaquil", "Av. Principal")
    assert any(f["tipo"] == "ubicacion" and "maps.google.com/?q=-2.170998,-79.922359" in f["contenido"] for f in mensajes.filas)


def test_fotos_sin_repetir():
    material = [{"url": "https://x.supabase.co/a.jpg", "storage_path": "i7/a.jpg"}, {"url": "https://x.supabase.co/b.mp4", "storage_path": "i7/b.mp4"}]
    servicio, _, _, mensajes, canal, *_ = _armar([
        _usa("enviar_material", {"codigo": "CASA-GYE-01"}), _texto("Listo, le mandé las fotos."),
    ], material=material)
    servicio.procesar_turno(1)
    canal.enviar_imagen.assert_called_once()
    canal.enviar_video.assert_called_once()
    herramientas = servicio._herramientas
    assert "Ya le enviaste todas" in herramientas.ejecutar("enviar_material", 1, {"codigo": "CASA-GYE-01"}, "x").contenido


def test_pedido_de_visita_no_confirma_y_avisa_por_telegram():
    servicio, _, _, _, _, telegram, visitas = _armar([
        _usa("solicitar_visita", {"codigo": "CASA-GYE-01", "preferencia": "el sábado a las 10", "nombre_cliente": "María", "personas": 2}),
        _texto("Perfecto, el propietario le confirma el horario en breve."),
    ])
    servicio.procesar_turno(1)
    assert visitas.filas[0]["estado"] == "solicitada" and visitas.filas[0]["preferencia_cliente"] == "el sábado a las 10"
    assert visitas.filas[0]["personas"] == 2 and visitas.filas[0]["creada_por"] == "asistente"
    titulo, detalle = telegram.notificar_aviso.call_args.args
    assert "Pedido de visita nuevo" in titulo and "el sábado a las 10" in detalle
    # Si cambia de idea, se actualiza la misma visita (no se crea otra).
    resultado = servicio._herramientas.ejecutar("solicitar_visita", 1, {"codigo": "CASA-GYE-01", "preferencia": "mejor el domingo"}, "y")
    assert len(visitas.filas) == 1 and visitas.filas[0]["preferencia_cliente"] == "mejor el domingo"
    assert "NO le confirmes" in resultado.contenido


def test_una_visita_confirmada_que_cambia_vuelve_a_por_confirmar():
    servicio, *_, visitas = _armar([_texto("ok")])
    visitas.filas.append({"id": 1, "estado": "confirmada", "fecha_hora": "x", "inmueble_codigo": "CASA-GYE-01"})
    servicio._herramientas.ejecutar("solicitar_visita", 1, {"codigo": "CASA-GYE-01", "preferencia": "el lunes"}, "z")
    assert visitas.filas[0]["estado"] == "solicitada" and visitas.filas[0]["fecha_hora"] is None


def test_una_propiedad_vendida_no_agenda():
    servicio, *_, visitas = _armar([_texto("ok")], {**CASA, "estado": "vendido"})
    resultado = servicio._herramientas.ejecutar("solicitar_visita", 1, {"codigo": "CASA-GYE-01", "preferencia": "hoy"}, "z")
    assert "no está disponible" in resultado.contenido and visitas.filas == []


def test_pasar_al_dueno_escala_y_corta():
    servicio, llm, conversaciones, _, _, telegram, _ = _armar([
        _usa("pasar_al_dueno", {"motivo": "Ofrece 70 mil"}), _texto("El propietario le escribe en breve."),
    ])
    assert servicio.procesar_turno(1) == "El propietario le escribe en breve."
    assert conversaciones.escaladas == [1]
    assert telegram.notificar_escalado.call_args.args[2] == "Ofrece 70 mil"


def test_codigo_inventado():
    servicio, *_ = _armar([_texto("ok")])
    assert "No encontré" in servicio._herramientas.ejecutar("enviar_ubicacion", 1, {"codigo": "NO-EXISTE"}, "z").contenido


def test_sin_texto_pasa_al_dueno_con_el_mensaje_del_parametro():
    servicio, _, conversaciones, *_ = _armar([_texto("")])
    texto = servicio.procesar_turno(1)
    assert conversaciones.escaladas == [1]
    assert "propietario" in texto.lower()


def test_nada_sin_responder_no_hace_nada():
    servicio, llm, *_ = _armar([], historial=[
        {"id": 1, "rol": "cliente", "contenido": "Hola", "tipo": "texto", "creado_en": None},
        {"id": 2, "rol": "bot", "contenido": "Hola", "tipo": "texto", "creado_en": None},
    ])
    assert servicio.procesar_turno(1) == ""
    assert llm.systems == []
