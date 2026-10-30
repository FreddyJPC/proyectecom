"use client";

import { Bot, CircleSlash, Clock, Info, Loader2, NotebookPen, Package, SendHorizontal, UserRound } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent, type ReactNode } from "react";
import { toast } from "sonner";

import { AvatarInitials } from "@/components/app/avatar-initials";
import { EmptyState } from "@/components/app/empty-state";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { useApi } from "@/hooks/use-api";
import { apiFetch, ApiError } from "@/lib/api";
import { estadoConversacionInfo } from "@/lib/estados";
import { etiquetaDia, formatFechaHora, formatHora, formatMoney, formatPhone, tiempoRestante } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { ConversacionDetalleCompleto, LeadConversacion, MensajeConversacion } from "@/types/conversacion";

const REFRESCO_MS = 15_000;

function Dato({ label, children }: { label: string; children?: ReactNode }) {
  const vacio = children === undefined || children === null || children === "";
  return (
    <div className="space-y-0.5">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className={cn("text-sm", vacio && "text-muted-foreground/70 italic")}>{vacio ? "Sin definir aún" : children}</dd>
    </div>
  );
}

function Burbuja({ m, mostrarAutor }: { m: MensajeConversacion; mostrarAutor: boolean }) {
  const esCliente = m.rol === "cliente";
  const esBot = m.rol === "bot";
  const esMedia = m.tipo !== "texto" || /^\[.*\]$/.test(m.contenido);

  return (
    <div className={cn("flex flex-col gap-1", esCliente ? "items-start" : "items-end")}>
      {mostrarAutor && (
        <span className="flex items-center gap-1 px-1 text-xs text-muted-foreground">
          {esBot && <Bot className="size-3" aria-hidden />}
          {esCliente ? "Cliente" : esBot ? "Victoria" : "Tú"}
        </span>
      )}
      <div
        className={cn(
          "max-w-[86%] rounded-2xl px-3.5 py-2 text-[0.9375rem] leading-relaxed whitespace-pre-wrap shadow-card sm:max-w-md lg:max-w-lg",
          esCliente && "rounded-tl-md border bg-card",
          esBot && "rounded-tr-md bg-accent text-accent-foreground",
          !esCliente && !esBot && "rounded-tr-md bg-primary text-primary-foreground",
          esMedia && "italic opacity-90",
        )}
      >
        {m.contenido}
        <span
          className={cn(
            "tabular mt-0.5 block text-right text-[0.65rem] leading-none",
            esCliente ? "text-muted-foreground" : esBot ? "text-accent-foreground/60" : "text-primary-foreground/70",
          )}
        >
          {formatHora(m.creadoEn)}
        </span>
      </div>
    </div>
  );
}

