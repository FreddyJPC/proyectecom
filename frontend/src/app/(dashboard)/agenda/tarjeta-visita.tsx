"use client";

import { CalendarCheck, ChevronDown, Clock, Loader2, MessageCircle, Phone, Send, UserRound, Users } from "lucide-react";
import Link from "next/link";
import { useState, type FormEvent, type ReactNode } from "react";
import { toast } from "sonner";

import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { apiFetch, ApiError } from "@/lib/api";
import { estadoVisitaInfo } from "@/lib/estados";
import { formatPhone, tiempoRestante } from "@/lib/format";
import { fechaEcuador, hoyEcuador, horaEcuador, instanteEcuador, partesEcuador } from "@/lib/inmuebles";
import type { EstadoVisita, Visita } from "@/types/inmueble";

/** Lo que se puede marcar desde cada estado (confirmar va aparte porque pide día y hora). */
const MARCAS: Partial<Record<EstadoVisita, { estado: EstadoVisita; label: string }[]>> = {
  solicitada: [{ estado: "cancelada", label: "Cancelar" }],
  confirmada: [
    { estado: "realizada", label: "Se realizó" },
    { estado: "no_asistio", label: "No asistió" },
    { estado: "cancelada", label: "Cancelar" },
  ],
  realizada: [{ estado: "no_asistio", label: "Corregir: no asistió" }],
  no_asistio: [{ estado: "realizada", label: "Corregir: se realizó" }],
  cancelada: [{ estado: "solicitada", label: "Volver a «por confirmar»" }],
};

