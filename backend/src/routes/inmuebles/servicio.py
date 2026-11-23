"""
Reglas del panel de «Inmuebles» (migración 037): fichas de propiedades, su material, los anuncios que hablan de cada una, la
agenda de visitas y los números de WhatsApp del negocio.

La agenda es MANUAL a propósito (pedido de Freddy): el asistente solo registra lo que el cliente pidió; el dueño confirma día y
hora y decide cuándo avisarle al cliente. Avisar usa la ventana de 24 h de WhatsApp: fuera de ella no se puede escribir texto
libre (haría falta una plantilla aprobada por Meta, pendiente).
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.config.parametros import parametros
from src.config.settings import load_settings
from src.integrations.canales import CanalNoDisponibleError, get_registro_canales
from src.integrations.whatsapp import WhatsAppBusinessError, WhatsAppRequestError
from src.routes.anuncios.servicio import AnuncioServicio
from src.routes.imagenes.logica import RutaDeImagenInvalida, tipo_de, url_publica, validar_ruta
from src.routes.whatsapp.repository import ConversacionRepository, MensajeRepository

from .logica import (
    ESTADOS_INMUEBLE,
    TransicionDeVisitaInvalida,
    faltantes,
    requisitos_para_activar,
    texto_confirmacion,
    validar_transicion,
)
from .repository import (
    AnuncioInmuebleRepository,
    InmuebleRepository,
    MaterialInmuebleRepository,
    NumeroWhatsappRepository,
    VisitaRepository,
)
from .ruteo import ASISTENTES, INMUEBLES

logger = logging.getLogger(__name__)

MAXIMO_MATERIAL = 20  # fotos y videos por propiedad


class InmuebleNoEncontradoError(Exception):
    pass


class VisitaNoEncontradaError(Exception):
    pass


class DatosInvalidosError(ValueError):
    pass


class VentanaCerradaError(Exception):
    """Pasaron más de 24 h desde el último mensaje del cliente: WhatsApp no deja escribirle texto libre."""


class EnvioFallidoError(Exception):
    pass


def carpeta_de_inmueble(inmueble_id: int) -> str:
    """La carpeta de la propiedad dentro del bucket `productos` (los productos usan `p<id>`)."""
    return f"i{inmueble_id}"


class InmueblesServicio:
    def __init__(
        self,
        inmuebles: Optional[InmuebleRepository] = None,
        material: Optional[MaterialInmuebleRepository] = None,
        anuncios: Optional[AnuncioInmuebleRepository] = None,
        numeros: Optional[NumeroWhatsappRepository] = None,
        conversaciones: Optional[ConversacionRepository] = None,
    ):
        self._inmuebles = inmuebles or InmuebleRepository()
        self._material = material or MaterialInmuebleRepository()
        self._anuncios = anuncios or AnuncioInmuebleRepository()
        self._numeros = numeros or NumeroWhatsappRepository()
        self._conversaciones = conversaciones or ConversacionRepository()

    # -- fichas -----------------------------------------------------------------------------------------------------------

    def listar(self, incluir_archivados: bool = False) -> List[Dict[str, Any]]:
        estados = None if incluir_archivados else [e for e in ESTADOS_INMUEBLE if e != "archivado"]
        return self._inmuebles.listar(estados)

    def detalle(self, inmueble_id: int) -> Dict[str, Any]:
        inmueble = self._inmuebles.obtener(inmueble_id)
        if inmueble is None:
            raise InmuebleNoEncontradoError("No existe esa propiedad.")
        material = self._material.listar(inmueble_id)
        for m in material:
            m["tipo"] = tipo_de(m.get("storage_path") or m["url"])
        return {
            **inmueble,
            "material": material,
            "anuncios": self._anuncios.listar_de(inmueble_id),
            "faltantes": faltantes(inmueble, len(material)),
            "carpeta": carpeta_de_inmueble(inmueble_id),
        }

    @staticmethod
    def _limpiar(datos: Dict[str, Any]) -> Dict[str, Any]:
        limpio = {}
        for clave, valor in datos.items():
            if isinstance(valor, str):
                valor = valor.strip() or None
            limpio[clave] = valor
        if "codigo" in limpio and limpio["codigo"]:
            limpio["codigo"] = limpio["codigo"].upper().replace(" ", "-")
        if ("latitud" in limpio) != ("longitud" in limpio) or (
            "latitud" in limpio and (limpio["latitud"] is None) != (limpio["longitud"] is None)
        ):
            raise DatosInvalidosError("La ubicación necesita latitud y longitud juntas.")
        return limpio

    def crear(self, datos: Dict[str, Any]) -> Dict[str, Any]:
        datos = self._limpiar(datos)
        if not datos.get("codigo") or not datos.get("titulo"):
            raise DatosInvalidosError("El código y el título son obligatorios.")
        datos["estado"] = "borrador"  # siempre nace en borrador: se publica cuando la ficha está lista
        inmueble = self._inmuebles.crear(datos)
        return self.detalle(inmueble["id"])

    def actualizar(self, inmueble_id: int, cambios: Dict[str, Any]) -> Dict[str, Any]:
        actual = self._inmuebles.obtener(inmueble_id)
        if actual is None:
            raise InmuebleNoEncontradoError("No existe esa propiedad.")
        cambios = self._limpiar(cambios)
        cambios.pop("estado", None)  # el estado se cambia con cambiar_estado (tiene sus propias reglas)
        if "codigo" in cambios and not cambios["codigo"]:
            raise DatosInvalidosError("El código no puede quedar vacío.")
        if "titulo" in cambios and not cambios["titulo"]:
            raise DatosInvalidosError("El título no puede quedar vacío.")
        if actual["estado"] == "activo":
            faltan = requisitos_para_activar({**actual, **cambios})
            if faltan:
                raise DatosInvalidosError(f"Una propiedad publicada necesita {', '.join(faltan)}.")
        self._inmuebles.actualizar(inmueble_id, cambios)
        return self.detalle(inmueble_id)

    def cambiar_estado(self, inmueble_id: int, estado: str) -> Dict[str, Any]:
        actual = self._inmuebles.obtener(inmueble_id)
        if actual is None:
            raise InmuebleNoEncontradoError("No existe esa propiedad.")
        if estado not in ESTADOS_INMUEBLE:
            raise DatosInvalidosError("Estado no válido.")
        if estado == "activo":
            faltan = requisitos_para_activar(actual)
            if faltan:
                raise DatosInvalidosError(f"Para publicarla falta {', '.join(faltan)}.")
        self._inmuebles.actualizar(inmueble_id, {"estado": estado})
        return self.detalle(inmueble_id)

    # -- material ---------------------------------------------------------------------------------------------------------

    def agregar_material(self, inmueble_id: int, ruta: str, usuario: Optional[str]) -> Dict[str, Any]:
        if self._inmuebles.obtener(inmueble_id) is None:
            raise InmuebleNoEncontradoError("No existe esa propiedad.")
        try:
            ruta = validar_ruta(carpeta_de_inmueble(inmueble_id), ruta)
        except RutaDeImagenInvalida as exc:
            raise DatosInvalidosError(str(exc)) from exc
        if len(self._material.listar(inmueble_id)) >= MAXIMO_MATERIAL:
            raise DatosInvalidosError(f"Máximo {MAXIMO_MATERIAL} fotos y videos por propiedad.")
        self._material.agregar(inmueble_id, url_publica(load_settings().supabase_url, ruta), ruta, usuario)
        return self.detalle(inmueble_id)

    def quitar_material(self, inmueble_id: int, material_id: int) -> Dict[str, Any]:
        if self._material.quitar(inmueble_id, material_id) is None:
            raise InmuebleNoEncontradoError("Ese archivo no es de esta propiedad.")
        return self.detalle(inmueble_id)

    def ordenar_material(self, inmueble_id: int, ids: List[int]) -> Dict[str, Any]:
        if self._inmuebles.obtener(inmueble_id) is None:
            raise InmuebleNoEncontradoError("No existe esa propiedad.")
        actuales = {m["id"] for m in self._material.listar(inmueble_id)}
        if set(ids) != actuales:
            raise DatosInvalidosError("La lista no coincide con la galería actual. Recarga la página.")
        self._material.reordenar(inmueble_id, ids)
        return self.detalle(inmueble_id)

    # -- anuncios ---------------------------------------------------------------------------------------------------------

    def vincular_anuncio(self, inmueble_id: int, id_anuncio: str, nombre: Optional[str]) -> Dict[str, Any]:
        if self._inmuebles.obtener(inmueble_id) is None:
            raise InmuebleNoEncontradoError("No existe esa propiedad.")
        id_anuncio = (id_anuncio or "").strip()
        if not id_anuncio.isdigit():
            raise DatosInvalidosError("El identificador del anuncio son solo números (está en el Administrador de anuncios).")
        if self._anuncios.es_anuncio_de_producto(id_anuncio):
            raise DatosInvalidosError("Ese anuncio ya está vinculado a un producto de la tienda. Desvincúlalo primero en Anuncios.")
        self._anuncios.vincular(id_anuncio, inmueble_id, (nombre or "").strip() or None)
        return self.detalle(inmueble_id)

    def desvincular_anuncio(self, inmueble_id: int, id_anuncio: str) -> Dict[str, Any]:
        if not self._anuncios.desvincular(id_anuncio, inmueble_id):
            raise InmuebleNoEncontradoError("Ese anuncio no estaba vinculado a esta propiedad.")
        return self.detalle(inmueble_id)

    # -- números de WhatsApp ----------------------------------------------------------------------------------------------

    def listar_numeros(self) -> List[Dict[str, Any]]:
        principal = load_settings().whatsapp_phone_number_id
        return [{**n, "es_principal": n["phone_number_id"] == principal} for n in self._numeros.listar()]

    def guardar_numero(self, datos: Dict[str, Any]) -> Dict[str, Any]:
        phone_number_id = str(datos.get("phone_number_id") or "").strip()
        if not phone_number_id.isdigit():
            raise DatosInvalidosError("El identificador del número (phone number ID) son solo números.")
        if datos.get("asistente") not in ASISTENTES:
            raise DatosInvalidosError("Asistente no válido.")
        nombre = str(datos.get("nombre") or "").strip()
        if not nombre:
            raise DatosInvalidosError("Ponle un nombre al número para reconocerlo.")
        return self._numeros.guardar(
            phone_number_id, nombre, (str(datos.get("telefono_visible") or "").strip() or None), datos["asistente"],
            bool(datos.get("activo", True)),
        )

    def quitar_numero(self, phone_number_id: str) -> None:
        if not self._numeros.quitar(phone_number_id):
            raise InmuebleNoEncontradoError("Ese número no está registrado.")

    # -- conversación -----------------------------------------------------------------------------------------------------

    def fijar_asistente_de_conversacion(self, conversacion_id: int, asistente: str, inmueble_id: Optional[int]) -> None:
        """El dueño cambia a mano quién atiende una conversación (p. ej. un cliente de la casa que escribió al número de la
        tienda sin pasar por el anuncio)."""
        if asistente not in ASISTENTES:
            raise DatosInvalidosError("Asistente no válido.")
        if self._conversaciones.obtener_por_id(conversacion_id) is None:
            raise InmuebleNoEncontradoError("No existe esa conversación.")
        if asistente == INMUEBLES and inmueble_id is not None and self._inmuebles.obtener(inmueble_id) is None:
            raise InmuebleNoEncontradoError("No existe esa propiedad.")
        self._conversaciones.fijar_asistente(conversacion_id, asistente, inmueble_id)


class VisitasServicio:
    def __init__(
        self,
        visitas: Optional[VisitaRepository] = None,
        inmuebles: Optional[InmuebleRepository] = None,
        conversaciones: Optional[ConversacionRepository] = None,
        mensajes: Optional[MensajeRepository] = None,
        canales=None,
        anuncios: Optional[AnuncioServicio] = None,
    ):
        self._visitas = visitas or VisitaRepository()
        self._inmuebles = inmuebles or InmuebleRepository()
        self._conversaciones = conversaciones or ConversacionRepository()
        self._mensajes = mensajes or MensajeRepository()
        self._canales_fijo = canales
        self._anuncios = anuncios or AnuncioServicio()

    def _canales(self):
        if self._canales_fijo is None:
            self._canales_fijo = get_registro_canales()
        return self._canales_fijo

    def listar(self, desde=None, hasta=None, estados=None, inmueble_id=None) -> List[Dict[str, Any]]:
        visitas = self._visitas.listar(desde=desde, hasta=hasta, estados=estados, inmueble_id=inmueble_id)
        return [self._con_ventana(v) for v in visitas]

    def resumen(self) -> Dict[str, int]:
        return self._visitas.contar_por_estado()

    def _obtener(self, visita_id: int) -> Dict[str, Any]:
        visita = self._visitas.obtener(visita_id)
        if visita is None:
            raise VisitaNoEncontradaError("No existe esa visita.")
        return visita

    def _ventana(self, conversacion_id: Optional[int]):
        """(abierta, cierre) de la ventana de 24 h de la conversación de la visita: solo dentro de ella se le puede escribir."""
        if not conversacion_id:
            return False, None
        mensajes = self._mensajes.obtener_por_conversacion(conversacion_id)
        return self._anuncios.ventana_de_servicio(mensajes, datetime.now(timezone.utc))

    def _con_ventana(self, visita: Dict[str, Any]) -> Dict[str, Any]:
        abierta, cierre = self._ventana(visita.get("conversacion_id"))
        return {**visita, "ventana_abierta": abierta, "ventana_expira_en": cierre}

    def crear_manual(self, datos: Dict[str, Any]) -> Dict[str, Any]:
        """Una visita que el dueño agenda él mismo (p. ej. alguien que llamó por teléfono)."""
        inmueble = self._inmuebles.obtener(datos["inmueble_id"])
        if inmueble is None:
            raise InmuebleNoEncontradoError("No existe esa propiedad.")
        fecha = datos.get("fecha_hora")
        estado = "confirmada" if fecha else "solicitada"
        visita = self._visitas.crear({
            "inmueble_id": inmueble["id"],
            "nombre_cliente": (datos.get("nombre_cliente") or "").strip() or None,
            "telefono": (datos.get("telefono") or "").strip() or None,
            "preferencia_cliente": (datos.get("preferencia_cliente") or "").strip() or None,
            "personas": datos.get("personas"),
            "fecha_hora": fecha,
            "encargado": (datos.get("encargado") or "").strip() or inmueble.get("encargado_visitas"),
            "notas": (datos.get("notas") or "").strip() or None,
            "estado": estado,
            "creada_por": "dueno",
            **({"confirmada_en": datetime.now(timezone.utc)} if fecha else {}),
        })
        return self._con_ventana(visita)

    def confirmar(self, visita_id: int, fecha_hora: datetime, encargado: Optional[str], notas: Optional[str]) -> Dict[str, Any]:
        """Confirma (o reprograma) la visita con día y hora. No le avisa al cliente: eso es «Avisar al cliente», aparte, para que
        el dueño pueda revisar antes."""
        visita = self._obtener(visita_id)
        try:
            validar_transicion(visita["estado"], "confirmada")
        except TransicionDeVisitaInvalida as exc:
            raise DatosInvalidosError(str(exc)) from exc
        if fecha_hora is None:
            raise DatosInvalidosError("Falta el día y la hora de la visita.")
        cambios: Dict[str, Any] = {
            "estado": "confirmada", "fecha_hora": fecha_hora, "confirmada_en": datetime.now(timezone.utc),
            # Reprogramar = el aviso anterior ya no vale.
            "avisado_cliente_en": None if visita.get("fecha_hora") != fecha_hora else visita.get("avisado_cliente_en"),
        }
        if encargado is not None:
            cambios["encargado"] = encargado.strip() or None
        elif not visita.get("encargado"):
            inmueble = self._inmuebles.obtener(visita["inmueble_id"]) or {}
            cambios["encargado"] = inmueble.get("encargado_visitas")
        if notas is not None:
            cambios["notas"] = notas.strip() or None
        return self._con_ventana(self._visitas.actualizar(visita_id, cambios))

    def cambiar_estado(self, visita_id: int, estado: str, motivo: Optional[str] = None) -> Dict[str, Any]:
        """Realizada, no asistió o cancelada (confirmar va por `confirmar`, que pide la fecha)."""
        visita = self._obtener(visita_id)
        if estado == "confirmada":
            raise DatosInvalidosError("Para confirmar una visita indica el día y la hora.")
        try:
            validar_transicion(visita["estado"], estado)
        except TransicionDeVisitaInvalida as exc:
            raise DatosInvalidosError(str(exc)) from exc
        cambios: Dict[str, Any] = {"estado": estado}
        if estado == "cancelada":
            cambios["motivo_cancelacion"] = (motivo or "").strip() or None
        if estado == "solicitada":
            cambios.update({"fecha_hora": None, "confirmada_en": None, "avisado_cliente_en": None})
        return self._con_ventana(self._visitas.actualizar(visita_id, cambios))

    def actualizar_notas(self, visita_id: int, notas: Optional[str], encargado: Optional[str]) -> Dict[str, Any]:
        self._obtener(visita_id)
        cambios = {}
        if notas is not None:
            cambios["notas"] = notas.strip() or None
        if encargado is not None:
            cambios["encargado"] = encargado.strip() or None
        return self._con_ventana(self._visitas.actualizar(visita_id, cambios))

    def texto_de_aviso(self, visita_id: int) -> str:
        visita = self._obtener(visita_id)
        if visita["estado"] != "confirmada" or not visita.get("fecha_hora"):
            raise DatosInvalidosError("Primero confirma la visita con día y hora.")
        inmueble = self._inmuebles.obtener(visita["inmueble_id"])
        return texto_confirmacion(parametros.valor("inmuebles.texto_confirmacion_visita"), visita, inmueble)

    def avisar_cliente(self, visita_id: int, texto: Optional[str] = None) -> Dict[str, Any]:
        """Le escribe al cliente que su visita quedó confirmada (por la misma conversación y el mismo número por el que
        escribió). `texto` permite que el dueño ajuste el mensaje antes de enviarlo; si no, se arma con el parámetro."""
        visita = self._obtener(visita_id)
        mensaje = (texto or "").strip() or self.texto_de_aviso(visita_id)
        if visita["estado"] != "confirmada":
            raise DatosInvalidosError("Primero confirma la visita con día y hora.")
        if not visita.get("conversacion_id"):
            raise DatosInvalidosError("Esta visita no tiene conversación de WhatsApp: avísale al cliente por teléfono.")
        abierta, _ = self._ventana(visita["conversacion_id"])
        if not abierta:
            raise VentanaCerradaError(
                "Pasaron más de 24 horas desde el último mensaje del cliente: WhatsApp no deja escribirle texto libre. "
                "Llámalo o escríbele desde tu teléfono."
            )
        conversacion = self._conversaciones.obtener_por_id(visita["conversacion_id"])
        self._mensajes.crear(conversacion_id=conversacion["id"], rol="humano", contenido=mensaje, tipo="texto", wamid=None)
        try:
            self._canales().para_conversacion(conversacion).enviar_texto(conversacion["id_externo"], mensaje)
        except (WhatsAppRequestError, WhatsAppBusinessError, CanalNoDisponibleError) as exc:
            raise EnvioFallidoError(f"El mensaje quedó guardado pero no se pudo enviar: {exc}") from exc
        self._conversaciones.actualizar_timestamp(conversacion["id"])
        return self._con_ventana(self._visitas.actualizar(visita_id, {"avisado_cliente_en": datetime.now(timezone.utc)}))