function PanelDatos({
  lead,
  conversacion,
  nota,
  onNota,
  onGuardarNota,
  guardandoNota,
  notaCambiada,
  telefono,
}: {
  lead: LeadConversacion | null;
  conversacion: ConversacionDetalleCompleto["conversacion"];
  nota: string;
  onNota: (v: string) => void;
  onGuardarNota: () => void;
  guardandoNota: boolean;
  notaCambiada: boolean;
  telefono: string;
}) {
  const puedeCrearPedido = Boolean(lead?.nombreCliente && lead?.direccion && lead?.productoNombre) && lead?.estado !== "despachado";

  const paramsPedido = new URLSearchParams();
  if (lead?.nombreCliente) paramsPedido.set("nombreCliente", lead.nombreCliente);
  if (telefono) paramsPedido.set("telefono", telefono);
  if (lead?.direccion) paramsPedido.set("direccion", lead.direccion);
  if (lead?.canton) paramsPedido.set("canton", lead.canton);
  if (lead?.provincia) paramsPedido.set("provincia", lead.provincia);
  if (lead?.productoSku) paramsPedido.set("productoSku", lead.productoSku);
  if (lead?.productoNombre) paramsPedido.set("productoNombre", lead.productoNombre);
  if (lead?.total) paramsPedido.set("total", lead.total);

  return (
    <div className="flex flex-col gap-6 p-4">
      <section aria-labelledby="t-cliente" className="space-y-3">
        <h3 id="t-cliente" className="flex items-center gap-2 text-sm font-semibold">
          <UserRound className="size-4 text-muted-foreground" aria-hidden /> Cliente
        </h3>
        <dl className="space-y-3">
          <Dato label="Nombre">{lead?.nombreCliente}</Dato>
          <Dato label="Teléfono">
            <a href={`tel:+${telefono}`} className="tabular text-primary underline-offset-2 hover:underline">
              {formatPhone(telefono)}
            </a>
          </Dato>
          <Dato label="Dirección">{lead?.direccion}</Dato>
          <Dato label="Cantón y provincia">{[lead?.canton, lead?.provincia].filter(Boolean).join(", ")}</Dato>
        </dl>
      </section>

      <section aria-labelledby="t-pedido" className="space-y-3 border-t pt-5">
        <h3 id="t-pedido" className="flex items-center gap-2 text-sm font-semibold">
          <Package className="size-4 text-muted-foreground" aria-hidden /> Compra
        </h3>
        <dl className="space-y-3">
          <Dato label="Producto">{lead?.productoNombre}</Dato>
          {lead?.productoVariante && <Dato label="Variante">{lead.productoVariante}</Dato>}
          <Dato label="Total">{lead?.total ? <span className="tabular font-semibold">{formatMoney(lead.total)}</span> : undefined}</Dato>
          <Dato label="Método de pago">{lead?.metodoPago}</Dato>
          <Dato label="Estado del lead">{lead?.estado?.replace(/_/g, " ")}</Dato>
          {conversacion.idAnuncio && <Dato label="Vino de un anuncio">{conversacion.idAnuncio}</Dato>}
        </dl>

        {lead?.idPedidoRocketfy && lead?.idPedidoLocal && (
          <Button variant="outline" asChild className="w-full">
            <Link href={`/pedidos/${lead.idPedidoLocal}`}>Ver pedido #{lead.idPedidoLocal}</Link>
          </Button>
        )}
        {puedeCrearPedido && (
          <Button asChild className="w-full">
            <Link href={`/pedidos/nuevo?${paramsPedido.toString()}`}>Crear pedido con estos datos</Link>
          </Button>
        )}
      </section>

      <section aria-labelledby="t-notas" className="space-y-3 border-t pt-5">
        <h3 id="t-notas" className="flex items-center gap-2 text-sm font-semibold">
          <NotebookPen className="size-4 text-muted-foreground" aria-hidden /> Notas internas
        </h3>
        <p className="text-xs text-muted-foreground">Privadas: nunca se le muestran al cliente ni a Victoria.</p>
        <Textarea value={nota} onChange={(e) => onNota(e.target.value)} rows={4} aria-label="Notas internas" placeholder="Escribe aquí lo que debas recordar de este cliente…" />
        <Button size="sm" variant={notaCambiada ? "default" : "outline"} onClick={onGuardarNota} disabled={guardandoNota || !notaCambiada}>
          {guardandoNota ? (
            <>
              <Loader2 className="animate-spin" /> Guardando…
            </>
          ) : notaCambiada ? (
            "Guardar nota"
          ) : (
            "Guardada"
          )}
        </Button>
      </section>
    </div>
  );
}

