"use client";

import { CircleCheck, FlaskConical, Image as ImageIcon, Info, Loader2, RotateCcw, Send, TriangleAlert, UserRound } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";

import { SectionCard } from "@/components/app/section-card";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useApi } from "@/hooks/use-api";
import { apiFetch, ApiError } from "@/lib/api";
import { formatMoney } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { AvisoSimulado, EstadoPrueba, FotoSimulada, LlamadaHerramienta, MensajePrueba, PedidoSimulado, ProbarInput, SolicitudSimulada, TurnoSimulado, UsoPruebas, VentaManualSimulada } from "@/types/producto-bot";

// Mismo límite que el backend (schemas.py).
const MAX_MENSAJE = 1000;

/** Escenarios para probar con un toque. `esperado` dice qué debería pasar, para
 * que se pueda juzgar si Victoria lo hizo bien. */
const ESCENARIOS = [
  { id: "comprar", label: "Quiero comprarlo", texto: "Hola, quiero comprarlo", esperado: "Victoria te pide los datos que faltan (nombre, dirección, cantón, provincia y forma de pago) y confirma el total." },
  { id: "envio", label: "¿Cuánto cuesta el envío?", texto: "¿Cuánto cuesta el envío y cuánto demora en llegar?", esperado: "Debe responder solo con lo que dice la ficha (tiempo de entrega). Si la ficha no habla del costo del envío, no debe inventarlo." },
  { id: "transferencia", label: "Pago por transferencia", texto: "Quiero pagar por transferencia bancaria", esperado: "Si aceptas transferencia, Victoria pide el comprobante y pasa la conversación a una persona (no ve imágenes). Si no la aceptas, debe decirlo." },
  { id: "fuera", label: "Pregunta fuera de la ficha", texto: "¿Tiene garantía de 5 años y puedo pagarlo en 12 cuotas con tarjeta de crédito?", esperado: "Debe pasar la conversación a una persona en vez de inventar una respuesta." },
  { id: "dos", label: "Quiero 2 unidades", texto: "Quiero 2 unidades", esperado: "Debe respetar el máximo de unidades por pedido: si pasa del máximo, se lo explica al cliente." },
  { id: "persona", label: "Quiero hablar con una persona", texto: "Prefiero hablar con una persona, por favor", esperado: "Debe pasar la conversación a una persona enseguida." },
  { id: "foto", label: "Quiero ver una foto", texto: "¿Tienes fotos? Quiero ver cómo se ve", esperado: "Si el producto tiene fotos, Victoria envía unas pocas (y las siguientes si pides más, sin repetir); si no tiene, dice que por ahora no hay imágenes sin prometerlas." },
] as const;

/** Escenarios de un producto PROPIO: el pedido no se crea solo, pasa al dueño. */
const ESCENARIOS_PROPIO = [
  { id: "ver", label: "Quiero verlo en persona", texto: "¿Puedo ir a ver el producto antes de comprarlo?", esperado: "Victoria avisa al dueño («Quiere ver el producto») y se despide: la conversación pasa a ti. No debe inventar una dirección ni una cita." },
  { id: "pagar", label: "¿Cómo pago?", texto: "Quiero pagar, ¿cómo lo hago?", esperado: "Victoria avisa al dueño («Quiere pagar») y sigue tomando los datos del pedido. No da cuentas bancarias ni confirma pagos: eso lo haces tú." },
  { id: "negociar", label: "¿Me haces rebaja?", texto: "¿Me lo puedes dejar más barato si llevo dos?", esperado: "Victoria no ofrece descuentos: avisa al dueño («Quiere negociar») y pasa la conversación." },
] as const;

type Escenario = { id: string; label: string; texto: string; esperado: string };

