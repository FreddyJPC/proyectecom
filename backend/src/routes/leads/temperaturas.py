"""
Temperatura de un lead (docs/PLAN_LEADS_CRM.md §2.2) y las reglas puras que la rodean. Sin base de datos ni parámetros:
todo lo que entra es un valor y todo lo que sale es un valor, para poder probarlo a fondo.

Dos ejes que no se mezclan: la ETAPA (`leads.estado`, la fija el sistema: recopilando datos, esperando pago, despachado…)
dice DÓNDE VA el lead; la TEMPERATURA dice QUÉ TAN PROBABLE ES que compre.
"""
from typing import Optional

CALIENTE = "caliente"
TIBIO = "tibio"
FRIO = "frio"
PERDIDO = "perdido"
GANADO = "ganado"

# De la más probable a la menos; después las dos finales. Es el orden en que se muestran y se ordenan.
TEMPERATURAS = (CALIENTE, TIBIO, FRIO, PERDIDO, GANADO)
ABIERTAS = (CALIENTE, TIBIO, FRIO)
FINALES = (PERDIDO, GANADO)

ETIQUETAS = {CALIENTE: "Caliente", TIBIO: "Tibio", FRIO: "Frío", PERDIDO: "Perdido", GANADO: "Ganado"}

# Quién puso la temperatura, de más a menos fuerte: el dueño a mano, las reglas sobre hechos, la IA.
ORIGEN_DUENO = "dueno"
ORIGEN_REGLA = "regla"
ORIGEN_IA = "ia"
ORIGENES = (ORIGEN_DUENO, ORIGEN_REGLA, ORIGEN_IA)

MOTIVOS_DE_PERDIDA = {
    "precio": "El precio",
    "sin_respuesta": "No respondió",
    "compro_en_otro_lado": "Compró en otro lado",
    "sin_cobertura": "No llegamos a su ciudad",
    "sin_stock": "Sin stock",
    "no_le_interesa": "No le interesa",
    "otro": "Otro motivo",
}

# Hechos que fijan la temperatura sin discusión: una venta cerrada es «ganado», una cancelada es «perdido».
ESTADOS_GANADOS = ("despachado", "por_gestionar")
ESTADO_PERDIDO = "cancelado"

LARGO_MAXIMO_MOTIVO = 300


def es_valida(temperatura: Optional[str]) -> bool:
    return temperatura in TEMPERATURAS


def es_abierta(temperatura: Optional[str]) -> bool:
    return temperatura in ABIERTAS


def es_final(temperatura: Optional[str]) -> bool:
    return temperatura in FINALES


def temperatura_por_hechos(estado: Optional[str]) -> Optional[str]:
    """La temperatura que imponen los hechos (la etapa del lead), o None si los hechos no dicen nada."""
    if estado in ESTADOS_GANADOS:
        return GANADO
    if estado == ESTADO_PERDIDO:
        return PERDIDO
    return None


def motivo_de_perdida_valido(clave: Optional[str]) -> bool:
    return clave in MOTIVOS_DE_PERDIDA


def limpiar_motivo(texto: Optional[str]) -> Optional[str]:
    limpio = " ".join((texto or "").split())[:LARGO_MAXIMO_MOTIVO]
    return limpio or None


def _peldano(temperatura: str) -> int:
    return ABIERTAS.index(temperatura)


def temperatura_por_silencio(
    actual: str, dias_sin_responder: float, dias_a_tibio: int, dias_a_frio: int, dias_a_perdido: int
) -> str:
    """Enfriamiento automático por el silencio del cliente: caliente → tibio → frío → perdido. SOLO enfría, nunca calienta
    (calentar es juicio de Victoria o del dueño). Cada umbral son días de silencio contados desde el último mensaje del
    cliente; si los umbrales vienen desordenados se ordenan (un parámetro mal puesto no debe romper el enfriamiento).

    Un lead que ya está más frío que lo que le tocaría por el silencio conserva su temperatura."""
    if actual not in ABIERTAS:
        return actual
    a_tibio, a_frio, a_perdido = sorted((dias_a_tibio, dias_a_frio, dias_a_perdido))
    if dias_sin_responder >= a_perdido:
        return PERDIDO
    if dias_sin_responder >= a_frio:
        merecida = FRIO
    elif dias_sin_responder >= a_tibio:
        merecida = TIBIO
    else:
        merecida = CALIENTE
    return merecida if _peldano(merecida) > _peldano(actual) else actual


def tipo_de_contacto(compras: int) -> str:
    """Como los CRM grandes: prospecto (nunca compró), cliente (una compra) o recurrente (dos o más). Se deduce de las
    ventas no canceladas, no se guarda."""
    if compras <= 0:
        return "prospecto"
    return "cliente" if compras == 1 else "recurrente"
