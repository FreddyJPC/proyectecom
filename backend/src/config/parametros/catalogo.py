"""
Catálogo de parámetros del sistema (ADR-011, docs/PLAN_PARAMETRIZACION.md).

Cada parámetro se declara UNA vez acá, con todo lo que la app necesita para mostrarlo
(nombre, «¿para qué sirve?», tipo, rango, cuándo se aplica) y todo lo que el backend
necesita para usarlo (valor por defecto, variable del servidor equivalente). La
pantalla de Parámetros lee esta lista por API, así la explicación vive en un solo
lugar y no puede quedar desactualizada respecto al código.

El catálogo es una LISTA BLANCA: una clave que no está acá no se puede leer ni guardar.
Por eso acá nunca va un secreto (claves, tokens, URLs de conexión): un test lo vigila
por el nombre de la variable del servidor y de la clave.

Orden de prioridad de un valor (de más fuerte a más débil):
  1. el que se guardó desde la app (tabla `parametros_sistema`);
  2. la variable del servidor equivalente (Railway), si existe;
  3. el valor por defecto de este archivo (el respaldo).
"""
import re
from dataclasses import dataclass
from typing import Any, Optional, Tuple

from src.config.settings import VALORES_VERDADEROS

TIPO_ENTERO = "entero"
TIPO_BOOLEANO = "booleano"
TIPO_TEXTO = "texto"
TIPO_OPCION = "opcion"

# Cuándo se nota un cambio (texto que ve la persona junto a cada parámetro).
APLICA_SIGUIENTE_MENSAJE = "Desde el siguiente mensaje de un cliente."
APLICA_SIGUIENTE_USO = "Desde la siguiente vez que se usa (en menos de un minuto)."
APLICA_PROXIMA_CORRIDA = "En la próxima corrida de la tarea automática (en menos de un minuto)."
APLICA_AL_GUARDAR = "Al guardar: el reloj de la tarea se reprograma enseguida."

# Palabras que delatan un secreto: ni la clave ni la variable del servidor de un
# parámetro pueden contenerlas (lo comprueba un test sobre todo el catálogo).
PALABRAS_DE_SECRETO = ("token", "secret", "key", "password", "passwd", "clave_api", "dsn", "url", "credential")


class ValorInvalido(ValueError):
    """El valor no cumple el tipo o el rango del parámetro. El mensaje está en español
    y se le muestra tal cual a la persona."""


class ParametroDesconocidoError(KeyError):
    """La clave no está en el catálogo."""


@dataclass(frozen=True)
class Opcion:
    valor: str
    etiqueta: str
    nota: str = ""


@dataclass(frozen=True)
class Grupo:
    clave: str
    nombre: str
    descripcion: str