/** Una visita de la agenda con sus acciones. */
export function TarjetaVisita({ visita, onCambio }: { visita: Visita; onCambio: () => void }) {
  const [trabajando, setTrabajando] = useState(false);

  async function marcar(estado: EstadoVisita, motivo?: string) {
    setTrabajando(true);
    try {
      await apiFetch(`/visitas/${visita.id}/estado`, { method: "PUT", body: JSON.stringify({ estado, motivo: motivo ?? null }) });
      toast.success(`Visita marcada: ${estadoVisitaInfo(estado).label.toLowerCase()}.`);
      onCambio();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo cambiar la visita.");
    } finally {
      setTrabajando(false);
    }
  }

  const marcas = MARCAS[visita.estado] ?? [];
  const puedeConfirmar = visita.estado === "solicitada" || visita.estado === "confirmada" || visita.estado === "cancelada";

  return (
    <article className="flex h-full flex-col gap-3 rounded-xl bg-card p-4 shadow-card ring-1 ring-border">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 className="font-medium">{visita.nombreCliente ?? "Cliente sin nombre"}</h3>
          <p className="text-xs text-muted-foreground">
            <Link href={`/inmuebles/${visita.inmuebleId}`} className="underline-offset-2 hover:underline">
              {visita.inmuebleTitulo}
            </Link>
          </p>
        </div>
        <StatusBadge {...estadoVisitaInfo(visita.estado)} />
      </div>

      <dl className="grid gap-1.5 text-sm">
        {visita.fechaHora ? (
          <Fila icono={<CalendarCheck className="size-4" aria-hidden />} etiqueta="Fecha">
            <span className="font-medium first-letter:uppercase">
              {fechaEcuador(visita.fechaHora)}, {horaEcuador(visita.fechaHora)}
            </span>
          </Fila>
        ) : null}
        {visita.preferenciaCliente && (
          <Fila icono={<Clock className="size-4" aria-hidden />} etiqueta="Pidió">
            «{visita.preferenciaCliente}»
          </Fila>
        )}
        {visita.telefono && (
          <Fila icono={<Phone className="size-4" aria-hidden />} etiqueta="Teléfono">
            <a href={`tel:+${visita.telefono.replace(/\D/g, "")}`} className="underline-offset-2 hover:underline">
              {formatPhone(visita.telefono)}
            </a>
          </Fila>
        )}
        {visita.personas && (
          <Fila icono={<Users className="size-4" aria-hidden />} etiqueta="Personas">
            {visita.personas}
          </Fila>
        )}
        {visita.encargado && (
          <Fila icono={<UserRound className="size-4" aria-hidden />} etiqueta="La enseña">
            {visita.encargado}
          </Fila>
        )}
      </dl>
      {visita.notas && <p className="rounded-lg bg-muted px-3 py-2 text-sm">{visita.notas}</p>}
      {visita.motivoCancelacion && <p className="text-xs text-muted-foreground">Motivo: {visita.motivoCancelacion}</p>}
      {visita.estado === "confirmada" && (
        <p className="text-xs text-muted-foreground">
          {visita.avisadoClienteEn ? "Ya le avisaste al cliente." : "Todavía no le avisas al cliente."}
          {visita.conversacionId && !visita.ventanaAbierta ? " WhatsApp ya no deja escribirle (pasaron 24 h): llámalo." : ""}
        </p>
      )}

      <div className="mt-auto flex flex-wrap items-center gap-2">
        {puedeConfirmar && (
          <ConfirmarVisitaDialog visita={visita} onListo={onCambio}>
            <Button size="sm" variant={visita.estado === "solicitada" ? "default" : "outline"}>
              <CalendarCheck /> {visita.estado === "confirmada" ? "Reprogramar" : "Confirmar"}
            </Button>
          </ConfirmarVisitaDialog>
        )}
        {visita.estado === "confirmada" && visita.conversacionId && (
          <AvisarClienteDialog visita={visita} onListo={onCambio}>
            <Button size="sm" variant={visita.avisadoClienteEn ? "outline" : "default"} disabled={!visita.ventanaAbierta}>
              <Send /> Avisar al cliente
            </Button>
          </AvisarClienteDialog>
        )}
        {visita.conversacionId && (
          <Button size="sm" variant="ghost" asChild>
            <Link href={`/conversaciones/${visita.conversacionId}`}>
              <MessageCircle /> Chat
            </Link>
          </Button>
        )}
        {marcas.length > 0 && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button size="sm" variant="ghost" disabled={trabajando}>
                {trabajando ? <Loader2 className="animate-spin" /> : null} Marcar <ChevronDown />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              {marcas.map((m) =>
                m.estado === "cancelada" ? (
                  <CancelarVisitaDialog key={m.estado} onCancelar={(motivo) => void marcar("cancelada", motivo)}>
                    <DropdownMenuItem onSelect={(e) => e.preventDefault()}>{m.label}</DropdownMenuItem>
                  </CancelarVisitaDialog>
                ) : (
                  <DropdownMenuItem key={m.estado} onSelect={() => void marcar(m.estado)}>
                    {m.label}
                  </DropdownMenuItem>
                ),
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        )}
      </div>
    </article>
  );
}

function Fila({ icono, etiqueta, children }: { icono: ReactNode; etiqueta: string; children: ReactNode }) {
  return (
    <div className="flex items-start gap-2">
      <dt className="mt-0.5 text-muted-foreground">
        {icono}
        <span className="sr-only">{etiqueta}</span>
      </dt>
      <dd className="min-w-0">{children}</dd>
    </div>
  );
}

/** Confirmar (o reprogramar) con día y hora de Ecuador. No le avisa al cliente: eso va aparte, para revisar el mensaje. */
function ConfirmarVisitaDialog({ visita, onListo, children }: { visita: Visita; onListo: () => void; children: ReactNode }) {
  const [abierto, setAbierto] = useState(false);
  const previa = partesEcuador(visita.fechaHora);
  const [dia, setDia] = useState(previa.dia || hoyEcuador());
  const [hora, setHora] = useState(previa.hora || "10:00");
  const [encargado, setEncargado] = useState(visita.encargado ?? "");
  const [notas, setNotas] = useState(visita.notas ?? "");
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function guardar(e: FormEvent) {
    e.preventDefault();
    setGuardando(true);
    setError(null);
    try {
      await apiFetch(`/visitas/${visita.id}/confirmar`, {
        method: "PUT",
        body: JSON.stringify({ fechaHora: instanteEcuador(dia, hora), encargado: encargado.trim() || null, notas: notas.trim() || null }),
      });
      toast.success("Visita confirmada. Ahora puedes avisarle al cliente.");
      setAbierto(false);
      onListo();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo confirmar.");
    } finally {
      setGuardando(false);
    }
  }

  return (
    <Dialog open={abierto} onOpenChange={setAbierto}>
      <DialogTrigger asChild>{children}</DialogTrigger>
      <DialogContent>
        <form onSubmit={guardar} className="space-y-4">
          <DialogHeader>
            <DialogTitle>{visita.estado === "confirmada" ? "Reprogramar visita" : "Confirmar visita"}</DialogTitle>
            <DialogDescription>
              {visita.preferenciaCliente ? `El cliente pidió: «${visita.preferenciaCliente}».` : "Día y hora en hora de Ecuador."}
            </DialogDescription>
          </DialogHeader>
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-1.5">
              <Label htmlFor={`dia-${visita.id}`}>Día</Label>
              <Input id={`dia-${visita.id}`} type="date" value={dia} onChange={(e) => setDia(e.target.value)} required disabled={guardando} />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor={`hora-${visita.id}`}>Hora</Label>
              <Input id={`hora-${visita.id}`} type="time" value={hora} onChange={(e) => setHora(e.target.value)} required disabled={guardando} />
            </div>
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor={`encargado-${visita.id}`}>Quién la enseña</Label>
            <Input id={`encargado-${visita.id}`} value={encargado} onChange={(e) => setEncargado(e.target.value)} disabled={guardando} />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor={`notas-${visita.id}`}>
              Notas <span className="font-normal text-muted-foreground">(opcional)</span>
            </Label>
            <Textarea id={`notas-${visita.id}`} value={notas} onChange={(e) => setNotas(e.target.value)} rows={2} disabled={guardando} />
          </div>
          {error && (
            <p role="alert" className="text-sm font-medium text-status-danger-ink">
              {error}
            </p>
          )}
          <DialogFooter>
            <DialogClose asChild>
              <Button type="button" variant="outline" disabled={guardando}>
                Cancelar
              </Button>
            </DialogClose>
            <Button type="submit" disabled={guardando || !dia || !hora}>
              {guardando && <Loader2 className="animate-spin" />} Confirmar
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

/** Le manda al cliente la confirmación por WhatsApp. El texto sale del parámetro «Mensaje de visita confirmada» y se puede
 * ajustar antes de enviar. */
function AvisarClienteDialog({ visita, onListo, children }: { visita: Visita; onListo: () => void; children: ReactNode }) {
  const [abierto, setAbierto] = useState(false);
  const [texto, setTexto] = useState("");
  const [cargando, setCargando] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function alAbrir(valor: boolean) {
    setAbierto(valor);
    if (!valor) return;
    setError(null);
    setCargando(true);
    try {
      const r = await apiFetch<{ texto: string }>(`/visitas/${visita.id}/aviso`);
      setTexto(r.texto);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo preparar el mensaje.");
    } finally {
      setCargando(false);
    }
  }

  async function enviar(e: FormEvent) {
    e.preventDefault();
    setEnviando(true);
    setError(null);
    try {
      await apiFetch(`/visitas/${visita.id}/avisar`, { method: "POST", body: JSON.stringify({ texto: texto.trim() }) });
      toast.success("Le avisaste al cliente por WhatsApp.");
      setAbierto(false);
      onListo();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo enviar.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <Dialog open={abierto} onOpenChange={(v) => void alAbrir(v)}>
      <DialogTrigger asChild>{children}</DialogTrigger>
      <DialogContent>
        <form onSubmit={enviar} className="space-y-4">
          <DialogHeader>
            <DialogTitle>Avisar al cliente</DialogTitle>
            <DialogDescription>
              Se envía por WhatsApp{visita.ventanaExpiraEn ? ` (la ventana se cierra en ${tiempoRestante(visita.ventanaExpiraEn)})` : ""}.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-1.5">
            <Label htmlFor={`aviso-${visita.id}`}>Mensaje</Label>
            <Textarea id={`aviso-${visita.id}`} value={texto} onChange={(e) => setTexto(e.target.value)} rows={5} disabled={cargando || enviando} />
          </div>
          {error && (
            <p role="alert" className="text-sm font-medium text-status-danger-ink">
              {error}
            </p>
          )}
          <DialogFooter>
            <DialogClose asChild>
              <Button type="button" variant="outline" disabled={enviando}>
                Cancelar
              </Button>
            </DialogClose>
            <Button type="submit" disabled={cargando || enviando || !texto.trim()}>
              {enviando ? <Loader2 className="animate-spin" /> : <Send />} Enviar
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function CancelarVisitaDialog({ onCancelar, children }: { onCancelar: (motivo: string) => void; children: ReactNode }) {
  const [abierto, setAbierto] = useState(false);
  const [motivo, setMotivo] = useState("");
  return (
    <Dialog open={abierto} onOpenChange={setAbierto}>
      <DialogTrigger asChild>{children}</DialogTrigger>
      <DialogContent>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            onCancelar(motivo.trim());
            setAbierto(false);
          }}
          className="space-y-4"
        >
          <DialogHeader>
            <DialogTitle>Cancelar visita</DialogTitle>
            <DialogDescription>El cliente no recibe ningún mensaje automático.</DialogDescription>
          </DialogHeader>
          <div className="grid gap-1.5">
            <Label htmlFor="motivo-cancelacion">
              Motivo <span className="font-normal text-muted-foreground">(opcional)</span>
            </Label>
            <Input id="motivo-cancelacion" value={motivo} onChange={(e) => setMotivo(e.target.value)} placeholder="Ya no le interesa…" />
          </div>
          <DialogFooter>
            <DialogClose asChild>
              <Button type="button" variant="outline">
                Volver
              </Button>
            </DialogClose>
            <Button type="submit" variant="destructive">
              Cancelar visita
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
