"use client";

import { CircleSlash, Loader2, MapPin, MessageCircle, Pencil, Phone, ReceiptText, TriangleAlert, Truck, XCircle } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState, type FormEvent, type ReactNode } from "react";
import { toast } from "sonner";

import { EmptyState } from "@/components/app/empty-state";
import { PageHeader } from "@/components/app/page-header";
import { StatusBadge } from "@/components/status-badge";
import { UbicacionSelector } from "@/components/ubicacion-selector";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/use-api";
import { apiFetch, ApiError } from "@/lib/api";
import { estadoLocalInfo, rocketfyStatusInfo } from "@/lib/estados";
import { formatFechaHora, formatMoney, formatPhone } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { ModificarPedidoInput, PedidoDetalle } from "@/types/pedido";

function Dato({ label, children, className }: { label: string; children?: ReactNode; className?: string }) {
  const vacio = children === undefined || children === null || children === "";
  return (
    <div className={cn("space-y-0.5", className)}>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className={cn("text-sm", vacio && "text-muted-foreground/70")}>{vacio ? "—" : children}</dd>
    </div>
  );
}

function Bloque({ icon: Icon, titulo, children, className }: { icon: typeof MapPin; titulo: string; children: ReactNode; className?: string }) {
  return (
    <Card className={cn("gap-0 py-0", className)}>
      <div className="flex items-center gap-2 border-b px-4 py-3.5 sm:px-5">
        <Icon className="size-4 text-muted-foreground" aria-hidden />
        <h2 className="text-sm font-semibold">{titulo}</h2>
      </div>
      <div className="p-4 sm:p-5">{children}</div>
    </Card>
  );
}

