"""
Herramientas del asistente de inmuebles (módulo «Inmuebles», migración 037). Son pocas a propósito: el asistente INFORMA y toma
pedidos de visita; no vende, no negocia, no crea pedidos ni toca Rocketfy.

Todo dato que sale hacia el cliente (coordenadas, URLs de fotos) sale de la base, nunca de lo que escriba el modelo: el modelo
solo dice QUÉ propiedad (por su código) y QUÉ quiere hacer.
"""
import logging
from typing import Any, Callable, Dict, List, Optional

from src.config.parametros import parametros
from src.integrations.canales import etiqueta_de_cliente, get_registro_canales
from src.integrations.llm.contratos import HerramientaLLM, ResultadoHerramienta
from src.routes.imagenes.logica import PREFIJO_FOTO, PREFIJO_VIDEO, TIPO_VIDEO, galeria_para_enviar
from src.routes.whatsapp.repository import ConversacionRepository, MensajeRepository

from .logica import coordenadas, enlace_mapa, ubicacion_corta
from .repository import InmuebleRepository, MaterialInmuebleRepository, VisitaRepository

logger = logging.getLogger(__name__)

PREFIJO_UBICACION = "[Ubicación enviada — "

_CODIGO = {"type": "string", "description": "El código de la propiedad (aparece en su ficha o en la lista de propiedades)."}

HERRAMIENTAS_INMUEBLES: List[HerramientaLLM] = [
    HerramientaLLM(
        nombre="enviar_ubicacion",
        descripcion=(
            "Envía al cliente la ubicación de la propiedad como un pin de WhatsApp que se abre en su mapa. Úsala cuando pregunte "
            "dónde queda, cómo llegar o pida la ubicación. Después dile en una frase la referencia para llegar."
        ),
        parametros={"type": "object", "properties": {"codigo": _CODIGO}, "required": ["codigo"]},
    ),
    HerramientaLLM(
        nombre="enviar_material",
        descripcion=(
            "Envía al cliente las fotos y videos de la propiedad, en el orden de su galería y sin repetir lo que ya se le mandó. "
            "Úsala cuando pida fotos, videos o «ver la casa»."
        ),
        parametros={"type": "object", "properties": {"codigo": _CODIGO}, "required": ["codigo"]},
    ),
    HerramientaLLM(
        nombre="solicitar_visita",
        descripcion=(
            "Registra que el cliente QUIERE visitar la propiedad, con el día y la hora que prefiere en sus palabras. NO confirma la "
            "visita: la confirma el propietario y luego se le avisa al cliente. Úsala cuando el cliente haya dicho que quiere ir y "
            "cuándo le conviene (o que le da igual). Si ya la había pedido y cambia de día u hora, úsala otra vez: se actualiza."
        ),
        parametros={
            "type": "object",
            "properties": {
                "codigo": _CODIGO,
                "nombre_cliente": {"type": "string", "description": "Su nombre, si lo dijo."},
                "preferencia": {
                    "type": "string",
                    "description": "El día y la hora que prefiere, tal como lo dijo («el sábado en la mañana», «cualquier día después de las 5»).",
                },
                "personas": {"type": "integer", "description": "Cuántas personas irían, si lo dijo."},
                "nota": {"type": "string", "description": "Algo útil para el propietario (p. ej. «viene con su arquitecto»)."},
            },
            "required": ["codigo", "preferencia"],
        },
    ),
    HerramientaLLM(
        nombre="pasar_al_dueno",
        descripcion=(
            "Pasa la conversación al propietario. Úsala cuando el cliente pregunte algo que no está en la ficha, haga una oferta o "
            "pida rebaja, pregunte por financiamiento, papeles o algo delicado, pida hablar con una persona, o cuando no entiendas "
            "qué quiere después de dos intentos. Después dile al cliente que el propietario le escribirá."
        ),
        parametros={
            "type": "object",
            "properties": {
                "motivo": {"type": "string", "description": "Qué necesita el cliente, en una frase, para que el propietario lo entienda sin leer todo."},
            },
            "required": ["motivo"],
        },
    ),
]


