"""
Pruebas de Victoria con errores humanos (ortografía, abreviaturas, palabras pegadas, nombres informales de producto,
respuestas de confirmación informales...). Usa la SIMULACIÓN del backend ("Probar con Victoria"): nada real se envía ni se
guarda; el pedido de Rocketfy y Telegram son de mentira. La IA es la REAL (Anthropic) cuando se pasa --real.

Uso (desde backend/, con las variables de CLAUDE.md §5 y, para --real, ANTHROPIC_API_KEY):
    python tools/pruebas_con_errores_humanos.py --seco            # IA falsa: solo comprueba que el guion corre
    python tools/pruebas_con_errores_humanos.py --real [ids...]   # IA real (cuesta unos centavos); ids = S1 S2 ... (todos si no se pasan)
Los mismos casos, para escribirlos a mano en la app, están en docs/PRUEBAS_CON_ERRORES_HUMANOS.md.
"""
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.integrations.llm.contratos import LLMProvider, RespuestaLLM
from src.routes.productos_bot.simulacion import simular_turno

PRODUCTO = {
    "id": 7, "sku": "AUD-BT-001", "nombre": "Audífonos Bluetooth", "descripcion": "Audífonos inalámbricos con 20 horas de batería, "
    "micrófono integrado y estuche de carga. No tienen cable.", "precio": Decimal("24.99"), "variantes": "Negro, blanco",
    "tiempo_entrega": "2 a 4 días hábiles", "metodos_pago_aceptados": "contraentrega, transferencia",
    "preguntas_frecuentes": "¿Incluyen estuche? Sí. ¿Tienen garantía? Consulta con un asesor.", "temas_no_responder": "Garantía",
    "max_unidades_por_pedido": 3, "estado": "publicado", "activo": True, "stock_ultimo": 50, "envio_incluido": True,
    "imagen_url": None,
}

# id: (título, qué se espera, [mensajes del cliente])
ESCENARIOS = {
    "S1": ("Compra completa con faltas de ortografía y ciudad mal escrita",
           "Corrige «guayakil» a Guayaquil sin preguntar, muestra el resumen con «Guayaquil, Guayas» y cierra tras el «sip».",
           ["ola kiero unos audifonos blutu", "cuanto cuestan? y q colores ay", "el negro xfa, 2",
            "mi nombre es maria jose pacheco, vivo en guayakil, provincia guayas, en la cdla kennedy mz 5 villa 3",
            "cuando llege pago", "sip todo bien"]),
    "S2": ("No sabe el nombre del producto",
           "Identifica el producto por la descripción («los que no tienen cable») y no inventa datos.",
           ["buenas tardes tienen esos audifonos q no tienen cable?", "los negros cuanto salen", "y viene con estuche?",
            "y la garantia cuanto es?"]),
    "S3": ("Palabras pegadas y letras comidas",
           "Entiende «quierocomprarlo», «mellamo juan», «vivoen cuenca».",
           ["holaquiero comprarlos audifonos", "mellamo juan perez vivoen cuenca azuay", "xq tan caro mm",
            "kiero 1 nomas blanco"]),
    "S4": ("Mensajes en pedacitos (llegan juntos tras la espera)",
           "Responde UNA vez a todo junto, sin repetir el saludo ni perderse.",
           ["Hola\nbuenas tardes\nquiero\nunos audifonos\nlos blancos"]),
    "S5": ("Respuestas de confirmación informales",
           "Entiende «dale», «👍», «ta bien» como sí; un «no, la direccion es otra» como corrección y vuelve a confirmar.",
           ["quiero 1 audifono negro", "ana lopez, quito pichincha, av amazonas n34-12 y atahualpa", "contraentrega",
            "no, la direccion es av. 10 de agosto y colon", "dale"]),
    "S6": ("Ciudad y provincia que no cuadran",
           "No guarda «Quito, Guayas» (no cuadra); pregunta cuál es la correcta sin inventar.",
           ["quiero 1 audifono blanco", "soy pedro ruiz, vivo en quito provincia guayas, calle 9 de octubre 123"]),
    "S7": ("Pide hablar con una persona, con errores",
           "Usa escalar_a_humano.", ["kiero ablar con una persona porfa"]),
    "S8": ("No quiere más mensajes",
           "Usa no_contactar y se despide con amabilidad.", ["no gracias, ya no me escriban mas porfa"]),
    "S11": ("Errores evidentes que no se preguntan",
            "«blanko» = Blanco y «quto» = Quito sin preguntar; el resumen los muestra bien escritos.",
            ["quiero 1 audifono blanko", "soy ana, vivo en quto, calle 10 y 12"]),
    "S9": ("Abreviaturas y jerga",
           "Entiende «cnto sale», «tmb», «x favor», «dnd» y no se pierde.",
           ["wenas cnto sale el aud blutu", "tmb ay en blanco? dnd lo envian? soy de ambato", "ok x favor 1 blanco"]),
    "S10": ("Respuesta ambigua / emoji solo",
            "Ante un 👍 o «ok» sin contexto claro, no confirma datos ni cierra por su cuenta.",
            ["hola", "👍", "ok", "ni idea q hago aqui"]),
}


class LLMSeco(LLMProvider):
    def generar_respuesta(self, system, mensajes, herramientas, max_tokens=1024, forzar_herramienta=None):
        return RespuestaLLM(texto="(respuesta de prueba)", llamadas_herramientas=[], razon_de_parada="fin")


def correr(id_escenario, llm):
    titulo, esperado, mensajes = ESCENARIOS[id_escenario]
    print(f"\n{'=' * 78}\n{id_escenario} — {titulo}\nEsperado: {esperado}\n{'-' * 78}")
    historial, estado = [], None
    for mensaje in mensajes:
        r = simular_turno(
            producto=PRODUCTO, mensaje=mensaje, historial=list(historial), estado=estado, desde_anuncio=False, llm=llm,
            imagenes=[],
        )
        print(f"CLIENTE : {mensaje!r}")
        for h in r.herramientas:
            entrada = {k: v for k, v in h["entrada"].items()}
            print(f"  [herramienta] {h['nombre']} {entrada or ''}\n                -> {str(h['resultado'])[:230].replace(chr(10), ' / ')}")
        print(f"VICTORIA: {r.respuesta}")
        historial += [{"rol": "cliente", "contenido": mensaje}, {"rol": "bot", "contenido": r.respuesta}]
        estado = r.estado
        if r.escalada:
            print("  (conversación escalada a una persona)")
            break
    e = estado or {}
    print(f"{'-' * 78}\nESTADO FINAL: nombre={e.get('nombre_cliente')!r} direccion={e.get('direccion')!r} canton={e.get('canton')!r} "
          f"provincia={e.get('provincia')!r} producto={e.get('producto_sku')!r} cant={e.get('cantidad')} "
          f"variante={e.get('producto_variante')!r} pago={e.get('metodo_pago')!r} pedido={'SI' if r.pedido else 'no'} "
          f"confirmado={'SI' if e.get('datos_confirmados_en') else 'no'}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--real" in args:
        from src.integrations.llm.factory import get_llm_client

        llm = get_llm_client()  # exige ANTHROPIC_API_KEY
    else:
        llm = LLMSeco()
    ids = [a for a in args if a in ESCENARIOS] or list(ESCENARIOS)
    for i in ids:
        correr(i, llm)
