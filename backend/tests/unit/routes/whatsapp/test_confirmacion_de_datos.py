"""
Confirmación de los datos de envío con el cliente antes de cerrar la venta.

Victoria arma el resumen con `mostrar_resumen_para_confirmar` (lo redacta el CÓDIGO con los datos guardados), el cliente
responde que sí, Victoria usa `confirmar_datos_envio` y solo entonces `cerrar_venta` funciona. Cambiar cualquier dato
borra la confirmación.
"""
import pytest

from src.routes.productos_bot.simulacion import MensajesEnMemoria
from src.routes.whatsapp.confirmacion import datos_que_faltan, texto_de_confirmacion
from tests.unit.routes.whatsapp.test_tools_propios import Escena, _listo_para_cerrar

pytestmark = pytest.mark.confirma_datos


class EscenaConfirmable(Escena):
    """La escena de siempre, con una conversación que tiene «hora» para saber si el cliente contestó después del resumen."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.mensajes = MensajesEnMemoria([], "Quiero comprar")
        self.herramientas._mensajes = self.mensajes
        self.leads.reloj = lambda: len(self.mensajes.filas)

    def cliente_escribe(self, texto):
        self.mensajes.filas.append({"rol": "cliente", "contenido": texto, "tipo": "texto", "creado_en": len(self.mensajes.filas) + 1})

    def bot_escribe(self, texto):
        self.mensajes.crear(1, "bot", texto)


def _con_todo_listo(**kw):
    e = EscenaConfirmable(**kw)
    _listo_para_cerrar(e)
    return e


class TestResumen:
    def test_el_resumen_lo_arma_el_codigo_con_los_datos_guardados(self):
        e = _con_todo_listo()
        mensaje = e.usar("mostrar_resumen_para_confirmar")

        assert "No cierres la venta todavía" in mensaje
        assert "Nombre: Ana" in mensaje and "Dirección: Calle 1 y Av. 2 — Cuenca, Azuay" in mensaje
        assert "Producto: 2 × Zapatos de cuero" in mensaje and "Total a pagar: $62.00" in mensaje
        assert "Entrega: Envío en Cuenca" in mensaje and "Contra entrega" in mensaje
        assert e.lead["datos_confirmacion_pedida_en"] is not None and e.lead["datos_confirmados_en"] is None

    def test_si_falta_algo_dice_que_falta_y_no_marca_nada(self):
        e = EscenaConfirmable()
        e.registrar_producto()
        mensaje = e.usar("mostrar_resumen_para_confirmar")
        assert "falta" in mensaje and "la dirección" in mensaje and "la forma de pago" in mensaje
        assert e.lead["datos_confirmacion_pedida_en"] is None

    def test_si_el_envio_va_aparte_pide_elegir_la_entrega_antes(self):
        e = EscenaConfirmable()
        e.registrar_producto()
        e.datos_completos()
        e.usar("registrar_metodo_pago", metodo_pago="contraentrega")
        assert "la opción de entrega" in e.usar("mostrar_resumen_para_confirmar")

    def test_el_telefono_se_muestra_como_lo_escribe_un_ecuatoriano(self):
        lead = {"nombre_cliente": "Ana", "direccion": "Calle 1", "canton": "QUITO", "provincia": "Pichincha", "cantidad": 1,
                "producto_sku": "R-1", "producto_nombre": "Reloj", "total": "24.99", "metodo_pago": "transferencia", "telefono": "593987654321"}
        texto = texto_de_confirmacion(lead)
        assert "Teléfono: 0987654321" in texto and "Quito, Pichincha" in texto and "Transferencia" in texto
        assert datos_que_faltan(lead, None) == []


class TestConfirmar:
    def test_no_se_puede_confirmar_sin_haber_mostrado_el_resumen(self):
        e = _con_todo_listo()
        mensaje = e.usar("confirmar_datos_envio")
        assert "Todavía no le mostraste el resumen" in mensaje and e.lead["datos_confirmados_en"] is None

    def test_no_se_puede_confirmar_en_el_mismo_turno_sin_que_el_cliente_conteste(self):
        e = _con_todo_listo()
        e.usar("mostrar_resumen_para_confirmar")
        assert "todavía no respondió" in e.usar("confirmar_datos_envio")
        assert e.lead["datos_confirmados_en"] is None

    def test_con_la_respuesta_del_cliente_queda_confirmado(self):
        e = _con_todo_listo()
        e.usar("mostrar_resumen_para_confirmar")
        e.bot_escribe("(el resumen)")
        e.cliente_escribe("Sí, todo correcto")
        assert "Datos confirmados" in e.usar("confirmar_datos_envio")
        assert e.lead["datos_confirmados_en"] is not None
        assert "ya estaban confirmados" in e.usar("confirmar_datos_envio")

    @pytest.mark.parametrize(
        "cambio",
        [
            lambda e: e.usar("guardar_datos_cliente", direccion="Otra calle 5"),
            lambda e: e.usar("guardar_datos_cliente", nombre_cliente="Ana María"),
            lambda e: e.usar("registrar_metodo_pago", metodo_pago="transferencia"),
            lambda e: e.registrar_producto(cantidad=1),
        ],
    )
    def test_cambiar_un_dato_borra_la_confirmacion(self, cambio):
        e = _con_todo_listo()
        e.usar("mostrar_resumen_para_confirmar")
        e.cliente_escribe("Sí")
        e.usar("confirmar_datos_envio")
        assert e.lead["datos_confirmados_en"] is not None

        cambio(e)

        assert e.lead["datos_confirmados_en"] is None and e.lead["datos_confirmacion_pedida_en"] is None

    def test_repetir_el_mismo_dato_no_obliga_a_confirmar_otra_vez(self):
        e = _con_todo_listo()
        e.usar("mostrar_resumen_para_confirmar")
        e.cliente_escribe("Sí")
        e.usar("confirmar_datos_envio")
        e.usar("guardar_datos_cliente", direccion="Calle 1 y Av. 2")
        e.usar("registrar_metodo_pago", metodo_pago="contraentrega")
        assert e.lead["datos_confirmados_en"] is not None


class TestCerrarVenta:
    def test_sin_confirmar_no_cierra(self):
        e = _con_todo_listo()
        mensaje = e.usar("cerrar_venta")
        assert "el cliente debe confirmar sus datos" in mensaje and "mostrar_resumen_para_confirmar" in mensaje
        assert e.lead["estado"] != "por_gestionar" and not e.conversaciones.en_gestion

    def test_con_el_resumen_mostrado_pero_sin_respuesta_tampoco_cierra(self):
        e = _con_todo_listo()
        e.usar("mostrar_resumen_para_confirmar")
        assert "debe confirmar" in e.usar("cerrar_venta")

    def test_confirmado_si_cierra(self):
        e = _con_todo_listo()
        e.usar("mostrar_resumen_para_confirmar")
        e.cliente_escribe("Sí, correcto")
        e.usar("confirmar_datos_envio")
        assert "¡Pedido registrado!" in e.usar("cerrar_venta")
        assert e.lead["estado"] == "por_gestionar"

    def test_si_cambia_un_dato_despues_de_confirmar_hay_que_confirmar_de_nuevo(self):
        e = _con_todo_listo()
        e.usar("mostrar_resumen_para_confirmar")
        e.cliente_escribe("Sí")
        e.usar("confirmar_datos_envio")
        e.usar("guardar_datos_cliente", direccion="Otra dirección")
        assert "debe confirmar" in e.usar("cerrar_venta")

    def test_el_dueno_puede_apagar_la_confirmacion(self, monkeypatch):
        from src.config.parametros import parametros

        real = parametros.valor
        monkeypatch.setattr(parametros, "valor", lambda c: False if c == "bot.confirmar_datos_antes_de_cerrar" else real(c))
        e = _con_todo_listo()
        assert "¡Pedido registrado!" in e.usar("cerrar_venta")

    def test_por_defecto_viene_encendida(self):
        from src.config.parametros import parametros

        assert parametros.valor("bot.confirmar_datos_antes_de_cerrar") is True

    def test_lo_que_ya_estaba_cerrado_no_se_pide_confirmar_otra_vez(self):
        e = _con_todo_listo()
        e.lead["estado"] = "por_gestionar"
        assert "ya quedó registrado" in e.usar("cerrar_venta")
