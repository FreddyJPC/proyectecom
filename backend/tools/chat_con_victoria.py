"""
Simulador de conversación en terminal con Victoria, sin depender de
WhatsApp -- necesario mientras la app de Meta siga sin publicar (Fase
3.1: mientras tanto, Meta solo entrega webhooks de prueba disparados
desde su propio panel, ningún mensaje real de un cliente llega al
webhook).

Uso:
    .venv/bin/python tools/chat_con_victoria.py [--telefono 593999999999]

Comandos dentro del chat:
    /reset   -- borra la conversación y el lead de este teléfono, empieza de cero
    /estado  -- imprime el estado completo del lead actual
    /salir   -- termina (Ctrl+C también funciona)

NO llama a WhatsAppClient en ningún momento: llama directamente a
VictoriaConversationService.procesar_turno(), exactamente lo mismo que
hace BotWorker en producción para modo='ia' -- solo que acá el texto de
respuesta se imprime en la terminal en vez de mandarse por WhatsApp.

Requiere backend/.env con SUPABASE_DB_URL y ANTHROPIC_API_KEY ya
configurados (esta última se pide recién al construir
VictoriaConversationService, con un error claro si falta).
"""
import argparse
import sys

from dotenv import load_dotenv

sys.path.insert(0, ".")
load_dotenv(".env")

from src.config.database import get_connection  # noqa: E402
from src.routes.whatsapp.conversation_service import VictoriaConversationService  # noqa: E402
from src.routes.whatsapp.repository import ConversacionRepository, LeadRepository, MensajeRepository  # noqa: E402

_TELEFONO_DEFAULT = "593900000000"


def _borrar_conversacion(telefono: str) -> None:
    # ON DELETE CASCADE se encarga de mensajes, leads y cola_mensajes.
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("delete from conversaciones where telefono = %s", (telefono,))


def _obtener_o_crear_conversacion(telefono: str) -> dict:
    conversacion = ConversacionRepository.obtener_por_telefono(telefono)
    if conversacion is None:
        conversacion = ConversacionRepository.crear(telefono=telefono, origen="directo")
        print(f"(conversación nueva creada, id={conversacion['id']})")
    else:
        print(f"(reutilizando conversación existente, id={conversacion['id']}, estado={conversacion['estado']})")
    return conversacion


def _imprimir_estado(conversacion_id: int) -> None:
    lead = LeadRepository.obtener_por_conversacion(conversacion_id)
    if lead is None:
        print("(todavía no hay lead para esta conversación)")
        return
    print("--- Estado del lead ---")
    for campo, valor in lead.items():
        print(f"  {campo}: {valor}")
    print("-----------------------")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--telefono", default=_TELEFONO_DEFAULT, help="Número simulado, formato internacional sin '+' (ej: 593999999999)"
    )
    args = parser.parse_args()
    telefono = args.telefono

    print(f"=== Simulador de chat con Victoria (teléfono simulado: {telefono}) ===")
    print("Comandos: /reset  /estado  /salir  (Ctrl+C también termina)\n")

    conversacion = _obtener_o_crear_conversacion(telefono)
    servicio = VictoriaConversationService()
    mensaje_repo = MensajeRepository()

    try:
        while True:
            entrada = input("Tú: ").strip()
            if not entrada:
                continue
            if entrada == "/salir":
                break
            if entrada == "/reset":
                _borrar_conversacion(telefono)
                print("(conversación y lead borrados)")
                conversacion = _obtener_o_crear_conversacion(telefono)
                continue
            if entrada == "/estado":
                _imprimir_estado(conversacion["id"])
                continue

            # Se guarda ANTES de llamar a procesar_turno(), igual que hace
            # WebhookService en producción -- VictoriaConversationService
            # asume que el mensaje del cliente ya está persistido cuando
            # arma el historial (ver conversation_service.py, _construir_historial).
            mensaje_repo.crear(conversacion_id=conversacion["id"], rol="cliente", contenido=entrada, tipo="texto", wamid=None)
            respuesta = servicio.procesar_turno(conversacion_id=conversacion["id"], mensaje_cliente=entrada)
            print(f"Victoria: {respuesta}")

            conversacion = ConversacionRepository.obtener_por_id(conversacion["id"])
            if conversacion["estado"] == "escalada":
                print("\n(la conversación quedó escalada a un asesor humano -- Victoria ya no responde más acá)")
                break
    except KeyboardInterrupt:
        print("\n(salida solicitada con Ctrl+C)")


if __name__ == "__main__":
    main()