const NOMBRE_DE_HERRAMIENTA: Record<string, string> = {
  guardar_datos_cliente: "Guardó datos del cliente",
  registrar_producto: "Registró el producto",
  ver_ficha_producto: "Leyó la ficha del producto",
  registrar_metodo_pago: "Registró el método de pago",
  cerrar_venta: "Intentó cerrar la venta",
  escalar_a_humano: "Pasó la conversación a una persona",
  enviar_foto_producto: "Envió fotos del producto",
  registrar_entrega: "Ofreció / registró la entrega",
  solicitar_gestion: "Avisó al dueño",
};

type Turno = {
  cliente: string;
  bot: string;
  herramientas: LlamadaHerramienta[];
  avisos: AvisoSimulado[];
  fotos: FotoSimulada[];
};

function aHistorial(turnos: Turno[]): MensajePrueba[] {
  // Una foto queda en la conversación como un mensaje del bot, igual que en la vida real:
  // así Victoria sabe que ya la mandó y no la repite.
  return turnos.flatMap((t) => [
    { rol: "cliente" as const, contenido: t.cliente },
    ...t.fotos.map((f) => ({ rol: "bot" as const, contenido: f.mensaje })),
    { rol: "bot" as const, contenido: t.bot },
  ]);
}

function lineasDelPedido(payload: Record<string, unknown>): { sku: string; name: string; quantity: number }[] {
  try {
    const lineas: unknown = JSON.parse(String(payload.order_details ?? "[]"));
    return Array.isArray(lineas) ? (lineas as { sku: string; name: string; quantity: number }[]) : [];
  } catch {
    return [];
  }
}

/** `heredarColor`: sobre un fondo de estado (verde, ámbar) la etiqueta toma el color del
 * texto del panel en vez del gris, que ahí no tendría contraste suficiente. */
function Dato({ etiqueta, children, heredarColor, className }: { etiqueta: string; children?: ReactNode; heredarColor?: boolean; className?: string }) {
  const vacio = children === undefined || children === null || children === "";
  return (
    <div className={cn("space-y-0.5", className)}>
      <dt className={cn("text-xs", !heredarColor && "text-muted-foreground")}>{etiqueta}</dt>
      <dd className={cn("break-words text-sm", vacio && "text-muted-foreground/70")}>{vacio ? "—" : children}</dd>
    </div>
  );
}

function VentaEnCurso({ estado }: { estado: EstadoPrueba | null }) {
  const conEnvio = estado?.entregaNombre != null;
  const pago = estado?.metodoPago === "contraentrega" ? "Contraentrega" : estado?.metodoPago === "transferencia" ? "Transferencia" : null;
  return (
    <section aria-label="Venta en curso" className="grid gap-3 rounded-xl border bg-card p-3 sm:p-4">
      <div>
        <h3 className="text-sm font-semibold">Lo que Victoria ha anotado</h3>
        <p className="text-xs text-muted-foreground">Así se iría armando el pedido de verdad.</p>
      </div>
      <dl className="grid grid-cols-2 gap-x-3 gap-y-2.5">
        <Dato etiqueta="Cliente">{estado?.nombreCliente}</Dato>
        <Dato etiqueta="Pago">{pago}</Dato>
        <Dato className="col-span-2" etiqueta="Dirección">{estado?.direccion}</Dato>
        <Dato etiqueta="Cantón">{estado?.canton}</Dato>
        <Dato etiqueta="Provincia">{estado?.provincia}</Dato>
        <Dato className="col-span-2" etiqueta="Producto">
            {estado?.productoNombre ? `${estado.cantidad} × ${estado.productoNombre}${estado.productoVariante ? ` (${estado.productoVariante})` : ""}` : null}
          </Dato>
        {conEnvio && <Dato className="col-span-2" etiqueta="Entrega">{`${estado?.entregaNombre}${estado && Number(estado.costoEnvio) > 0 ? ` (+${formatMoney(estado.costoEnvio)})` : ""}`}</Dato>}
        <Dato etiqueta="Total a cobrar">{estado?.total ? <span className="tabular font-medium">{formatMoney(estado.total)}</span> : null}</Dato>
      </dl>
    </section>
  );
}