export default function PedidoDetallePage() {
  const { idLocal } = useParams<{ idLocal: string }>();
  const { data: pedido, error, cargando, recargar } = useApi<PedidoDetalle>(`/pedidos/${idLocal}`);

  const [rechazando, setRechazando] = useState(false);
  const [guardando, setGuardando] = useState(false);
  const [dialogAbierto, setDialogAbierto] = useState(false);
  const [form, setForm] = useState<ModificarPedidoInput>({});

  function abrirDialogo(abierto: boolean) {
    if (abierto && pedido) {
      setForm({
        nombreCliente: pedido.nombreCliente,
        telefono: pedido.telefono,
        direccion: pedido.direccion,
        direccion2: pedido.direccion2,
        canton: pedido.canton,
        provincia: pedido.provincia,
        codigoPostal: pedido.codigoPostal ?? "",
      });
    }
    setDialogAbierto(abierto);
  }

  async function handleRechazar() {
    setRechazando(true);
    try {
      await apiFetch(`/pedidos/${idLocal}/rechazar`, { method: "POST" });
      toast.success("Pedido rechazado.");
      recargar();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo rechazar el pedido.");
    } finally {
      setRechazando(false);
    }
  }

  async function handleModificar(e: FormEvent) {
    e.preventDefault();
    setGuardando(true);
    try {
      await apiFetch(`/pedidos/${idLocal}`, { method: "PATCH", body: JSON.stringify(form) });
      toast.success("Pedido actualizado.");
      setDialogAbierto(false);
      recargar();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo modificar el pedido.");
    } finally {
      setGuardando(false);
    }
  }

  if (cargando) {
    return (
      <div className="flex flex-col gap-5" aria-busy="true">
        <div className="space-y-2">
          <Skeleton className="h-8 w-56" />
          <Skeleton className="h-4 w-72" />
        </div>
        <div className="grid gap-5 lg:grid-cols-[1fr_20rem]">
          <Skeleton className="h-64 w-full rounded-xl" />
          <Skeleton className="h-64 w-full rounded-xl" />
        </div>
      </div>
    );
  }

  if (!pedido) {
    return (
      <EmptyState
        icon={CircleSlash}
        tone="danger"
        title="No se pudo abrir el pedido"
        description={error ?? `No se encontró el pedido ${idLocal}.`}
        className="py-24"
        action={
          <div className="flex gap-2">
            <Button variant="outline" onClick={recargar}>
              Reintentar
            </Button>
            <Button asChild variant="ghost">
              <Link href="/pedidos">Volver a Pedidos</Link>
            </Button>
          </div>
        }
      />
    );
  }

  const estadoInfo = estadoLocalInfo(pedido.estadoLocal);
  const rocketfyInfo = rocketfyStatusInfo(pedido.statusIdRocketfy);
  const puedeModificar = pedido.idRocketfy != null;
  const puedeRechazar = pedido.idRocketfy != null && pedido.estadoLocal !== "rechazado";
  const telefonoDigitos = pedido.telefono.replace(/\D/g, "");

  const hitos = [
    { label: "Pedido creado", fecha: pedido.creadoEn, hecho: true },
    {
      label: pedido.estadoLocal === "rechazado" ? "Pedido rechazado" : "Confirmado en Rocketfy",
      fecha: pedido.estadoLocal === "rechazado" ? pedido.actualizadoEn : pedido.confirmadoEn,
      hecho: pedido.estadoLocal === "rechazado" || Boolean(pedido.confirmadoEn),
    },
  ];

  return (
    <>
      <PageHeader
        accionesDebajoEnMovil
        title={`Pedido #${pedido.idLocal}`}
        badge={
          <>
            <StatusBadge label={estadoInfo.label} variant={estadoInfo.variant} />
            {rocketfyInfo && <StatusBadge label={`Rocketfy: ${rocketfyInfo.label}`} variant={rocketfyInfo.variant} />}
          </>
        }
        description={
          <>
            Creado el {formatFechaHora(pedido.creadoEn)}
            {pedido.idRocketfy && (
              <>
                {" "}
                · Rocketfy <span className="tabular">#{pedido.idRocketfy}</span>
              </>
            )}
          </>
        }
        actions={
          <>
            <Dialog open={dialogAbierto} onOpenChange={abrirDialogo}>
              <DialogTrigger asChild>
                <Button variant="outline" disabled={!puedeModificar}>
                  <Pencil /> Modificar
                </Button>
              </DialogTrigger>
              <DialogContent className="max-h-[92dvh] overflow-y-auto">
                <form onSubmit={handleModificar}>
                  <DialogHeader>
                    <DialogTitle>Modificar datos de entrega</DialogTitle>
                    <DialogDescription>El cambio se envía a Rocketfy. Solo se puede mientras el pedido no haya salido.</DialogDescription>
                  </DialogHeader>
                  <div className="grid gap-4 py-4">
                    <div className="grid gap-1.5">
                      <Label htmlFor="nombreCliente">Nombre</Label>
                      <Input id="nombreCliente" value={form.nombreCliente ?? ""} onChange={(e) => setForm({ ...form, nombreCliente: e.target.value })} />
                    </div>
                    <div className="grid gap-1.5">
                      <Label htmlFor="telefono">Teléfono</Label>
                      <Input id="telefono" inputMode="tel" value={form.telefono ?? ""} onChange={(e) => setForm({ ...form, telefono: e.target.value })} />
                    </div>
                    <div className="grid gap-1.5">
                      <Label htmlFor="direccion">Dirección</Label>
                      <Input id="direccion" value={form.direccion ?? ""} onChange={(e) => setForm({ ...form, direccion: e.target.value })} />
                    </div>
                    <div className="grid gap-1.5">
                      <Label htmlFor="direccion2">Referencia</Label>
                      <Input id="direccion2" value={form.direccion2 ?? ""} onChange={(e) => setForm({ ...form, direccion2: e.target.value })} />
                    </div>
                    <UbicacionSelector
                      provincia={form.provincia ?? ""}
                      canton={form.canton ?? ""}
                      onProvinciaChange={(provincia) => setForm({ ...form, provincia })}
                      onCantonChange={(canton) => setForm({ ...form, canton })}
                    />
                  </div>
                  <DialogFooter>
                    <DialogClose asChild>
                      <Button variant="outline" type="button">
                        Cancelar
                      </Button>
                    </DialogClose>
                    <Button type="submit" disabled={guardando}>
                      {guardando ? (
                        <>
                          <Loader2 className="animate-spin" /> Guardando…
                        </>
                      ) : (
                        "Guardar cambios"
                      )}
                    </Button>
                  </DialogFooter>
                </form>
              </DialogContent>
            </Dialog>

            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button variant="destructive" disabled={!puedeRechazar || rechazando}>
                  <XCircle /> Rechazar
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>¿Rechazar este pedido en Rocketfy?</AlertDialogTitle>
                  <AlertDialogDescription>
                    Esta acción se envía directamente a Rocketfy y no se puede deshacer desde aquí.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancelar</AlertDialogCancel>
                  <AlertDialogAction onClick={handleRechazar}>Sí, rechazar</AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </>
        }
      />

      {pedido.mensajeError && (
        <div role="alert" className="flex items-start gap-3 rounded-xl border border-status-danger/30 bg-status-danger-soft p-4 text-status-danger-ink">
          <TriangleAlert className="mt-0.5 size-5 shrink-0" aria-hidden />
          <div className="space-y-1">
            <p className="font-semibold">Este pedido requiere tu atención</p>
            <p className="text-sm">{pedido.mensajeError}</p>
          </div>
        </div>
      )}

      <div className="grid items-start gap-5 lg:grid-cols-[1fr_20rem]">
        <div className="flex min-w-0 flex-col gap-5">
          <Bloque icon={ReceiptText} titulo="Productos">
            <ul className="divide-y">
              {pedido.lineas.map((linea, i) => (
                <li key={i} className="flex items-center gap-3 py-3 first:pt-0">
                  <span className="tabular flex size-9 shrink-0 items-center justify-center rounded-lg bg-muted text-sm font-semibold">
                    {linea.cantidad}×
                  </span>
                  <div className="min-w-0">
                    <p className="font-medium">{linea.nombre}</p>
                    <p className="tabular text-xs text-muted-foreground">{linea.sku}</p>
                  </div>
                </li>
              ))}
            </ul>
            <div className="mt-1 flex items-center justify-between border-t pt-4">
              <span className="text-sm text-muted-foreground">{pedido.noContraEntrega ? "Total (ya pagado)" : "Total a cobrar"}</span>
              <span className="tabular text-2xl font-semibold tracking-tight">{formatMoney(pedido.total)}</span>
            </div>
          </Bloque>

          <Bloque icon={MapPin} titulo="Cliente y entrega">
            <dl className="grid gap-x-6 gap-y-4 sm:grid-cols-2">
              <Dato label="Nombre">{pedido.nombreCliente}</Dato>
              <Dato label="Teléfono">
                <span className="tabular">{formatPhone(pedido.telefono)}</span>
              </Dato>
              <Dato label="Dirección" className="sm:col-span-2">
                {pedido.direccion}
              </Dato>
              <Dato label="Referencia" className="sm:col-span-2">
                {pedido.direccion2}
              </Dato>
              <Dato label="Cantón">{pedido.canton}</Dato>
              <Dato label="Provincia">{pedido.provincia}</Dato>
              <Dato label="Código postal">{pedido.codigoPostal}</Dato>
              <Dato label="Tipo de cobro">{pedido.noContraEntrega ? "Prepagado" : "Contraentrega"}</Dato>
              <Dato label="Observaciones para el transportista" className="sm:col-span-2">
                {pedido.observacionesTransportista}
              </Dato>
            </dl>
            <div className="mt-5 flex flex-wrap gap-2 border-t pt-4">
              <Button variant="outline" size="sm" asChild>
                <a href={`tel:+${telefonoDigitos}`}>
                  <Phone /> Llamar
                </a>
              </Button>
              <Button variant="outline" size="sm" asChild>
                <a href={`https://wa.me/${telefonoDigitos}`} target="_blank" rel="noreferrer">
                  <MessageCircle /> WhatsApp
                </a>
              </Button>
            </div>
          </Bloque>
        </div>

        <Bloque icon={Truck} titulo="Seguimiento" className="lg:sticky lg:top-20">
          <ol className="relative space-y-5 before:absolute before:top-2 before:bottom-2 before:left-[0.6875rem] before:w-px before:bg-border">
            {hitos.map((h) => (
              <li key={h.label} className="relative flex gap-3">
                <span
                  aria-hidden
                  className={cn(
                    "relative z-10 mt-0.5 flex size-[1.4rem] shrink-0 items-center justify-center rounded-full ring-4 ring-card",
                    h.hecho ? "bg-status-success text-status-success-foreground" : "bg-muted text-muted-foreground",
                  )}
                >
                  <span className={cn("size-2 rounded-full", h.hecho ? "bg-status-success-foreground" : "bg-muted-foreground/50")} />
                </span>
                <div>
                  <p className={cn("text-sm font-medium", !h.hecho && "text-muted-foreground")}>{h.label}</p>
                  <p className="text-xs text-muted-foreground">{h.hecho ? formatFechaHora(h.fecha) : "Pendiente"}</p>
                </div>
              </li>
            ))}
          </ol>

          <dl className="mt-6 space-y-4 border-t pt-4">
            <Dato label="Estado en Rocketfy">
              {rocketfyInfo ? <StatusBadge label={rocketfyInfo.label} variant={rocketfyInfo.variant} /> : "Aún sin estado"}
            </Dato>
            <Dato label="Última actualización">{formatFechaHora(pedido.actualizadoEn)}</Dato>
          </dl>
        </Bloque>
      </div>
    </>
  );
}