@dataclass(frozen=True)
class Parametro:
    clave: str
    grupo: str
    nombre: str
    para_que_sirve: str
    tipo: str
    defecto: Any
    aplica: str
    minimo: Optional[int] = None
    maximo: Optional[int] = None
    largo_maximo: Optional[int] = None
    unidad: str = ""
    opciones: Tuple[Opcion, ...] = ()
    # Nombre de la variable del servidor que, si existe, vale cuando no hay valor guardado.
    variable_servidor: Optional[str] = None
    # Sensible = pide confirmación al guardar y muestra `aviso` antes.
    sensible: bool = False
    aviso: str = ""

    # ------------------------------------------------------------------
    # Lectura (texto guardado / variable del servidor -> valor)
    # ------------------------------------------------------------------
    def desde_texto(self, texto: str, *, del_servidor: bool = False) -> Any:
        """Convierte el texto guardado (o el de la variable del servidor) en el valor
        del parámetro. `del_servidor` relaja las reglas donde la variable de Railway
        siempre fue más permisiva (los «sí» alternativos de un booleano) o donde
        el catálogo cerrado no puede conocer el valor (un modelo de IA ya configurado)."""
        if self.tipo == TIPO_ENTERO:
            try:
                numero = int(str(texto).strip())
            except ValueError as exc:
                raise ValorInvalido(self._mensaje_entero()) from exc
            return self._validar_rango(numero)
        if self.tipo == TIPO_BOOLEANO:
            limpio = str(texto).strip().lower()
            if del_servidor:
                return limpio in VALORES_VERDADEROS
            if limpio not in ("true", "false"):
                raise ValorInvalido("Debe ser sí o no.")
            return limpio == "true"
        if self.tipo == TIPO_OPCION:
            limpio = str(texto).strip()
            if not limpio:
                raise ValorInvalido("Elige una de las opciones.")
            if not del_servidor and limpio not in {o.valor for o in self.opciones}:
                raise ValorInvalido("Elige una de las opciones de la lista.")
            return limpio
        return self._validar_texto(texto)

    def a_texto(self, valor: Any) -> str:
        """Valor ya validado -> texto para guardar en la base."""
        if self.tipo == TIPO_BOOLEANO:
            return "true" if valor else "false"
        return str(valor)

    # ------------------------------------------------------------------
    # Entrada desde la API (JSON -> valor), estricta con el tipo
    # ------------------------------------------------------------------
    def desde_json(self, crudo: Any) -> Any:
        if self.tipo == TIPO_ENTERO:
            if isinstance(crudo, bool):
                raise ValorInvalido(self._mensaje_entero())
            if isinstance(crudo, int):
                return self._validar_rango(crudo)
            if isinstance(crudo, str) and re.fullmatch(r"\s*-?\d+\s*", crudo):
                return self._validar_rango(int(crudo))
            raise ValorInvalido(self._mensaje_entero())
        if self.tipo == TIPO_BOOLEANO:
            if not isinstance(crudo, bool):
                raise ValorInvalido("Debe ser sí o no.")
            return crudo
        if not isinstance(crudo, str):
            raise ValorInvalido("Debe ser un texto.")
        return self.desde_texto(crudo)

    # ------------------------------------------------------------------
    def _validar_rango(self, numero: int) -> int:
        if (self.minimo is not None and numero < self.minimo) or (self.maximo is not None and numero > self.maximo):
            raise ValorInvalido(self._mensaje_entero())
        return numero

    def _mensaje_entero(self) -> str:
        unidad = f" {self.unidad}" if self.unidad else ""
        return f"Debe ser un número entero entre {self.minimo} y {self.maximo}{unidad}."

    def _validar_texto(self, texto: Any) -> str:
        limpio = str(texto).strip()
        if not limpio:
            raise ValorInvalido("No puede quedar vacío.")
        if self.largo_maximo is not None and len(limpio) > self.largo_maximo:
            raise ValorInvalido(f"Es demasiado largo: máximo {self.largo_maximo} caracteres.")
        if "\x00" in limpio:
            raise ValorInvalido("Contiene caracteres no permitidos.")
        return limpio


# ----------------------------------------------------------------------------
# Grupos (el orden es el de la pantalla)
# ----------------------------------------------------------------------------
GRUPOS: Tuple[Grupo, ...] = (
    Grupo("victoria", "Victoria (el bot de WhatsApp)", "Cómo trabaja Victoria con cada cliente."),
    Grupo("textos", "Mensajes fijos al cliente", "Frases que el sistema envía sin pasar por la IA, en situaciones puntuales."),
    Grupo("stock", "Stock y productos", "Cuánto stock se considera poco, qué hace el sistema solo cuando un producto cambia y cómo funcionan las pruebas."),
    Grupo("leads", "Leads (temperatura de los clientes)", "Cómo se enfría un lead cuando el cliente deja de contestar y de qué anuncio se considera que viene."),
    Grupo(
        "seguimiento",
        "Seguimiento automático de clientes",
        "Mensajes que el sistema le escribe por su cuenta a un cliente que dejó de contestar: cuándo, a quién, cuántos y con qué texto.",
    ),
    Grupo("tareas", "Tareas automáticas", "Cada cuántos minutos el sistema revisa Rocketfy, enfría los leads y envía seguimientos por su cuenta."),
)