function PedidoQueSeHabriaEnviado({ pedido }: { pedido: PedidoSimulado }) {
  const p = pedido.payload;
  const lineas = lineasDelPedido(p);
  return (
    <section aria-label="Pedido simulado" className="grid gap-3 rounded-xl border border-status-success/30 bg-status-success-soft p-3 text-status-success-ink sm:p-4">
      <div className="flex items-start gap-2.5">
        <CircleCheck className="mt-0.5 size-4 shrink-0" aria-hidden />
        <div className="min-w-0">
          <h3 className="text-sm font-semibold">Pedido que se habría enviado a Rocketfy</h3>
          <p className="text-xs">Es una vista previa: no se envió nada. Estos son los datos tal como los recibiría Rocketfy.</p>
        </div>
      </div>
      <dl className="grid grid-cols-2 gap-x-3 gap-y-2.5">
        <Dato heredarColor etiqueta="Cliente">{String(p.name ?? "")}</Dato>
        <Dato heredarColor etiqueta="Teléfono">{String(p.phone ?? "")}</Dato>
        <Dato className="col-span-2" heredarColor etiqueta="Dirección">{[p.address, p.city, p.province].filter(Boolean).map(String).join(", ")}</Dato>
        <Dato heredarColor etiqueta="Total a cobrar">
          <span className="tabular font-medium">{formatMoney(String(p.total ?? ""))}</span>
        </Dato>
        <Dato heredarColor etiqueta="Cobro">{Number(p.not_COD) === 1 ? "Prepagado" : "Contraentrega"}</Dato>
        <Dato className="col-span-2" heredarColor etiqueta="Productos">
            {lineas.length > 0 ? (
              <ul className="list-disc space-y-0.5 pl-4">
                {lineas.map((l, i) => (
                  <li key={`${l.sku}-${i}`}>
                    {l.quantity} × {l.name} <span className="tabular text-xs">({l.sku})</span>
                  </li>
                ))}
              </ul>
            ) : null}
          </Dato>
      </dl>
      <details className="text-xs">
        <summary className="min-h-8 cursor-pointer py-1.5 font-medium underline-offset-2 hover:underline">Ver el envío completo (datos técnicos)</summary>
        <pre className="mt-1 max-h-48 overflow-auto rounded-md bg-card p-2 text-foreground">{JSON.stringify(p, null, 2)}</pre>
      </details>
    </section>
  );
}

/** Lo que se habría guardado al cerrar la venta de un producto propio (con su ganancia real). */
function VentaQueSeHabriaGuardado({ venta }: { venta: VentaManualSimulada }) {
  return (
    <section aria-label="Pedido para gestionar" className="grid gap-3 rounded-xl border border-status-success/30 bg-status-success-soft p-3 text-status-success-ink sm:p-4">
      <div className="flex items-start gap-2.5">
        <CircleCheck className="mt-0.5 size-4 shrink-0" aria-hidden />
        <div className="min-w-0">
          <h3 className="text-sm font-semibold">Pedido que te habría llegado para gestionar</h3>
          <p className="text-xs">Es una vista previa: no se guardó nada, no se descontó stock y no se avisó a nadie. En la vida real aparecería en «Por gestionar» y te llegaría un aviso por Telegram.</p>
        </div>
      </div>
      <dl className="grid grid-cols-2 gap-x-3 gap-y-2.5">
        <Dato className="col-span-2" heredarColor etiqueta="Producto">{`${venta.cantidad} × ${venta.producto}${venta.variante ? ` (${venta.variante})` : ""}`}</Dato>
        <Dato heredarColor etiqueta="Subtotal"><span className="tabular">{formatMoney(venta.subtotal)}</span></Dato>
        <Dato heredarColor etiqueta="Envío cobrado"><span className="tabular">{formatMoney(venta.costoEnvioCliente)}</span></Dato>
        <Dato heredarColor etiqueta="Total a cobrar"><span className="tabular font-semibold">{formatMoney(venta.total)}</span></Dato>
        <Dato heredarColor etiqueta="Entrega">{venta.entrega}</Dato>
        <Dato heredarColor etiqueta="Forma de pago">{venta.metodoPago === "transferencia" ? "Transferencia" : venta.metodoPago === "contraentrega" ? "Contraentrega" : venta.metodoPago}</Dato>
        <Dato heredarColor etiqueta="Tu ganancia">{venta.ganancia ? <span className="tabular font-semibold">{formatMoney(venta.ganancia)}</span> : "No se puede calcular (falta algún costo)"}</Dato>
      </dl>
    </section>
  );
}

