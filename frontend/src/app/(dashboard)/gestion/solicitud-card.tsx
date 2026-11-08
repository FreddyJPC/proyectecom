"use client";

import { ExternalLink, Loader2, MessageCircle } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { apiFetch, ApiError } from "@/lib/api";
import { tipoSolicitudInfo } from "@/lib/estados";
import { formatFechaHora, formatMoney, formatPhone, tiempoRelativo } from "@/lib/format";
import type { Solicitud } from "@/types/gestion";

function Dato({ etiqueta, children, ancho }: { etiqueta: string; children?: React.ReactNode; ancho?: boolean }) {
  if (children === undefined || children === null || children === "") return null;
  return (
    <div className={`min-w-0 space-y-0.5${ancho ? " col-span-2" : ""}`}>
      <dt className="text-xs text-muted-foreground">{etiqueta}</dt>
      <dd className="break-words text-sm">{children}</dd>
    </div>
  );
}

const PAGO: Record<string, string> = { contraentrega: "Contraentrega", transferencia: "Transferencia" };

/** Un aviso para el dueño, con lo necesario para actuar sin abrir otra pantalla. */
export function SolicitudCard({ solicitud: s, onAtendida }: { solicitud: Solicitud; onAtendida: () => void }) {
  const tipo = tipoSolicitudInfo(s.tipo);
  const [abierto, setAbierto] = useState(false);
  const [nota, setNota] = useState("");
  const [guardando, setGuardando] = useState(false);
  const pendiente = s.estado === "pendiente";
  const nombre = s.nombreCliente || formatPhone(s.telefono);
  const destino = [s.direccion, s.canton, s.provincia].filter(Boolean).join(", ");
  const producto = s.producto ? `${s.cantidad && s.cantidad > 1 ? `${s.cantidad} × ` : ""}${s.producto}${s.variante ? ` (${s.variante})` : ""}` : null;
  // Abre el chat de WhatsApp del cliente en el teléfono o en WhatsApp Web (solo dígitos).
  const enlaceWhatsApp = s.telefono ? `https://wa.me/${s.telefono.replace(/\D/g, "")}` : null;

  async function marcarAtendida() {
    setGuardando(true);
    try {
      await apiFetch<Solicitud>(`/gestion/${s.id}/atender`, { method: "POST", body: JSON.stringify({ nota: nota.trim() || null }) });
      toast.success("Marcada como atendida.");
      setAbierto(false);
      onAtendida();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo marcar como atendida.");
    } finally {
      setGuardando(false);
    }
  }

  return (
    <Card className="gap-0 py-0">
      <div className="space-y-3 p-4 sm:p-5">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge label={tipo.label} variant={tipo.variant} />
              {s.proveedor && <span className="text-xs text-muted-foreground">{s.proveedor}</span>}
            </div>
            <p className="mt-1.5 truncate text-base font-semibold">{nombre}</p>
            <p className="tabular text-sm text-muted-foreground">{formatPhone(s.telefono)}</p>
          </div>
          <p className="text-xs text-muted-foreground" title={formatFechaHora(s.creadaEn)}>
            {tiempoRelativo(s.creadaEn)}
          </p>
        </div>

        {s.detalle && <p className="rounded-lg bg-muted/60 p-3 text-sm">{s.detalle}</p>}

        {(producto || destino || s.entrega || s.metodoPago || s.total) && (
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2.5">
            <Dato ancho etiqueta="Producto">{producto}</Dato>
            <Dato ancho etiqueta="Enviar a">{destino}</Dato>
            <Dato etiqueta="Entrega">{s.entrega}</Dato>
            <Dato etiqueta="Pago">{s.metodoPago ? PAGO[s.metodoPago] ?? s.metodoPago : null}</Dato>
            <Dato etiqueta="Total a cobrar">{s.total ? <span className="tabular font-semibold">{formatMoney(s.total)}</span> : null}</Dato>
          </dl>
        )}

        {s.metodoPago === "transferencia" && s.tienePedido && pendiente && (
          <p className="rounded-lg bg-status-warning-soft p-3 text-sm text-status-warning-ink">
            Pagará por transferencia: pásale tú los datos de la cuenta y verifica el comprobante antes de enviar.
          </p>
        )}

        {!pendiente && (
          <p className="text-xs text-muted-foreground">
            Atendida {s.atendidaPor ? `por ${s.atendidaPor} ` : ""}el {formatFechaHora(s.atendidaEn)}.{s.notaAtencion ? ` Nota: ${s.notaAtencion}` : ""}
          </p>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-2 border-t p-3 sm:px-5">
        <Button asChild variant="outline" size="sm">
          <Link href={`/conversaciones/${s.conversacionId}`}>
            <MessageCircle /> Ver conversación
          </Link>
        </Button>
        {enlaceWhatsApp && (
          <Button asChild variant="outline" size="sm">
            <a href={enlaceWhatsApp} target="_blank" rel="noopener noreferrer">
              <ExternalLink /> Abrir en WhatsApp
            </a>
          </Button>
        )}
        {pendiente && (
          <Dialog open={abierto} onOpenChange={setAbierto}>
            <DialogTrigger asChild>
              <Button size="sm" className="ml-auto">
                Marcar como atendida
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>¿Marcar como atendida?</DialogTitle>
                <DialogDescription>
                  {s.tienePedido
                    ? "El pedido pasa a «gestionado» y deja de aparecer como pendiente. Si el cliente vuelve a escribir, lo recibirá el mensaje de cliente con pedido previo."
                    : "Dejará de aparecer como pendiente. Si la conversación estaba en tus manos, vuelve a quedar activa."}
                </DialogDescription>
              </DialogHeader>
              <div className="grid gap-1.5">
                <Label htmlFor={`nota-${s.id}`}>
                  Nota <span className="font-normal text-muted-foreground">(opcional)</span>
                </Label>
                <Textarea id={`nota-${s.id}`} rows={3} maxLength={500} value={nota} onChange={(e) => setNota(e.target.value)} placeholder="Por ejemplo: enviado con la guía 12345" />
              </div>
              <DialogFooter>
                <DialogClose asChild>
                  <Button type="button" variant="outline" disabled={guardando}>
                    Cancelar
                  </Button>
                </DialogClose>
                <Button type="button" onClick={marcarAtendida} disabled={guardando}>
                  {guardando && <Loader2 className="animate-spin" />}
                  Sí, marcar como atendida
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        )}
      </div>
    </Card>
  );
}