# ----------------------------------------------------------------------------
# Modelos de IA que se pueden elegir (lista CERRADA a propósito: un nombre mal
# escrito dejaría a Victoria sin cerebro). Referencia de precios: tabla de
# Anthropic de octubre de 2026, por millón de tokens (entrada / salida).
#
# Solo están los modelos que se comportan como el actual con este código. Quedaron
# fuera `claude-sonnet-5-5`, `claude-opus-5-5` y `claude-fable-5-1`: rechazan la
# «herramienta forzada» con que «Redactar con IA» pide el borrador, y su manejo del
# pensamiento exige cambios en el cliente de la IA. Se suman cuando se adapte y
# pruebe ese código, no antes.
# ----------------------------------------------------------------------------
MODELO_POR_DEFECTO = "claude-sonnet-5"
MODELOS_DE_IA: Tuple[Opcion, ...] = (
    Opcion("claude-sonnet-5", "Sonnet 5 (el actual)", "Equilibrado. Referencia: $2 entrada / $10 salida por millón de tokens. Es el que se probó con este sistema."),
    Opcion("claude-haiku-5-5", "Haiku 5.5 (más barato)", "Mucho más económico: $0.10 / $0.50 por millón. Sin probar con Victoria: pruébalo en «Probar con Victoria» antes de usarlo con clientes."),
    Opcion("claude-opus-5", "Opus 5 (más capaz)", "El más capaz de la lista, pero más caro: $5 / $25 por millón. Sin probar con Victoria: pruébalo antes de usarlo con clientes."),
)