export default function ConversacionDetallePage() {
  const { id } = useParams<{ id: string }>();
  const { data, error, cargando, recargar } = useApi<ConversacionDetalleCompleto>(`/conversaciones/${id}`, {
    intervalo: REFRESCO_MS,
  });

  const [mensaje, setMensaje] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [pendientes, setPendientes] = useState<MensajeConversacion[]>([]);
  const [notaLocal, setNotaLocal] = useState<string | null>(null);
  const [guardandoNota, setGuardandoNota] = useState(false);
  const [reactivando, setReactivando] = useState(false);
  const [panelAbierto, setPanelAbierto] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const mensajes = data ? [...data.mensajes, ...pendientes] : [];

  // Al llegar mensajes nuevos (o al abrir otro chat) bajar al último.
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [mensajes.length, id]);

  async function handleEnviar(e?: FormEvent) {
    e?.preventDefault();
    const texto = mensaje.trim();
    if (!texto || !data || enviando) return;

    setEnviando(true);
    const optimista: MensajeConversacion = {
      id: -Date.now(),
      rol: "humano",
      contenido: texto,
      tipo: "texto",
      creadoEn: new Date().toISOString(),
    };
    // Actualización optimista: el mensaje aparece al instante. Si falla (p. ej.
    // 409 porque la ventana se cerró justo ahora) se quita y se devuelve el texto.
    setPendientes((p) => [...p, optimista]);
    setMensaje("");

    try {
      await apiFetch(`/conversaciones/${id}/mensajes`, { method: "POST", body: JSON.stringify({ contenido: texto }) });
      recargar();
      setPendientes((p) => p.filter((x) => x.id !== optimista.id));
    } catch (err) {
      setPendientes((p) => p.filter((x) => x.id !== optimista.id));
      setMensaje(texto);
      toast.error(err instanceof ApiError ? err.message : "No se pudo enviar el mensaje.");
      recargar();
    } finally {
      setEnviando(false);
    }
  }

  function alTeclear(e: KeyboardEvent<HTMLTextAreaElement>) {
    // En escritorio Enter envía y Shift+Enter hace salto de línea; en pantallas
    // táctiles Enter es salto de línea (para eso está el botón de enviar).
    const esTactil = window.matchMedia("(pointer: coarse)").matches;
    if (e.key === "Enter" && !e.shiftKey && !esTactil) {
      e.preventDefault();
      void handleEnviar();
    }
  }

  async function handleGuardarNota() {
    if (notaLocal === null) return;
    setGuardandoNota(true);
    try {
      await apiFetch(`/conversaciones/${id}/notas`, { method: "PATCH", body: JSON.stringify({ notasInternas: notaLocal }) });
      toast.success("Nota guardada.");
      recargar();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo guardar la nota.");
    } finally {
      setGuardandoNota(false);
    }
  }

  async function handleReactivar() {
    setReactivando(true);
    try {
      await apiFetch(`/conversaciones/${id}/reactivar`, { method: "POST" });
      toast.success("Se devolvió el control a Victoria.");
      recargar();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo reactivar la conversación.");
    } finally {
      setReactivando(false);
    }
  }

  if (cargando) {
    return (
      <div className="flex flex-1 flex-col" aria-busy="true">
        <div className="flex items-center gap-3 border-b bg-card p-4">
          <Skeleton className="size-11 rounded-full" />
          <div className="space-y-2">
            <Skeleton className="h-4 w-40" />
            <Skeleton className="h-3 w-28" />
          </div>
        </div>
        <div className="flex-1 space-y-4 p-4">
          <Skeleton className="h-12 w-3/5 rounded-2xl" />
          <Skeleton className="ml-auto h-16 w-2/3 rounded-2xl" />
          <Skeleton className="h-10 w-1/2 rounded-2xl" />
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <EmptyState
          icon={CircleSlash}
          tone="danger"
          title="No se pudo abrir la conversación"
          description={error ?? `No se encontró la conversación ${id}.`}
          action={
            <Button variant="outline" onClick={recargar}>
              Reintentar
            </Button>
          }
        />
      </div>
    );
  }

  const { conversacion, lead } = data;
  const info = estadoConversacionInfo(conversacion.estado);
  const nombre = lead?.nombreCliente || formatPhone(conversacion.telefono);
  const nota = notaLocal ?? conversacion.notasInternas ?? "";
  const notaCambiada = notaLocal !== null && notaLocal !== (conversacion.notasInternas ?? "");

  const panel = (
    <PanelDatos
      lead={lead}
      conversacion={conversacion}
      telefono={conversacion.telefono}
      nota={nota}
      onNota={setNotaLocal}
      onGuardarNota={handleGuardarNota}
      guardandoNota={guardandoNota}
      notaCambiada={notaCambiada}
    />
  );

  return (
    <div className="flex min-h-0 flex-1">
      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        {/* Cabecera del chat */}
        <div className="flex items-center gap-3 border-b bg-card px-4 py-3">
          <AvatarInitials nombre={lead?.nombreCliente ?? conversacion.telefono} semilla={conversacion.telefono} className="size-11" />
          <div className="min-w-0 flex-1">
            <p className="truncate font-semibold">{nombre}</p>
            <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
              <StatusBadge label={info.label} variant={info.variant} className="h-5 px-2 text-[0.7rem]" />
              <span className="tabular truncate text-xs text-muted-foreground">{formatPhone(conversacion.telefono)}</span>
            </div>
          </div>
          <Sheet open={panelAbierto} onOpenChange={setPanelAbierto}>
            <SheetTrigger asChild>
              <Button variant="outline" size="icon" aria-label="Ver datos del cliente" className="shrink-0 xl:hidden">
                <Info />
              </Button>
            </SheetTrigger>
            <SheetContent className="w-full overflow-y-auto sm:max-w-sm">
              <SheetHeader className="border-b">
                <SheetTitle>Datos del cliente</SheetTitle>
                <SheetDescription>{nombre}</SheetDescription>
              </SheetHeader>
              {panel}
            </SheetContent>
          </Sheet>
        </div>

        {/* Aviso de escalada: la acción principal es responder; devolverle el
            control a Victoria es la salida cuando ya no hace falta una persona. */}
        {conversacion.estado === "escalada" && (
          <div className="flex flex-col gap-2 border-b bg-status-danger-soft px-4 py-3 text-status-danger-ink sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm">
              <strong className="font-semibold">Victoria pasó este chat a una persona.</strong>{" "}
              <span className="opacity-85">Respóndele al cliente o devuélvele el control.</span>
            </p>
            <Button variant="outline" size="sm" onClick={handleReactivar} disabled={reactivando} className="shrink-0 bg-card text-foreground">
              {reactivando ? <Loader2 className="animate-spin" /> : <Bot />}
              {reactivando ? "Devolviendo…" : "Devolver a Victoria"}
            </Button>
          </div>
        )}

        {/* Estado de la ventana de mensajería de WhatsApp */}
        {conversacion.ventanaAbierta ? (
          <div className="flex items-center gap-2 border-b bg-status-success-soft px-4 py-2 text-xs text-status-success-ink sm:text-sm">
            <Clock className="size-3.5 shrink-0" aria-hidden />
            <span>
              Puedes responder libremente.
              {conversacion.ventanaExpiraEn && (
                <>
                  {" "}
                  Se cierra en <strong className="font-semibold">{tiempoRestante(conversacion.ventanaExpiraEn)}</strong>
                  <span className="hidden sm:inline"> ({formatFechaHora(conversacion.ventanaExpiraEn)})</span>.
                </>
              )}
            </span>
          </div>
        ) : (
          <div className="flex items-center gap-2 border-b bg-status-warning-soft px-4 py-2 text-xs text-status-warning-ink sm:text-sm">
            <Clock className="size-3.5 shrink-0" aria-hidden />
            <span>La ventana de WhatsApp está cerrada: solo puedes escribir cuando el cliente vuelva a hablar.</span>
          </div>
        )}

        {/* Mensajes */}
        <div ref={scrollRef} className="min-h-0 flex-1 space-y-1.5 overflow-y-auto bg-muted/40 px-4 py-4" aria-live="polite">
          {mensajes.length === 0 && <p className="py-10 text-center text-sm text-muted-foreground">Sin mensajes todavía.</p>}
          {mensajes.map((m, i) => {
            const anterior = mensajes[i - 1];
            const nuevoDia = !anterior || etiquetaDia(anterior.creadoEn ?? "") !== etiquetaDia(m.creadoEn ?? "");
            const mostrarAutor = nuevoDia || anterior.rol !== m.rol;
            return (
              <div key={m.id} className={cn(mostrarAutor && !nuevoDia && "pt-2")}>
                {nuevoDia && m.creadoEn && (
                  <div className="my-3 flex justify-center">
                    <span className="rounded-full bg-card px-3 py-1 text-xs font-medium text-muted-foreground shadow-card ring-1 ring-border">
                      {etiquetaDia(m.creadoEn)}
                    </span>
                  </div>
                )}
                <Burbuja m={m} mostrarAutor={mostrarAutor} />
              </div>
            );
          })}
        </div>

        {/* Campo de respuesta, siempre visible abajo */}
        <form onSubmit={handleEnviar} className="flex items-end gap-2 border-t bg-card p-3">
          <Textarea
            value={mensaje}
            rows={1}
            disabled={!conversacion.ventanaAbierta}
            onChange={(e) => setMensaje(e.target.value)}
            onKeyDown={alTeclear}
            aria-label="Escribe una respuesta"
            placeholder={conversacion.ventanaAbierta ? "Escribe una respuesta…" : "Ventana cerrada: no se puede enviar texto libre"}
            className="max-h-36 min-h-10 resize-none py-2.5"
          />
          <Button
            type="submit"
            size="icon-lg"
            disabled={!conversacion.ventanaAbierta || enviando || !mensaje.trim()}
            aria-label="Enviar mensaje"
            className="shrink-0 rounded-full"
          >
            {enviando ? <Loader2 className="animate-spin" /> : <SendHorizontal />}
          </Button>
        </form>
      </div>

      {/* Panel de datos fijo en pantallas muy anchas */}
      <aside className="hidden w-80 shrink-0 overflow-y-auto border-l bg-card xl:block" aria-label="Datos del cliente">
        {panel}
      </aside>
    </div>
  );
}