class HerramientasInmuebles:
    """Ejecuta las herramientas del asistente de inmuebles. Cada una devuelve un texto PARA EL MODELO (qué pasó y qué decirle
    al cliente); ninguna lanza: un fallo se le explica para que responda con naturalidad."""

    def __init__(
        self,
        inmuebles: Optional[InmuebleRepository] = None,
        material: Optional[MaterialInmuebleRepository] = None,
        visitas: Optional[VisitaRepository] = None,
        conversaciones: Optional[ConversacionRepository] = None,
        mensajes: Optional[MensajeRepository] = None,
        canales=None,
        telegram=None,
    ):
        self._inmuebles = inmuebles or InmuebleRepository()
        self._material = material or MaterialInmuebleRepository()
        self._visitas = visitas or VisitaRepository()
        self._conversaciones = conversaciones or ConversacionRepository()
        self._mensajes = mensajes or MensajeRepository()
        self._canales_fijo = canales
        self._telegram_fijo = telegram
        self._manejadores: Dict[str, Callable[[int, dict], str]] = {
            "enviar_ubicacion": self._enviar_ubicacion,
            "enviar_material": self._enviar_material,
            "solicitar_visita": self._solicitar_visita,
            "pasar_al_dueno": self._pasar_al_dueno,
        }

    # -- infraestructura --------------------------------------------------------------------------------------------------

    def _canales(self):
        if self._canales_fijo is None:
            self._canales_fijo = get_registro_canales()
        return self._canales_fijo

    def _telegram(self):
        if self._telegram_fijo is None:
            from src.integrations.telegram import get_telegram_notifier  # perezoso: no se arma si no hace falta

            self._telegram_fijo = get_telegram_notifier()
        return self._telegram_fijo

    def ejecutar(self, nombre: str, conversacion_id: int, entrada: dict, id_llamada: str) -> ResultadoHerramienta:
        manejador = self._manejadores.get(nombre)
        if manejador is None:
            contenido = f"Herramienta desconocida: {nombre}."
        else:
            try:
                contenido = manejador(conversacion_id, entrada or {})
            except Exception:
                logger.exception("Falló la herramienta %s del asistente de inmuebles", nombre, extra={"conversacion_id": conversacion_id})
                contenido = (
                    "No se pudo completar en este momento. Dile al cliente con naturalidad que en un momento le ayudas con eso, "
                    "y usa pasar_al_dueno si es importante."
                )
        return ResultadoHerramienta(id_llamada=id_llamada, contenido=contenido)

    def _propiedad(self, conversacion_id: int, entrada: dict) -> Optional[dict]:
        """La propiedad por su código; y queda anotada en la conversación (así el resto de la charla ya sabe de cuál se habla)."""
        codigo = str(entrada.get("codigo") or "").strip()
        inmueble = self._inmuebles.obtener_por_codigo(codigo) if codigo else None
        if inmueble is None:
            return None
        conversacion = self._conversaciones.obtener_por_id(conversacion_id)
        if conversacion and conversacion.get("inmueble_id") != inmueble["id"]:
            self._conversaciones.fijar_asistente(conversacion_id, "inmuebles", inmueble["id"])
        return inmueble

    @staticmethod
    def _no_encontrada() -> str:
        return "No encontré una propiedad con ese código. Revisa la lista de propiedades disponibles y usa el código exacto."

    # -- herramientas -----------------------------------------------------------------------------------------------------

    def _enviar_ubicacion(self, conversacion_id: int, entrada: dict) -> str:
        inmueble = self._propiedad(conversacion_id, entrada)
        if inmueble is None:
            return self._no_encontrada()
        punto = coordenadas(inmueble)
        if punto is None:
            referencia = inmueble.get("referencia_llegada") or inmueble.get("direccion") or ubicacion_corta(inmueble)
            return (
                "Esta propiedad no tiene la ubicación en el mapa. "
                + (f"Dale esta referencia: {referencia}. " if referencia else "")
                + "Si el cliente necesita el punto exacto, usa pasar_al_dueno."
            )
        conversacion = self._conversaciones.obtener_por_id(conversacion_id)
        try:
            self._canales().para_conversacion(conversacion).enviar_ubicacion(
                conversacion["id_externo"], punto[0], punto[1], inmueble["titulo"],
                inmueble.get("direccion") or ubicacion_corta(inmueble) or None,
            )
        except Exception:
            logger.warning("No se pudo enviar la ubicación", exc_info=True, extra={"conversacion_id": conversacion_id})
            return "No se pudo enviar la ubicación en este momento. Dale la referencia para llegar con palabras."
        self._mensajes.crear(
            conversacion_id=conversacion_id, rol="bot", contenido=f"{PREFIJO_UBICACION}{enlace_mapa(inmueble)}]", tipo="ubicacion",
            wamid=None,
        )
        referencia = inmueble.get("referencia_llegada")
        return "Ya le enviaste la ubicación. " + (
            f"Dile en una frase cómo llegar: {referencia}." if referencia else "Dile que ahí puede ver cómo llegar."
        )

    def _enviar_material(self, conversacion_id: int, entrada: dict) -> str:
        inmueble = self._propiedad(conversacion_id, entrada)
        if inmueble is None:
            return self._no_encontrada()
        galeria = galeria_para_enviar(self._material.listar(inmueble["id"]))
        if not galeria:
            return "Esta propiedad todavía no tiene fotos ni videos. Díselo con naturalidad y descríbela con su ficha; no prometas fotos."
        ya_enviadas = self._mensajes.contar_fotos(conversacion_id, inmueble["codigo"])
        pendientes = galeria[ya_enviadas:]
        if not pendientes:
            return "Ya le enviaste todas las fotos y videos de esta propiedad: no los repitas. Ofrécele la ubicación o una visita."
        tanda = pendientes[: parametros.valor("bot.max_fotos_por_envio")]
        conversacion = self._conversaciones.obtener_por_id(conversacion_id)
        canal = self._canales().para_conversacion(conversacion)
        enviadas = 0
        for posicion, archivo in enumerate(tanda):
            es_video = archivo["tipo"] == TIPO_VIDEO
            descripcion = inmueble["titulo"] if ya_enviadas + posicion == 0 else None
            try:
                if es_video:
                    canal.enviar_video(conversacion["id_externo"], archivo["url"], descripcion)
                else:
                    canal.enviar_imagen(conversacion["id_externo"], archivo["url"], descripcion)
            except Exception:
                logger.warning("No se pudo enviar el material", exc_info=True, extra={"conversacion_id": conversacion_id})
                break
            self._mensajes.crear(
                conversacion_id=conversacion_id, rol="bot",
                contenido=f"{PREFIJO_VIDEO if es_video else PREFIJO_FOTO}{inmueble['titulo']} ({inmueble['codigo']})",
                tipo=TIPO_VIDEO if es_video else "imagen", wamid=None,
            )
            enviadas += 1
        if not enviadas:
            return "No se pudieron enviar las fotos en este momento. Díselo con naturalidad y descríbela con su ficha."
        quedan = len(galeria) - ya_enviadas - enviadas
        resto = f" Quedan {quedan} más: si quiere ver más, vuelve a usar esta herramienta." if quedan > 0 else ""
        return f"Ya le enviaste {enviadas} archivo(s). Puedes decirle que se los mandaste.{resto}"

    def _solicitar_visita(self, conversacion_id: int, entrada: dict) -> str:
        inmueble = self._propiedad(conversacion_id, entrada)
        if inmueble is None:
            return self._no_encontrada()
        if inmueble.get("estado") != "activo":
            return "Esta propiedad no está disponible para visitas. Díselo con amabilidad y usa pasar_al_dueno si insiste."
        preferencia = str(entrada.get("preferencia") or "").strip()[:300]
        if not preferencia:
            return "Falta saber qué día y hora prefiere el cliente. Pregúntaselo antes de registrar la visita."
        personas = entrada.get("personas")
        personas = int(personas) if isinstance(personas, (int, float)) and 1 <= int(personas) <= 50 else None
        nombre = (str(entrada.get("nombre_cliente") or "").strip() or None)
        nota = (str(entrada.get("nota") or "").strip()[:500] or None)
        conversacion = self._conversaciones.obtener_por_id(conversacion_id)

        abierta = self._visitas.abierta_de(conversacion_id, inmueble["id"])
        if abierta is not None and abierta["estado"] == "confirmada":
            # Ya estaba confirmada y el cliente quiere otro horario: vuelve a quedar por confirmar, con lo nuevo que pidió.
            visita = self._visitas.actualizar(abierta["id"], {
                "estado": "solicitada", "preferencia_cliente": preferencia, "fecha_hora": None, "confirmada_en": None,
                **({"nombre_cliente": nombre} if nombre else {}), **({"personas": personas} if personas else {}),
                **({"notas": nota} if nota else {}),
            })
            cambio = True
        elif abierta is not None:
            visita = self._visitas.actualizar(abierta["id"], {
                "preferencia_cliente": preferencia,
                **({"nombre_cliente": nombre} if nombre else {}), **({"personas": personas} if personas else {}),
                **({"notas": nota} if nota else {}),
            })
            cambio = True
        else:
            visita = self._visitas.crear({
                "inmueble_id": inmueble["id"], "conversacion_id": conversacion_id, "contacto_id": conversacion.get("contacto_id"),
                "nombre_cliente": nombre or conversacion.get("contacto_nombre") or conversacion.get("nombre_perfil"),
                "telefono": conversacion.get("telefono"), "estado": "solicitada", "preferencia_cliente": preferencia,
                "personas": personas, "notas": nota, "creada_por": "asistente",
            })
            cambio = False
        self._avisar_visita(conversacion, inmueble, visita, cambio)
        return (
            "Pedido de visita registrado. Dile al cliente que el propietario le confirma el día y la hora en breve por este mismo "
            "chat. NO le confirmes tú la visita ni le des una hora como segura."
        )

    def _avisar_visita(self, conversacion: dict, inmueble: dict, visita: dict, cambio: bool) -> None:
        try:
            cliente = etiqueta_de_cliente(conversacion.get("canal"), conversacion.get("id_externo"), conversacion.get("telefono"))
            titulo = "🗓️ Cambio en un pedido de visita" if cambio else "🗓️ Pedido de visita nuevo"
            detalle = (
                f"Propiedad: {inmueble['titulo']} ({inmueble['codigo']})\n"
                f"Cliente: {visita.get('nombre_cliente') or 'sin nombre'} · {cliente}\n"
                f"Prefiere: {visita.get('preferencia_cliente')}\n"
                + (f"Personas: {visita['personas']}\n" if visita.get("personas") else "")
                + (f"Nota: {visita['notas']}\n" if visita.get("notas") else "")
                + "Confírmala en la app (Agenda de visitas)."
            )
            self._telegram().notificar_aviso(titulo, detalle)
        except Exception:
            logger.exception("No se pudo avisar por Telegram del pedido de visita")

    def _pasar_al_dueno(self, conversacion_id: int, entrada: dict) -> str:
        motivo = str(entrada.get("motivo") or "El cliente necesita atención del propietario").strip()[:300]
        conversacion = self._conversaciones.obtener_por_id(conversacion_id)
        self._conversaciones.marcar_escalada(conversacion_id)
        try:
            inmueble = self._inmuebles.obtener(conversacion["inmueble_id"]) if conversacion.get("inmueble_id") else None
            origen = f"Propiedad: {inmueble['titulo']} ({inmueble['codigo']})" if inmueble else "Inmuebles"
            self._telegram().notificar_escalado(
                conversacion_id,
                etiqueta_de_cliente(conversacion.get("canal"), conversacion.get("id_externo"), conversacion.get("telefono")),
                motivo,
                origen=origen,
            )
        except Exception:
            logger.exception("No se pudo avisar por Telegram del paso al propietario")
        return (
            "Listo: el propietario ya tiene la conversación. Despídete en una frase diciéndole al cliente que el propietario le "
            "escribirá por este mismo chat. Este es tu último mensaje."
        )