CATALOGO: Tuple[Parametro, ...] = (
    # ---------------------------------------------------------------- Victoria
    Parametro(
        clave="bot.max_mensajes_historial",
        grupo="victoria",
        nombre="Memoria de la conversación",
        para_que_sirve=(
            "Cuántos mensajes anteriores de la conversación se le entregan a la IA cada vez que responde. "
            "La IA no recuerda nada por sí sola: lee esos mensajes para saber de qué se venía hablando. "
            "Más mensajes = recuerda más, pero cada respuesta cuesta más y tarda un poco más. "
            "Menos mensajes = más barato, pero olvida antes lo que se dijo al principio "
            "(los datos ya guardados del cliente, como nombre y dirección, no se pierden)."
        ),
        tipo=TIPO_ENTERO,
        defecto=40,
        minimo=10,
        maximo=100,
        unidad="mensajes",
        variable_servidor="BOT_MAX_MENSAJES_HISTORIAL",
        aplica=APLICA_SIGUIENTE_MENSAJE,
    ),
    Parametro(
        clave="bot.max_fotos_por_envio",
        grupo="victoria",
        nombre="Fotos por envío",
        para_que_sirve=(
            "Cuántas fotos manda Victoria de una vez cuando el cliente pide ver el producto. Si el cliente quiere "
            "más, Victoria manda las siguientes de la galería (sin repetir). Muchas fotos juntas pueden ser "
            "abrumadoras en WhatsApp; con una sola, el cliente ve poco."
        ),
        tipo=TIPO_ENTERO,
        defecto=3,
        minimo=1,
        maximo=8,
        unidad="fotos",
        aplica=APLICA_SIGUIENTE_MENSAJE,
    ),
    Parametro(
        clave="bot.max_turnos_herramientas",
        grupo="victoria",
        nombre="Vueltas máximas con herramientas",
        para_que_sirve=(
            "Para responder un solo mensaje, Victoria puede usar herramientas (guardar un dato, registrar el producto, "
            "cerrar la venta…) y volver a pensar con el resultado: cada ida y vuelta es una «vuelta». "
            "Este número es el máximo de vueltas por mensaje. Si lo supera, el sistema pasa la conversación a una persona "
            "y le envía al cliente el mensaje «de límite alcanzado». Muy bajo, Victoria no alcanza a cerrar una venta; "
            "muy alto, un error de la IA puede gastar de más."
        ),
        tipo=TIPO_ENTERO,
        defecto=5,
        minimo=2,
        maximo=10,
        unidad="vueltas",
        variable_servidor="BOT_MAX_TURNOS_HERRAMIENTAS",
        aplica=APLICA_SIGUIENTE_MENSAJE,
    ),
    Parametro(
        clave="bot.enviar_fotos",
        grupo="victoria",
        nombre="Enviar fotos del producto",
        para_que_sirve=(
            "Si está encendido, Victoria puede mandar por WhatsApp las fotos del producto cuando el cliente las pide. "
            "Salen de la galería del producto (las que subes en su ficha) o, si no subiste ninguna, de la foto de "
            "Rocketfy; Meta tiene que poder descargarlas. Si el producto no tiene fotos, Victoria le dice al cliente "
            "que por ahora no hay imágenes. «Probar con Victoria» siempre simula las fotos, esté o no encendido."
        ),
        tipo=TIPO_BOOLEANO,
        defecto=False,
        variable_servidor="BOT_ENVIAR_FOTOS",
        aplica=APLICA_SIGUIENTE_MENSAJE,
        sensible=True,
        aviso="Enciéndelo solo después de comprobar, desde un teléfono real, que la foto llega al cliente.",
    ),
    Parametro(
        clave="llm.modelo",
        grupo="victoria",
        nombre="Modelo de IA",
        para_que_sirve=(
            "Qué modelo de inteligencia artificial responde. Es la palanca más fuerte de costo y de calidad. "
            "Vale para TODO el sistema: las conversaciones de Victoria, «Redactar con IA» y «Probar con Victoria»."
        ),
        tipo=TIPO_OPCION,
        defecto=MODELO_POR_DEFECTO,
        opciones=MODELOS_DE_IA,
        variable_servidor="LLM_MODEL",
        aplica=APLICA_SIGUIENTE_MENSAJE,
        sensible=True,
        aviso=(
            "Después de cambiarlo, haz una prueba completa en «Probar con Victoria» antes de confiar en el modelo nuevo. "
            "Los precios son de referencia: confírmalos en tu cuenta de Anthropic."
        ),
    ),
    Parametro(
        clave="bot.atender_clientes_recurrentes",
        grupo="victoria",
        nombre="Que Victoria atienda a los clientes que ya compraron",
        para_que_sirve=(
            "Si está activo, un cliente que ya tiene un pedido y vuelve a escribir lo atiende Victoria como a un cliente conocido: "
            "ve lo que compró o preguntó antes, le ayuda con lo nuevo y le abre un pedido nuevo si quiere volver a comprar. "
            "Lo que sea de su pedido anterior (envío, reclamos, garantía) sigue pasando a una persona. Si lo apagas, vuelve el "
            "comportamiento de antes: el sistema envía el mensaje «Cliente que ya tiene un pedido despachado» y avisa a una persona."
        ),
        tipo=TIPO_BOOLEANO,
        defecto=True,
        aplica=APLICA_SIGUIENTE_MENSAJE,
    ),
    # ----------------------------------------------------------------- Textos
    Parametro(
        clave="bot.texto_postventa",
        grupo="textos",
        nombre="Cliente que ya tiene un pedido despachado",
        para_que_sirve=(
            "Lo que se responde cuando escribe un cliente que ya tiene un pedido despachado y Victoria NO está atendiendo a los "
            "clientes recurrentes (ver «Que Victoria atienda a los clientes que ya compraron»). En ese caso Victoria no interviene: "
            "el sistema envía este mensaje y avisa a una persona para que lo atienda."
        ),
        tipo=TIPO_TEXTO,
        defecto="¡Hola de nuevo! Ya te conecto con nuestro equipo de atención, en un momento te responden 🙋",
        largo_maximo=300,
        aplica=APLICA_SIGUIENTE_MENSAJE,
    ),
    Parametro(
        clave="bot.texto_comprobante_recibido",
        grupo="textos",
        nombre="Cliente que envía una imagen mientras se espera el pago",
        para_que_sirve=(
            "Lo que se responde cuando el cliente manda una imagen estando su pedido en espera de pago (casi seguro, el "
            "comprobante de la transferencia). Victoria todavía no puede ver imágenes: el sistema envía este mensaje y "
            "avisa a una persona para que confirme el pago."
        ),
        tipo=TIPO_TEXTO,
        defecto="¡Gracias! Ya recibimos tu comprobante, en un momento uno de nuestros asesores lo confirma ✅",
        largo_maximo=300,
        aplica=APLICA_SIGUIENTE_MENSAJE,
    ),
    Parametro(
        clave="bot.texto_limite_alcanzado",
        grupo="textos",
        nombre="Victoria se pasó del límite de vueltas",
        para_que_sirve=(
            "Lo que se le envía al cliente cuando Victoria supera el máximo de vueltas con herramientas (ver «Vueltas máximas "
            "con herramientas») y la conversación se pasa a una persona."
        ),
        tipo=TIPO_TEXTO,
        defecto="Disculpa la demora — ya te conecto con un asesor humano que te ayuda enseguida 🙋",
        largo_maximo=300,
        aplica=APLICA_SIGUIENTE_MENSAJE,
    ),
    # ------------------------------------------------------------------ Stock
    Parametro(
        clave="stock.cache_segundos",
        grupo="stock",
        nombre="Cuánto se recuerda el stock consultado",
        para_que_sirve=(
            "Para no preguntarle a Rocketfy el stock en cada mensaje, Victoria recuerda lo que consultó durante este tiempo. "
            "Al cerrar una venta SIEMPRE se consulta el dato fresco, sin importar este valor. Más tiempo = menos consultas "
            "a Rocketfy pero un dato más viejo al conversar."
        ),
        tipo=TIPO_ENTERO,
        defecto=300,
        minimo=30,
        maximo=1800,
        unidad="segundos",
        aplica=APLICA_SIGUIENTE_USO,
    ),
    Parametro(
        clave="stock.umbral_bajo",
        grupo="stock",
        nombre="Qué cuenta como «stock bajo»",
        para_que_sirve=(
            "Con cuántas unidades o menos se considera que queda poco stock de un producto. Se usa en dos sitios: "
            "avisa en la lista de verificación al publicar un producto, y es el umbral con que se empieza a vigilar un "
            "producto nuevo al publicarlo. Los productos que ya se vigilan conservan su propio umbral (se cambia en "
            "Catálogo → Vigilados)."
        ),
        tipo=TIPO_ENTERO,
        defecto=5,
        minimo=0,
        maximo=100,
        unidad="unidades",
        aplica=APLICA_SIGUIENTE_USO,
    ),
    Parametro(
        clave="sync.autopausa_agotado",
        grupo="stock",
        nombre="Pausar solo un producto agotado",
        para_que_sirve=(
            "Si está encendido, cuando la sincronización con Rocketfy ve que un producto activo quedó con 0 unidades, lo pasa "
            "a «agotado»: Victoria deja de ofrecerlo, queda anotado en Incidencias y te avisa por Telegram. "
            "Reanudarlo siempre lo haces tú. Apagado, el producto sigue activo aunque no haya stock (Rocketfy rechazaría "
            "esos pedidos al confirmarlos)."
        ),
        tipo=TIPO_BOOLEANO,
        defecto=True,
        aplica=APLICA_PROXIMA_CORRIDA,
        sensible=True,
        aviso="Apagado, Victoria puede seguir vendiendo un producto que ya no tiene stock.",
    ),
    Parametro(
        clave="sync.alerta_margen",
        grupo="stock",
        nombre="Avisar cuando el margen está en riesgo",
        para_que_sirve=(
            "Si está encendido, cuando el costo de un producto sube en Rocketfy y, con tu precio actual, el margen cae por "
            "debajo del mínimo de tus ajustes de precios, el sistema te avisa una sola vez (Incidencias y Telegram). "
            "Nunca cambia el precio por su cuenta."
        ),
        tipo=TIPO_BOOLEANO,
        defecto=True,
        aplica=APLICA_PROXIMA_CORRIDA,
    ),
    Parametro(
        clave="pruebas.max_mensajes",
        grupo="stock",
        nombre="Mensajes por prueba en «Probar con Victoria»",
        para_que_sirve=(
            "Cuántos mensajes del cliente admite una misma prueba antes de pedir que la reinicies. Pasado cierto punto la "
            "conversación ya no enseña nada nuevo y cada mensaje sigue costando, porque el historial viaja completo."
        ),
        tipo=TIPO_ENTERO,
        defecto=20,
        minimo=5,
        maximo=50,
        unidad="mensajes",
        aplica=APLICA_SIGUIENTE_USO,
    ),
    # ------------------------------------------------------------------ Leads
    Parametro(
        clave="leads.enfriar_activo",
        grupo="leads",
        nombre="Enfriar leads cuando el cliente deja de contestar",
        para_que_sirve=(
            "Si está activo, un lead que no recibe respuesta del cliente va bajando solo de temperatura (caliente → tibio → frío → "
            "perdido) según los días de silencio de abajo. Solo cambia la clasificación: no le escribe a nadie. Nunca toca un lead "
            "cuya temperatura fijaste tú ni una conversación que está en tus manos (escalada o en gestión)."
        ),
        tipo=TIPO_BOOLEANO,
        defecto=True,
        aplica=APLICA_PROXIMA_CORRIDA,
    ),
    Parametro(
        clave="leads.dias_a_tibio",
        grupo="leads",
        nombre="Días para pasar de caliente a tibio",
        para_que_sirve="Días sin que el cliente escriba para que un lead «caliente» pase a «tibio».",
        tipo=TIPO_ENTERO,
        defecto=2,
        minimo=1,
        maximo=30,
        unidad="días",
        aplica=APLICA_PROXIMA_CORRIDA,
    ),
    Parametro(
        clave="leads.dias_a_frio",
        grupo="leads",
        nombre="Días para pasar a frío",
        para_que_sirve="Días sin que el cliente escriba para que un lead «caliente» o «tibio» pase a «frío».",
        tipo=TIPO_ENTERO,
        defecto=5,
        minimo=2,
        maximo=60,
        unidad="días",
        aplica=APLICA_PROXIMA_CORRIDA,
    ),
    Parametro(
        clave="leads.dias_a_perdido",
        grupo="leads",
        nombre="Días para dar el lead por perdido",
        para_que_sirve=(
            "Días sin que el cliente escriba para que un lead abierto pase a «perdido» (motivo: no respondió). Un lead perdido deja "
            "de ser el lead abierto del cliente: si vuelve a escribir, se abre uno nuevo."
        ),
        tipo=TIPO_ENTERO,
        defecto=14,
        minimo=3,
        maximo=180,
        unidad="días",
        aplica=APLICA_PROXIMA_CORRIDA,
    ),
    Parametro(
        clave="leads.dias_fijar",
        grupo="leads",
        nombre="Cuánto dura la temperatura que fijas tú",
        para_que_sirve=(
            "Cuando cambias a mano la temperatura de un lead, el enfriamiento automático la respeta estos días. Pasado ese tiempo "
            "vuelve a aplicarse el silencio del cliente."
        ),
        tipo=TIPO_ENTERO,
        defecto=7,
        minimo=1,
        maximo=90,
        unidad="días",
        aplica=APLICA_SIGUIENTE_USO,
    ),
    Parametro(
        clave="leads.dias_atribucion",
        grupo="leads",
        nombre="Días en que un anuncio cuenta como el origen de un lead nuevo",
        para_que_sirve=(
            "Cuando un cliente abre un lead nuevo, se considera que viene de un anuncio solo si tocó ese anuncio en los últimos días "
            "indicados; si no, el lead es «directo». Así, un cliente que llegó por un anuncio hace meses y vuelve a escribir por su "
            "cuenta no cuenta como venta de ese anuncio."
        ),
        tipo=TIPO_ENTERO,
        defecto=30,
        minimo=1,
        maximo=365,
        unidad="días",
        aplica=APLICA_SIGUIENTE_MENSAJE,
    ),
    # ------------------------------------------------------------ Seguimiento
    Parametro(
        clave="seguimiento.empujon_activo",
        grupo="seguimiento",
        nombre="Escribirle un empujón al cliente que dejó de contestar",
        para_que_sirve=(
            "Si está activo, el sistema le escribe UN mensaje corto (el texto de abajo) al cliente interesado que lleva unas horas "
            "sin contestar, mientras la ventana de 24 horas de WhatsApp sigue abierta (es gratis). Solo una vez por cliente en toda "
            "su vida. Nunca le escribe a quien marcaste «no contactar», a leads perdidos o ganados, ni a conversaciones que atiendes tú. "
            "El mensaje queda guardado en la conversación para que Victoria sepa que ya se le escribió."
        ),
        tipo=TIPO_BOOLEANO,
        defecto=False,
        aplica=APLICA_PROXIMA_CORRIDA,
        sensible=True,
        aviso="Escribirle a un cliente que no te escribió primero puede molestarlo; si muchos bloquean tus mensajes, Meta baja la calidad de tu número.",
    ),
    Parametro(
        clave="seguimiento.plantilla_activa",
        grupo="seguimiento",
        nombre="Retomar con una plantilla a los clientes de anuncio",
        para_que_sirve=(
            "Si está activo, el sistema le envía UNA plantilla aprobada por Meta (la de abajo) al cliente que llegó por un anuncio, "
            "mostró interés y dejó de contestar, pasadas las 24 horas, mientras Meta no cobra los mensajes de esa conversación (la "
            "ventana gratuita de anuncio, hasta 7 días). Solo una vez por cliente en toda su vida y con las mismas protecciones que "
            "el empujón. Requiere que la plantilla esté creada y aprobada en Meta."
        ),
        tipo=TIPO_BOOLEANO,
        defecto=False,
        aplica=APLICA_PROXIMA_CORRIDA,
        sensible=True,
        aviso="Si Meta no tiene la plantilla aprobada, los envíos fallan (el sistema lo avisa por Telegram y deja de intentarlo en esa corrida).",
    ),
    Parametro(
        clave="seguimiento.horas_empujon",
        grupo="seguimiento",
        nombre="Horas de silencio antes del empujón",
        para_que_sirve=(
            "Cuántas horas deben pasar desde el último mensaje del cliente para escribirle el empujón. Debe quedar tiempo antes de "
            "que se cierre la ventana de 24 horas: pasada esa ventana, solo se puede enviar la plantilla."
        ),
        tipo=TIPO_ENTERO,
        defecto=4,
        minimo=1,
        maximo=20,
        unidad="horas",
        aplica=APLICA_PROXIMA_CORRIDA,
    ),
    Parametro(
        clave="seguimiento.tope_diario",
        grupo="seguimiento",
        nombre="Máximo de seguimientos por día",
        para_que_sirve=(
            "Cuántos mensajes de seguimiento (empujones y plantillas juntos) se envían como máximo en un día, contado en hora de "
            "Ecuador. Es un freno de seguridad: protege la calidad de tu número y evita sorpresas si algo se descontrola."
        ),
        tipo=TIPO_ENTERO,
        defecto=10,
        minimo=1,
        maximo=200,
        unidad="mensajes",
        aplica=APLICA_PROXIMA_CORRIDA,
    ),
    Parametro(
        clave="seguimiento.hora_desde",
        grupo="seguimiento",
        nombre="Hora desde la que se envían seguimientos",
        para_que_sirve="Primera hora del día (hora de Ecuador, de 0 a 23) en que el sistema puede escribirles a los clientes. Antes de esa hora no envía nada.",
        tipo=TIPO_ENTERO,
        defecto=9,
        minimo=0,
        maximo=23,
        unidad="hora",
        aplica=APLICA_PROXIMA_CORRIDA,
    ),
    Parametro(
        clave="seguimiento.hora_hasta",
        grupo="seguimiento",
        nombre="Hora hasta la que se envían seguimientos",
        para_que_sirve=(
            "Hora del día (hora de Ecuador, de 1 a 24) en que el sistema deja de escribirles a los clientes: con 20, el último "
            "mensaje sale antes de las 20:00. Debe ser mayor que la hora de inicio; si no lo es, no se envía nada."
        ),
        tipo=TIPO_ENTERO,
        defecto=20,
        minimo=1,
        maximo=24,
        unidad="hora",
        aplica=APLICA_PROXIMA_CORRIDA,
    ),
    Parametro(
        clave="seguimiento.texto_empujon",
        grupo="seguimiento",
        nombre="Texto del empujón",
        para_que_sirve="El mensaje corto que recibe el cliente que dejó de contestar, dentro de las 24 horas. Trátalo de usted, como Victoria.",
        tipo=TIPO_TEXTO,
        defecto="Hola 👋 ¿Sigue interesado(a)? Cuénteme y lo terminamos en un momento 😊",
        largo_maximo=400,
        aplica=APLICA_PROXIMA_CORRIDA,
    ),
    Parametro(
        clave="seguimiento.plantilla_nombre",
        grupo="seguimiento",
        nombre="Nombre de la plantilla en Meta",
        para_que_sirve=(
            "El nombre exacto de la plantilla aprobada en Meta que se envía fuera de las 24 horas (solo minúsculas, números y guion "
            "bajo). Debe ser una plantilla sin variables."
        ),
        tipo=TIPO_TEXTO,
        defecto="retomar_conversacion",
        largo_maximo=100,
        aplica=APLICA_PROXIMA_CORRIDA,
    ),
    Parametro(
        clave="seguimiento.texto_plantilla",
        grupo="seguimiento",
        nombre="Texto de la plantilla",
        para_que_sirve=(
            "Lo que dice la plantilla aprobada en Meta. Cambiarlo aquí NO cambia lo que recibe el cliente (eso lo define Meta): solo "
            "sirve para dejar anotado en la conversación lo que se envió. Debe ser igual al texto aprobado."
        ),
        tipo=TIPO_TEXTO,
        defecto="Hola 👋 Soy Victoria, de AzoShop. Hace poco estuvimos conversando y quedó pendiente su pedido. ¿Sigue interesado(a)?",
        largo_maximo=1024,
        aplica=APLICA_PROXIMA_CORRIDA,
    ),
    # ----------------------------------------------------------------- Tareas
    Parametro(
        clave="jobs.minutos_sync_productos",
        grupo="tareas",
        nombre="Sincronización de productos",
        para_que_sirve=(
            "Cada cuántos minutos se vuelve a leer Rocketfy para actualizar costo, precio sugerido, stock, peso e imagen de "
            "los productos publicados, pausar los agotados y avisar de márgenes en riesgo."
        ),
        tipo=TIPO_ENTERO,
        defecto=60,
        minimo=15,
        maximo=1440,
        unidad="minutos",
        aplica=APLICA_AL_GUARDAR,
        sensible=True,
        aviso="Menos de 15 minutos no se permite para no saturar a Rocketfy.",
    ),
    Parametro(
        clave="jobs.minutos_stock_watcher",
        grupo="tareas",
        nombre="Vigilante de stock",
        para_que_sirve=(
            "Cada cuántos minutos se revisa el stock y el precio de los productos que tienes en «Vigilados» para crear "
            "alertas de stock bajo o cambio de precio."
        ),
        tipo=TIPO_ENTERO,
        defecto=60,
        minimo=15,
        maximo=1440,
        unidad="minutos",
        aplica=APLICA_AL_GUARDAR,
        sensible=True,
        aviso="Menos de 15 minutos no se permite para no saturar a Rocketfy.",
    ),
    Parametro(
        clave="jobs.minutos_enfriar_leads",
        grupo="tareas",
        nombre="Enfriamiento de leads",
        para_que_sirve="Cada cuántos minutos se revisan los leads abiertos para bajarles la temperatura si el cliente dejó de contestar.",
        tipo=TIPO_ENTERO,
        defecto=60,
        minimo=15,
        maximo=1440,
        unidad="minutos",
        aplica=APLICA_AL_GUARDAR,
    ),
    Parametro(
        clave="jobs.minutos_seguimiento",
        grupo="tareas",
        nombre="Seguimiento automático de clientes",
        para_que_sirve=(
            "Cada cuántos minutos se revisa si hay clientes a quienes escribirles un seguimiento. Solo hace algo si activaste "
            "alguno de los envíos en «Seguimiento automático de clientes»."
        ),
        tipo=TIPO_ENTERO,
        defecto=30,
        minimo=15,
        maximo=240,
        unidad="minutos",
        aplica=APLICA_AL_GUARDAR,
    ),
    Parametro(
        clave="jobs.minutos_reconciliacion",
        grupo="tareas",
        nombre="Reconciliación de pedidos",
        para_que_sirve=(
            "Cada cuántos minutos se comparan tus pedidos con lo que dice Rocketfy, por si se perdió algún aviso (webhook) "
            "de cambio de estado."
        ),
        tipo=TIPO_ENTERO,
        defecto=45,
        minimo=15,
        maximo=1440,
        unidad="minutos",
        aplica=APLICA_AL_GUARDAR,
        sensible=True,
        aviso="Menos de 15 minutos no se permite para no saturar a Rocketfy.",
    ),
)

_POR_CLAVE = {p.clave: p for p in CATALOGO}


def definicion(clave: str) -> Parametro:
    """El parámetro de esa clave, o `ParametroDesconocidoError` (error de programación
    si lo pide el código, 404 si lo pide la API)."""
    try:
        return _POR_CLAVE[clave]
    except KeyError:
        raise ParametroDesconocidoError(clave) from None