function HerramientasUsadas({ herramientas }: { herramientas: LlamadaHerramienta[] }) {
  if (herramientas.length === 0) return null;
  return (
    <details className="mt-1.5 text-xs text-muted-foreground">
      <summary className="min-h-8 cursor-pointer py-1.5 font-medium hover:text-foreground">
        Herramientas que usó ({herramientas.length})
      </summary>
      <ol className="mt-1 space-y-2">
        {herramientas.map((h, i) => (
          <li key={`${h.nombre}-${i}`} className="space-y-0.5 rounded-md bg-muted/60 p-2">
            <p className="font-medium text-foreground">{NOMBRE_DE_HERRAMIENTA[h.nombre] ?? h.nombre}</p>
            {Object.keys(h.entrada).length > 0 && <p className="break-words">Datos: {JSON.stringify(h.entrada)}</p>}
            <p className="break-words">Respuesta del sistema: {h.resultado}</p>
          </li>
        ))}
      </ol>
    </details>
  );
}

/** «Probar con Victoria»: una conversación de ensayo con el mismo cerebro que
 * habla con los clientes, con tu ficha tal como está guardada. Nada sale a
 * Rocketfy, WhatsApp ni Telegram y la conversación no se guarda: vive aquí. */
export function ProbarConVictoria({
  sku,
  nombre,
  propio = false,
  sinCambiosPendientes,
  usarBorrador = false,
}: {
  sku: string;
  nombre: string;
  /** Un producto propio: la prueba ensaya también el cierre manual (el pedido pasa al dueño). */
  propio?: boolean;
  /** Falso si hay ediciones sin guardar: la prueba usa lo último guardado. */
  sinCambiosPendientes: boolean;
  /** Probar con el borrador de las instrucciones de Victoria (Parámetros → Instrucciones), no con las publicadas. */
  usarBorrador?: boolean;
}) {
  const [abierto, setAbierto] = useState(false);
  const [turnos, setTurnos] = useState<Turno[]>([]);
  const [estado, setEstado] = useState<EstadoPrueba | null>(null);
  const [pedido, setPedido] = useState<PedidoSimulado | null>(null);
  const [escalada, setEscalada] = useState(false);
  const [desdeAnuncio, setDesdeAnuncio] = useState(true);
  const [borrador, setBorrador] = useState("");
  const [pendiente, setPendiente] = useState<string | null>(null);
  const [error, setError] = useState<{ mensaje: string; motivos: string[] } | null>(null);
  const [usoLocal, setUsoLocal] = useState<UsoPruebas | null>(null);
  const [escenario, setEscenario] = useState<Escenario | null>(null);
  const [venta, setVenta] = useState<VentaManualSimulada | null>(null);
  const [solicitudes, setSolicitudes] = useState<SolicitudSimulada[]>([]);
  const registro = useRef<HTMLDivElement>(null);

  const usoApi = useApi<UsoPruebas>(abierto ? "/productos-bot/pruebas/uso" : null);
  const uso = usoLocal ?? usoApi.data;
  const sinUsos = uso != null && uso.restantes <= 0;

  const enviando = pendiente !== null;
  const despachado = estado?.estado === "despachado" || estado?.estado === "por_gestionar";
  // El máximo es un parámetro del sistema (Parámetros → «Mensajes por prueba»): llega del servidor.
  const maxMensajes = uso?.maxMensajes ?? null;
  const llegoAlMaximo = maxMensajes !== null && turnos.length >= maxMensajes;
  const terminada = escalada || despachado || llegoAlMaximo;
  const bloqueada = terminada || sinUsos;

  // La conversación siempre muestra lo último.
  useEffect(() => {
    const el = registro.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [turnos.length, pendiente, abierto]);

  async function enviar(texto: string) {
    const mensaje = texto.trim();
    if (!mensaje || enviando || bloqueada) return;
    setPendiente(mensaje);
    setError(null);
    setBorrador("");
    const cuerpo: ProbarInput = { mensaje, historial: aHistorial(turnos), estado, desdeAnuncio, escalada, ...(usarBorrador ? { usarBorrador: true } : {}) };
    try {
      const res = await apiFetch<TurnoSimulado>(`/productos-bot/${encodeURIComponent(sku)}/probar`, {
        method: "POST",
        body: JSON.stringify(cuerpo),
      });
      setTurnos((previos) => [...previos, { cliente: mensaje, bot: res.respuesta, herramientas: res.herramientas, avisos: res.avisos, fotos: res.fotos ?? [] }]);
      setEstado(res.estado);
      setEscalada(res.escalada);
      if (res.pedido) setPedido(res.pedido);
      if (res.ventaManual) setVenta(res.ventaManual);
      if (res.solicitudes?.length) setSolicitudes((previas) => [...previas, ...res.solicitudes.filter((s) => !previas.some((p) => p.tipo === s.tipo))]);
      setUsoLocal(res.uso);
    } catch (err) {
      // El mensaje vuelve al cuadro para poder reintentar sin reescribirlo.
      setBorrador(mensaje);
      if (err instanceof ApiError && err.status === 422 && err.bloqueos.length > 0) {
        setError({ mensaje: "Antes de probar, completa esto en la ficha y guárdala:", motivos: err.bloqueos });
      } else {
        setError({ mensaje: err instanceof ApiError ? err.message : "No se pudo conectar con el servidor.", motivos: [] });
      }
      if (err instanceof ApiError && err.status === 429) usoApi.recargar();
    } finally {
      setPendiente(null);
    }
  }

  function enviarFormulario(e: FormEvent) {
    // Por si algún día este cuadro queda dentro de otro formulario.
    e.preventDefault();
    e.stopPropagation();
    void enviar(borrador);
  }

  function reiniciar() {
    setTurnos([]);
    setEstado(null);
    setPedido(null);
    setVenta(null);
    setSolicitudes([]);
    setEscalada(false);
    setBorrador("");
    setError(null);
    setEscenario(null);
  }

  const avisos = turnos.flatMap((t) => t.avisos);
  const hayPrueba = turnos.length > 0;

  return (
    <SectionCard
      titulo={usarBorrador ? "Probar el borrador con Victoria" : "Probar con Victoria"}
      descripcion={usarBorrador ? "Conversa con las instrucciones del borrador antes de publicarlas. Los clientes no ven nada." : "Conversa como un cliente antes de publicar. No se envía nada real."}
    >
      <div className="space-y-3 p-4 sm:p-5">
        <p className="text-sm text-muted-foreground">
          {usarBorrador
            ? "Mira cómo responde Victoria con tu borrador de instrucciones y la ficha del producto que elegiste: si mantiene el tono, si respeta tus reglas y si sigue cerrando bien la venta."
            : "Mira cómo responde Victoria con la ficha que guardaste: si cierra bien la venta, si respeta el máximo de unidades y si pasa a una persona lo que no sabe."}
        </p>

        <Dialog open={abierto} onOpenChange={setAbierto}>
          <DialogTrigger asChild>
            <Button type="button" variant="outline" disabled={!sinCambiosPendientes} className="w-full sm:w-auto">
              <FlaskConical /> {hayPrueba ? "Seguir la prueba" : "Abrir la prueba"}
            </Button>
          </DialogTrigger>
          {!sinCambiosPendientes && <p className="text-xs text-muted-foreground">Guarda o descarta tus cambios para probar: la prueba usa lo último que guardaste.</p>}
          {hayPrueba && sinCambiosPendientes && (
            <p role="status" className="text-xs text-muted-foreground">
              {pedido || venta ? "Hay una compra de prueba completada." : `Hay una prueba en curso (${turnos.length} ${turnos.length === 1 ? "mensaje" : "mensajes"}).`}
            </p>
          )}

          <DialogContent className="max-h-[92dvh] overflow-y-auto sm:max-w-4xl">
            <DialogHeader>
              <DialogTitle>Probar con Victoria</DialogTitle>
              <DialogDescription>
                Es una conversación de ensayo con «{nombre}» tal como está guardado
                {usarBorrador && <>, usando <strong className="font-medium text-foreground">tu borrador de instrucciones</strong></>}.{" "}
                <strong className="font-medium text-foreground">No se envía nada a Rocketfy, WhatsApp ni Telegram, no se guarda ninguna venta y la conversación no se guarda.</strong> Cada mensaje usa la IA y cuenta para tu tope diario.
              </DialogDescription>
            </DialogHeader>

            <div className="grid grid-cols-[minmax(0,1fr)] gap-4 md:grid-cols-[minmax(0,1fr)_18rem]">
              <div className="grid min-w-0 grid-cols-[minmax(0,1fr)] content-start gap-3">
                <label htmlFor="prueba-anuncio" className="flex min-h-12 cursor-pointer items-start gap-3 rounded-lg border bg-card p-3 has-[:disabled]:cursor-not-allowed has-[:disabled]:opacity-60">
                  <Checkbox id="prueba-anuncio" checked={desdeAnuncio} disabled={hayPrueba || enviando} onCheckedChange={(c) => setDesdeAnuncio(c === true)} className="mt-0.5" />
                  <span className="min-w-0">
                    <span className="block text-sm font-medium">El cliente llega desde un anuncio de este producto</span>
                    <span className="hidden text-xs text-muted-foreground sm:block">Así Victoria ya sabe de qué producto habla. Se elige antes del primer mensaje.</span>
                  </span>
                </label>

                <div>
                  <p id="prueba-escenarios" className="mb-1.5 text-xs font-medium text-muted-foreground">
                    Escenarios rápidos
                  </p>
                  <div
                    role="group"
                    aria-labelledby="prueba-escenarios"
                    // Con todos los botones deshabilitados, la fila con scroll no tendría nada enfocable: se enfoca ella misma.
                    tabIndex={enviando || bloqueada ? 0 : undefined}
                    className="-mx-1 flex gap-2 overflow-x-auto px-1 pb-1 sm:mx-0 sm:flex-wrap sm:overflow-visible sm:px-0 sm:pb-0">
                    {[...ESCENARIOS, ...(propio ? ESCENARIOS_PROPIO : [])].map((e) => (
                      <Button
                        key={e.id}
                        type="button"
                        variant="outline"
                        size="sm"
                        className="shrink-0"
                        disabled={enviando || bloqueada}
                        onClick={() => {
                          setEscenario(e);
                          void enviar(e.texto);
                        }}
                      >
                        {e.label}
                      </Button>
                    ))}
                  </div>
                  {escenario && (
                    <p className="mt-2 flex items-start gap-1.5 text-xs text-muted-foreground">
                      <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden />
                      <span>
                        <span className="font-medium text-foreground">Qué esperar con «{escenario.label}»:</span> {escenario.esperado}
                      </span>
                    </p>
                  )}
                </div>

                <div
                  ref={registro}
                  role="log"
                  aria-label="Conversación de prueba"
                  aria-busy={enviando}
                  className="flex h-[min(20rem,36dvh)] flex-col gap-3 overflow-y-auto rounded-xl border bg-muted/30 p-3"
                >
                  {turnos.length === 0 && !enviando && (
                    <p className="m-auto max-w-xs text-center text-sm text-muted-foreground">Escribe como lo haría un cliente, o toca un escenario rápido para empezar.</p>
                  )}
                  {turnos.map((t, i) => (
                    <div key={i} className="grid gap-3">
                      <div className="flex justify-end">
                        <p className="max-w-[85%] whitespace-pre-wrap break-words rounded-2xl rounded-br-sm bg-primary px-3.5 py-2 text-sm text-primary-foreground">
                          <span className="sr-only">Cliente de prueba: </span>
                          {t.cliente}
                        </p>
                      </div>
                      {t.fotos.map((foto, j) => (
                        <div key={j} className="flex flex-col items-start">
                          <p className="flex max-w-[90%] items-start gap-2 rounded-2xl rounded-bl-sm border bg-card px-3.5 py-2 text-sm">
                            <ImageIcon className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden />
                            <span className="min-w-0">
                              <span className="sr-only">Victoria: </span>
                              Foto enviada: {foto.descripcion}{" "}
                              <a href={foto.url} target="_blank" rel="noopener noreferrer" className="rounded-sm text-xs underline underline-offset-2 outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring">
                                ver imagen
                              </a>
                              <span className="block text-xs text-muted-foreground">No se envió nada: así se vería en WhatsApp.</span>
                            </span>
                          </p>
                        </div>
                      ))}
                      <div className="flex flex-col items-start">
                        <div className="max-w-[90%] rounded-2xl rounded-bl-sm border bg-card px-3.5 py-2 text-sm">
                          <p className="whitespace-pre-wrap break-words">
                            <span className="sr-only">Victoria: </span>
                            {t.bot || "(Victoria no escribió texto en este turno)"}
                          </p>
                          <HerramientasUsadas herramientas={t.herramientas} />
                        </div>
                      </div>
                    </div>
                  ))}
                  {pendiente !== null && (
                    <div className="grid gap-3">
                      <div className="flex justify-end">
                        <p className="max-w-[85%] whitespace-pre-wrap break-words rounded-2xl rounded-br-sm bg-primary px-3.5 py-2 text-sm text-primary-foreground">
                          <span className="sr-only">Cliente de prueba: </span>
                          {pendiente}
                        </p>
                      </div>
                      <p role="status" className="flex items-center gap-2 text-xs text-muted-foreground">
                        <Loader2 className="size-3.5 animate-spin" aria-hidden /> Victoria está escribiendo… (unos segundos)
                      </p>
                    </div>
                  )}
                </div>

                {escalada && !despachado && (
                  <p role="status" className="flex items-start gap-2.5 rounded-lg bg-status-warning-soft p-3 text-sm text-status-warning-ink">
                    <UserRound className="mt-0.5 size-4 shrink-0" aria-hidden />
                    Victoria pasó la conversación a una persona. En la vida real ya no seguiría respondiendo: reinicia la prueba para probar otro caso.
                  </p>
                )}
                {despachado && (
                  <p role="status" className="flex items-start gap-2.5 rounded-lg bg-status-success-soft p-3 text-sm text-status-success-ink">
                    <CircleCheck className="mt-0.5 size-4 shrink-0" aria-hidden />
                    La compra se cerró. En la vida real, si el cliente vuelve a escribir lo atiende una persona. Reinicia la prueba para probar otro caso.
                  </p>
                )}
                {llegoAlMaximo && !escalada && !despachado && (
                  <p role="status" className="flex items-start gap-2.5 rounded-lg bg-status-info-soft p-3 text-sm text-status-info-ink">
                    <Info className="mt-0.5 size-4 shrink-0" aria-hidden />
                    La prueba llegó a {maxMensajes} mensajes. Reiníciala para empezar de nuevo.
                  </p>
                )}

                {error && (
                  <div role="alert" className="flex items-start gap-2.5 rounded-lg bg-status-danger-soft p-3 text-sm text-status-danger-ink">
                    <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
                    <div className="min-w-0 space-y-1">
                      <p className="font-medium">{error.mensaje}</p>
                      {error.motivos.length > 0 && (
                        <ul className="list-disc space-y-1 pl-4">
                          {error.motivos.map((m) => (
                            <li key={m}>{m}</li>
                          ))}
                        </ul>
                      )}
                    </div>
                  </div>
                )}

                <form onSubmit={enviarFormulario} noValidate className="flex items-end gap-2">
                  <div className="grid min-w-0 flex-1 gap-1.5">
                    <Label htmlFor="prueba-mensaje" className="sr-only">
                      Mensaje del cliente de prueba
                    </Label>
                    <Input
                      id="prueba-mensaje"
                      value={borrador}
                      maxLength={MAX_MENSAJE}
                      autoComplete="off"
                      placeholder={bloqueada ? "La prueba terminó" : "Escribe como el cliente…"}
                      disabled={bloqueada}
                      onChange={(e) => setBorrador(e.target.value)}
                    />
                  </div>
                  <Button type="submit" disabled={bloqueada || enviando || !borrador.trim()}>
                    {enviando ? <Loader2 className="animate-spin" /> : <Send />}
                    Enviar
                  </Button>
                </form>

                <p role="status" className={cn("text-xs", sinUsos ? "font-medium text-status-warning-ink" : "text-muted-foreground")}>
                  {uso == null
                    ? "Consultando cuántos mensajes de prueba te quedan hoy…"
                    : sinUsos
                      ? `Llegaste al tope de hoy (${uso.tope} mensajes de prueba). Puedes subirlo en «Ajustes de precios»; el contador se reinicia a medianoche.`
                      : `Te quedan ${uso.restantes} de ${uso.tope} mensajes de prueba hoy.`}
                </p>
              </div>

              <div className="grid min-w-0 grid-cols-[minmax(0,1fr)] content-start gap-3">
                <VentaEnCurso estado={estado} />
                {pedido && <PedidoQueSeHabriaEnviado pedido={pedido} />}
                {venta && <VentaQueSeHabriaGuardado venta={venta} />}
                {solicitudes.length > 0 && (
                  <section aria-label="Solicitudes de gestión" className="grid gap-1.5 rounded-xl border bg-card p-3 sm:p-4">
                    <h3 className="text-sm font-semibold">Lo que te habría llegado en «Por gestionar»</h3>
                    <ul className="list-disc space-y-1 pl-4 text-sm">
                      {solicitudes.map((s) => (
                        <li key={s.tipo}>
                          <span className="font-medium">{s.etiqueta}</span>
                          {s.detalle ? `: ${s.detalle}` : ""}
                        </li>
                      ))}
                    </ul>
                  </section>
                )}
                {avisos.length > 0 && (
                  <section aria-label="Avisos que se habrían enviado" className="grid gap-1.5 rounded-xl border bg-status-warning-soft p-3 text-status-warning-ink sm:p-4">
                    <h3 className="text-sm font-semibold">Avisos que se habrían enviado a Telegram</h3>
                    <ul className="list-disc space-y-1 pl-4 text-sm">
                      {avisos.map((a, i) => (
                        <li key={i}>{a.texto}</li>
                      ))}
                    </ul>
                    <p className="text-xs">No se envió ninguno: así sabrías en la vida real que una persona debe intervenir.</p>
                  </section>
                )}
              </div>
            </div>

            <DialogFooter>
              <Button type="button" variant="outline" disabled={enviando || !hayPrueba} onClick={reiniciar}>
                <RotateCcw /> Reiniciar prueba
              </Button>
              <DialogClose asChild>
                <Button type="button">Cerrar</Button>
              </DialogClose>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </SectionCard>
  );
}
