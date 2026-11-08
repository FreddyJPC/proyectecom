"use client";

import { Ban, CircleDollarSign, ExternalLink, Loader2, MessageCircle, Undo2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { apiFetch, ApiError } from "@/lib/api";
import { estadoDeCobro, tipoSolicitudInfo } from "@/lib/estados";
import { formatFechaHora, formatMoney, formatPhone, tiempoRelativo } from "@/lib/format";
import type { Solicitud, VentaAccionada } from "@/types/gestion";

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

type Accion = "atender" | "cobrar" | "deshacer" | "cancelar";

/** Todo lo que cambia de un cuadro de confirmación a otro: textos, el campo de nota y la llamada al servidor. */
type Configuracion = {
  titulo: string;
  descripcion: string;
  campo?: { etiqueta: string; placeholder: string };
  boton: string;
  peligrosa?: boolean;
};

/** Un aviso para el dueño, con lo necesario para actuar sin abrir otra pantalla: gestionarlo, cobrarlo o cancelarlo. */
export function SolicitudCard({ solicitud: s, onCambio }: { solicitud: Solicitud; onCambio: () => void }) {
  const tipo = tipoSolicitudInfo(s.tipo);
  const cobro = estadoDeCobro(s);
  const [accion, setAccion] = useState<Accion | null>(null);
  // La última acción mostrada: el cuadro conserva su texto mientras se desvanece (accion ya vuelve a null al cerrar).
  const [ultimaAccion, setUltimaAccion] = useState<Accion>("atender");
  const [texto, setTexto] = useState("");
  const [guardando, setGuardando] = useState(false);
  const pendiente = s.estado === "pendiente";
  const nombre = s.nombreCliente || formatPhone(s.telefono);
  const destino = [s.direccion, s.canton, s.provincia].filter(Boolean).join(", ");
  const producto = s.producto ? `${s.cantidad && s.cantidad > 1 ? `${s.cantidad} × ` : ""}${s.producto}${s.variante ? ` (${s.variante})` : ""}` : null;
  // Abre el chat de WhatsApp del cliente en el teléfono o en WhatsApp Web (solo dígitos).
  const enlaceWhatsApp = s.telefono ? `https://wa.me/${s.telefono.replace(/\D/g, "")}` : null;
  const cancelada = s.ventaEstado === "cancelada";

  const configuracion: Record<Accion, Configuracion> = {
    atender: {
      titulo: "¿Marcar como atendida?",
      descripcion: s.tienePedido
        ? "El pedido pasa a «gestionado» y deja de aparecer como pendiente. Si el cliente vuelve a escribir, lo recibirá el mensaje de cliente con pedido previo."
        : "Dejará de aparecer como pendiente. Si la conversación estaba en tus manos, vuelve a quedar activa.",
      campo: { etiqueta: "Nota", placeholder: "Por ejemplo: enviado con la guía 12345" },
      boton: "Sí, marcar como atendida",
    },
    cobrar: {
      titulo: "¿Ya cobraste esta venta?",
      descripcion: `Confirma que el dinero ya llegó (${s.metodoPago === "transferencia" ? "transferencia verificada" : "cobro al entregar"}). Queda guardado cuándo y quién lo marcó, y puedes deshacerlo si fue un error.`,
      campo: { etiqueta: "Nota", placeholder: "Por ejemplo: transferencia del Banco Pichincha, comprobante 123456" },
      boton: "Sí, ya la cobré",
    },
    deshacer: {
      titulo: "¿Deshacer el cobro?",
      descripcion: "La venta vuelve a figurar como «por cobrar». Úsalo si la marcaste por error o si tienes que devolver el dinero.",
      boton: "Sí, deshacer el cobro",
    },
    cancelar: {
      titulo: "¿Cancelar esta venta?",
      descripcion:
        "La venta queda cancelada y deja de contar como venta. Si el producto lleva control de stock, las unidades que se descontaron vuelven al inventario. Esta acción no se puede deshacer.",
      campo: { etiqueta: "Motivo", placeholder: "Por ejemplo: el cliente se arrepintió" },
      boton: "Sí, cancelar la venta",
      peligrosa: true,
    },
  };

  function abrir(a: Accion) {
    setTexto("");
    setUltimaAccion(a);
    setAccion(a);
  }

  async function confirmar() {
    if (!accion) return;
    const limpio = texto.trim() || null;
    setGuardando(true);
    try {
      if (accion === "atender") {
        await apiFetch<Solicitud>(`/gestion/${s.id}/atender`, { method: "POST", body: JSON.stringify({ nota: limpio }) });
        toast.success("Marcada como atendida.");
      } else if (accion === "cobrar") {
        await apiFetch<VentaAccionada>(`/ventas/${s.ventaId}/cobrar`, { method: "POST", body: JSON.stringify({ nota: limpio }) });
        toast.success("Venta marcada como cobrada.");
      } else if (accion === "deshacer") {
        await apiFetch<VentaAccionada>(`/ventas/${s.ventaId}/deshacer-cobro`, { method: "POST" });
        toast.success("Cobro deshecho: la venta vuelve a figurar como por cobrar.");
      } else {
        const venta = await apiFetch<VentaAccionada>(`/ventas/${s.ventaId}/cancelar`, { method: "POST", body: JSON.stringify({ motivo: limpio }) });
        const devueltas = venta.stockDevuelto > 0 ? `Se devolvieron ${venta.stockDevuelto} ${venta.stockDevuelto === 1 ? "unidad" : "unidades"} al stock.` : "No había unidades que devolver al stock.";
        toast.success("Venta cancelada.", {
          description: venta.productoSigueAgotado ? `${devueltas} El producto sigue en «Agotado»: reanúdalo en Catálogo para volver a ofrecerlo.` : devueltas,
        });
      }
      setAccion(null);
      onCambio();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo completar la acción.");
    } finally {
      setGuardando(false);
    }
  }

  const actual = configuracion[ultimaAccion];

  return (
    <Card className="gap-0 py-0">
      <div className="space-y-3 p-4 sm:p-5">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge label={tipo.label} variant={tipo.variant} />
              {cobro && <StatusBadge label={cobro.label} variant={cobro.variant} />}
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

        {s.metodoPago === "transferencia" && s.tienePedido && !cancelada && !s.ventaCobradaEn && (
          <p className="rounded-lg bg-status-warning-soft p-3 text-sm text-status-warning-ink">
            Pagará por transferencia: pásale tú los datos de la cuenta y verifica el comprobante antes de enviar.
          </p>
        )}

        {cancelada && (
          <p className="rounded-lg bg-status-danger-soft p-3 text-sm text-status-danger-ink">
            Venta cancelada el {formatFechaHora(s.ventaCanceladaEn)}
            {s.ventaCanceladaPor ? ` por ${s.ventaCanceladaPor}` : ""}.{s.ventaMotivoCancelacion ? ` Motivo: ${s.ventaMotivoCancelacion}` : ""}
          </p>
        )}

        {s.ventaCobradaEn && !cancelada && (
          <p className="rounded-lg bg-status-success-soft p-3 text-sm text-status-success-ink">
            Cobrada el {formatFechaHora(s.ventaCobradaEn)}
            {s.ventaCobradaPor ? ` por ${s.ventaCobradaPor}` : ""}.{s.ventaNotaCobro ? ` Nota: ${s.ventaNotaCobro.replace(/[.\s]+$/, "")}.` : ""} Para cancelarla, primero deshaz el cobro (y devuelve el dinero al cliente).
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
        {s.puedeCobrar && (
          <Button type="button" variant="outline" size="sm" onClick={() => abrir("cobrar")}>
            <CircleDollarSign /> Marcar cobrada
          </Button>
        )}
        {s.puedeDeshacerCobro && (
          <Button type="button" variant="ghost" size="sm" onClick={() => abrir("deshacer")}>
            <Undo2 /> Deshacer cobro
          </Button>
        )}
        {s.puedeCancelar && (
          <Button type="button" variant="destructive" size="sm" onClick={() => abrir("cancelar")}>
            <Ban /> Cancelar venta
          </Button>
        )}
        {pendiente && (
          <Button type="button" size="sm" className="ml-auto" onClick={() => abrir("atender")}>
            Marcar como atendida
          </Button>
        )}
      </div>

      <Dialog open={accion !== null} onOpenChange={(abierto) => !abierto && !guardando && setAccion(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{actual.titulo}</DialogTitle>
            <DialogDescription>{actual.descripcion}</DialogDescription>
          </DialogHeader>
          {actual.campo && (
            <div className="grid gap-1.5">
              <Label htmlFor={`texto-${s.id}`}>
                {actual.campo.etiqueta} <span className="font-normal text-muted-foreground">(opcional)</span>
              </Label>
              <Textarea id={`texto-${s.id}`} rows={3} maxLength={500} value={texto} onChange={(e) => setTexto(e.target.value)} placeholder={actual.campo.placeholder} />
            </div>
          )}
          <DialogFooter>
            <DialogClose asChild>
              <Button type="button" variant="outline" disabled={guardando}>
                Volver
              </Button>
            </DialogClose>
            {/* El rojo «destructive» no llega a contraste AA sobre el fondo del cuadro en modo oscuro: aquí va el par
                suave+tinta de estado, que sí lo garantiza (el mismo de las insignias y los avisos). */}
            <Button
              type="button"
              variant={actual.peligrosa ? "outline" : "default"}
              className={actual.peligrosa ? "border-status-danger/40 bg-status-danger-soft text-status-danger-ink hover:bg-status-danger-soft/70 hover:text-status-danger-ink dark:bg-status-danger-soft dark:hover:bg-status-danger-soft/70" : undefined}
              onClick={confirmar}
              disabled={guardando}
            >
              {guardando && <Loader2 className="animate-spin" />}
              {actual.boton}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
