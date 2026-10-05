"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { toast } from "sonner";

import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { apiFetch, ApiError } from "@/lib/api";
import { estadoConversacionInfo } from "@/lib/estados";
import { cn } from "@/lib/utils";
import type { ConversacionDetalleCompleto } from "@/types/conversacion";

function Campo({ label, value }: { label: string; value?: ReactNode | null }) {
  return (
    <div className="space-y-0.5">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="text-sm">{value || "Sin definir aún"}</p>
    </div>
  );
}

export default function ConversacionDetallePage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = params.id;

  const [detalle, setDetalle] = useState<ConversacionDetalleCompleto | null>(null);
  const [cargando, setCargando] = useState(true);
  const [mensaje, setMensaje] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [nota, setNota] = useState("");
  const [guardandoNota, setGuardandoNota] = useState(false);
  const [reactivando, setReactivando] = useState(false);

  function cargar() {
    apiFetch<ConversacionDetalleCompleto>(`/conversaciones/${id}`)
      .then((data) => {
        setDetalle(data);
        setNota(data.conversacion.notasInternas ?? "");
      })
      .catch((err: unknown) => {
        toast.error(err instanceof ApiError ? err.message : "No se pudo cargar la conversación.");
      })
      .finally(() => setCargando(false));
  }

  useEffect(() => {
    cargar();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  async function handleEnviar(e: FormEvent) {
    e.preventDefault();
    if (!mensaje.trim() || !detalle) return;

    setEnviando(true);
    const textoEnviado = mensaje;
    const detalleAnterior = detalle;
    // Actualización optimista -- si falla (ej. 409 porque la ventana se
    // cerró justo ahora), cargar() de más abajo revierte con el estado real.
    setDetalle({
      ...detalle,
      mensajes: [
        ...detalle.mensajes,
        { id: Date.now(), rol: "humano", contenido: textoEnviado, tipo: "texto", creadoEn: new Date().toISOString() },
      ],
    });
    setMensaje("");

    try {
      await apiFetch(`/conversaciones/${id}/mensajes`, {
        method: "POST",
        body: JSON.stringify({ contenido: textoEnviado }),
      });
      toast.success("Mensaje enviado.");
    } catch (err) {
      setDetalle(detalleAnterior);
      setMensaje(textoEnviado);
      toast.error(err instanceof ApiError ? err.message : "No se pudo enviar el mensaje.");
      cargar();
    } finally {
      setEnviando(false);
    }
  }

  async function handleGuardarNota() {
    setGuardandoNota(true);
    try {
      await apiFetch(`/conversaciones/${id}/notas`, {
        method: "PATCH",
        body: JSON.stringify({ notasInternas: nota }),
      });
      toast.success("Nota guardada.");
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
      cargar();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo reactivar la conversación.");
    } finally {
      setReactivando(false);
    }
  }

  if (cargando) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-96 w-full" />
      </div>
    );
  }

  if (!detalle) {
    return (
      <div className="flex flex-col items-center justify-center gap-2 py-24 text-center text-muted-foreground">
        <p>No se encontró la conversación {id}.</p>
        <Button variant="outline" onClick={() => router.push("/conversaciones")}>
          Volver a Conversaciones
        </Button>
      </div>
    );
  }

  const { conversacion, lead, mensajes } = detalle;
  const info = estadoConversacionInfo(conversacion.estado);

  const puedeCrearPedido = Boolean(lead?.nombreCliente && lead?.direccion && lead?.productoNombre) && lead?.estado !== "despachado";

  const paramsPedido = new URLSearchParams();
  if (lead?.nombreCliente) paramsPedido.set("nombreCliente", lead.nombreCliente);
  if (conversacion.telefono) paramsPedido.set("telefono", conversacion.telefono);
  if (lead?.direccion) paramsPedido.set("direccion", lead.direccion);
  if (lead?.canton) paramsPedido.set("canton", lead.canton);
  if (lead?.provincia) paramsPedido.set("provincia", lead.provincia);
  if (lead?.productoSku) paramsPedido.set("productoSku", lead.productoSku);
  if (lead?.productoNombre) paramsPedido.set("productoNombre", lead.productoNombre);
  if (lead?.total) paramsPedido.set("total", lead.total);

  return (
    <div className="flex flex-col gap-4 lg:flex-row">
      <div className="flex flex-1 flex-col gap-4">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-semibold">{lead?.nombreCliente || conversacion.telefono}</h2>
            <StatusBadge label={info.label} variant={info.variant} />
          </div>
          {conversacion.estado === "escalada" && (
            <Button variant="outline" onClick={handleReactivar} disabled={reactivando}>
              {reactivando ? "Devolviendo…" : "Devolver el control a Victoria"}
            </Button>
          )}
        </div>

        {conversacion.ventanaAbierta ? (
          <div className="rounded-md border border-status-success/30 bg-status-success/5 px-4 py-2 text-sm text-status-success">
            Ventana abierta — puedes responder libremente.
            {conversacion.ventanaExpiraEn && (
              <> Se cierra el {new Date(conversacion.ventanaExpiraEn).toLocaleString("es-EC")}.</>
            )}
          </div>
        ) : (
          <div className="rounded-md border border-status-warning/30 bg-status-warning/5 px-4 py-2 text-sm text-status-warning">
            La ventana de mensajería está cerrada. No se puede enviar texto libre hasta que el cliente vuelva a
            escribir.
          </div>
        )}

        <Card className="flex-1">
          <CardHeader>
            <CardTitle className="text-sm">Transcripción</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            {mensajes.length === 0 && <p className="text-sm text-muted-foreground">Sin mensajes todavía.</p>}
            {mensajes.map((m) => (
              <div key={m.id} className={cn("flex flex-col gap-0.5", m.rol === "cliente" ? "items-start" : "items-end")}>
                <span className="text-xs text-muted-foreground">
                  {m.rol === "cliente" ? "Cliente" : m.rol === "bot" ? "Victoria" : "Tú"}
                </span>
                <p
                  className={cn(
                    "max-w-md rounded-lg px-3 py-2 text-sm whitespace-pre-wrap",
                    m.rol === "cliente" ? "bg-muted" : "bg-primary text-primary-foreground",
                  )}
                >
                  {m.contenido}
                </p>
              </div>
            ))}
          </CardContent>
        </Card>

        <form onSubmit={handleEnviar} className="flex gap-2">
          <Input
            placeholder={conversacion.ventanaAbierta ? "Escribe una respuesta…" : "Ventana cerrada"}
            value={mensaje}
            disabled={!conversacion.ventanaAbierta || enviando}
            onChange={(e) => setMensaje(e.target.value)}
          />
          <Button type="submit" disabled={!conversacion.ventanaAbierta || enviando || !mensaje.trim()}>
            Enviar
          </Button>
        </form>
      </div>

      <div className="flex w-full flex-col gap-4 lg:w-80 lg:shrink-0">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Datos del cliente</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <Campo label="Nombre" value={lead?.nombreCliente} />
            <Campo label="Dirección" value={lead?.direccion} />
            <Campo label="Cantón" value={lead?.canton} />
            <Campo label="Provincia" value={lead?.provincia} />
            <Separator />
            <Campo label="Producto" value={lead?.productoNombre} />
            <Campo label="Variante" value={lead?.productoVariante} />
            <Campo label="Total" value={lead?.total ? `$${lead.total}` : undefined} />
            <Campo label="Método de pago" value={lead?.metodoPago} />
            <Campo label="Estado del lead" value={lead?.estado} />
            {conversacion.idAnuncio && <Campo label="Vino de anuncio" value={conversacion.idAnuncio} />}

            {lead?.idPedidoRocketfy && lead?.idPedidoLocal && (
              <Link href={`/pedidos/${lead.idPedidoLocal}`} className="text-sm text-primary underline underline-offset-2">
                Ver pedido {lead.idPedidoLocal}
              </Link>
            )}

            {puedeCrearPedido && (
              <Button variant="outline" asChild className="mt-2">
                <Link href={`/pedidos/nuevo?${paramsPedido.toString()}`}>Crear pedido manual con estos datos</Link>
              </Button>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Notas internas</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-2">
            <p className="text-xs text-muted-foreground">Privadas — nunca se le muestran al cliente ni a Victoria.</p>
            <Textarea value={nota} onChange={(e) => setNota(e.target.value)} rows={4} />
            <Button size="sm" onClick={handleGuardarNota} disabled={guardandoNota}>
              {guardandoNota ? "Guardando…" : "Guardar nota"}
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
