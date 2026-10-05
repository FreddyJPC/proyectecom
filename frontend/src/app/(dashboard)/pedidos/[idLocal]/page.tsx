"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { toast } from "sonner";

import { StatusBadge } from "@/components/status-badge";
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
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { UbicacionSelector } from "@/components/ubicacion-selector";
import { apiFetch, ApiError } from "@/lib/api";
import { estadoLocalInfo, rocketfyStatusInfo } from "@/lib/estados";
import type { ModificarPedidoInput, PedidoDetalle } from "@/types/pedido";

function Campo({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="space-y-0.5">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="text-sm">{value || "—"}</p>
    </div>
  );
}

export default function PedidoDetallePage() {
  const params = useParams<{ idLocal: string }>();
  const router = useRouter();
  const idLocal = params.idLocal;

  const [pedido, setPedido] = useState<PedidoDetalle | null>(null);
  const [cargando, setCargando] = useState(true);
  const [rechazando, setRechazando] = useState(false);
  const [guardando, setGuardando] = useState(false);
  const [dialogAbierto, setDialogAbierto] = useState(false);
  const [form, setForm] = useState<ModificarPedidoInput>({});

  function cargar() {
    apiFetch<PedidoDetalle>(`/pedidos/${idLocal}`)
      .then((data) => {
        setPedido(data);
        setForm({
          nombreCliente: data.nombreCliente,
          telefono: data.telefono,
          direccion: data.direccion,
          direccion2: data.direccion2,
          canton: data.canton,
          provincia: data.provincia,
          codigoPostal: data.codigoPostal ?? "",
        });
      })
      .catch((err: unknown) => {
        const mensaje = err instanceof ApiError ? err.message : "No se pudo cargar el pedido.";
        toast.error(mensaje);
      })
      .finally(() => setCargando(false));
  }

  useEffect(() => {
    cargar();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [idLocal]);

  async function handleRechazar() {
    setRechazando(true);
    try {
      await apiFetch(`/pedidos/${idLocal}/rechazar`, { method: "POST" });
      toast.success("Pedido rechazado.");
      cargar();
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
      cargar();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo modificar el pedido.");
    } finally {
      setGuardando(false);
    }
  }

  if (cargando) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-48 w-full" />
      </div>
    );
  }

  if (!pedido) {
    return (
      <div className="flex flex-col items-center justify-center gap-2 py-24 text-center text-muted-foreground">
        <p>No se encontró el pedido {idLocal}.</p>
        <Button variant="outline" onClick={() => router.push("/pedidos")}>
          Volver a Pedidos
        </Button>
      </div>
    );
  }

  const estadoInfo = estadoLocalInfo(pedido.estadoLocal);
  const rocketfyInfo = rocketfyStatusInfo(pedido.statusIdRocketfy);
  const puedeModificar = pedido.idRocketfy != null;
  const puedeRechazar = pedido.idRocketfy != null && pedido.estadoLocal !== "rechazado";

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-semibold">Pedido {pedido.idLocal}</h2>
            <StatusBadge label={estadoInfo.label} variant={estadoInfo.variant} />
            {rocketfyInfo && <StatusBadge label={`Rocketfy: ${rocketfyInfo.label}`} variant={rocketfyInfo.variant} />}
          </div>
          {pedido.idRocketfy && (
            <p className="text-sm text-muted-foreground">id_rocketfy: {pedido.idRocketfy}</p>
          )}
        </div>

        <div className="flex gap-2">
          <Dialog open={dialogAbierto} onOpenChange={setDialogAbierto}>
            <DialogTrigger asChild>
              <Button variant="outline" disabled={!puedeModificar}>
                Modificar
              </Button>
            </DialogTrigger>
            <DialogContent>
              <form onSubmit={handleModificar}>
                <DialogHeader>
                  <DialogTitle>Modificar datos de entrega</DialogTitle>
                </DialogHeader>
                <div className="grid gap-3 py-4">
                  <div className="grid gap-1.5">
                    <Label htmlFor="nombreCliente">Nombre</Label>
                    <Input
                      id="nombreCliente"
                      value={form.nombreCliente ?? ""}
                      onChange={(e) => setForm({ ...form, nombreCliente: e.target.value })}
                    />
                  </div>
                  <div className="grid gap-1.5">
                    <Label htmlFor="telefono">Teléfono</Label>
                    <Input
                      id="telefono"
                      value={form.telefono ?? ""}
                      onChange={(e) => setForm({ ...form, telefono: e.target.value })}
                    />
                  </div>
                  <div className="grid gap-1.5">
                    <Label htmlFor="direccion">Dirección</Label>
                    <Input
                      id="direccion"
                      value={form.direccion ?? ""}
                      onChange={(e) => setForm({ ...form, direccion: e.target.value })}
                    />
                  </div>
                  <div className="grid gap-1.5">
                    <Label htmlFor="direccion2">Referencia</Label>
                    <Input
                      id="direccion2"
                      value={form.direccion2 ?? ""}
                      onChange={(e) => setForm({ ...form, direccion2: e.target.value })}
                    />
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
                    {guardando ? "Guardando…" : "Guardar cambios"}
                  </Button>
                </DialogFooter>
              </form>
            </DialogContent>
          </Dialog>

          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button variant="destructive" disabled={!puedeRechazar || rechazando}>
                Rechazar pedido
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>¿Rechazar este pedido en Rocketfy?</AlertDialogTitle>
                <AlertDialogDescription>
                  Esta acción se envía directamente a Rocketfy y no se puede deshacer desde acá.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancelar</AlertDialogCancel>
                <AlertDialogAction onClick={handleRechazar}>Sí, rechazar</AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      </div>

      {pedido.mensajeError && (
        <Card className="border-status-danger/30 bg-status-danger/5">
          <CardContent className="text-sm text-status-danger">
            <strong>Requiere atención: </strong>
            {pedido.mensajeError}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Cliente y entrega</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-2 gap-4 sm:grid-cols-3">
          <Campo label="Nombre" value={pedido.nombreCliente} />
          <Campo label="Teléfono" value={pedido.telefono} />
          <Campo label="Tipo" value={pedido.noContraEntrega ? "Prepagado" : "Contraentrega"} />
          <Campo label="Dirección" value={pedido.direccion} />
          <Campo label="Referencia" value={pedido.direccion2} />
          <Campo label="Código postal" value={pedido.codigoPostal} />
          <Campo label="Cantón" value={pedido.canton} />
          <Campo label="Provincia" value={pedido.provincia} />
          <Campo label="Observaciones al transportista" value={pedido.observacionesTransportista} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Productos</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-2">
          {pedido.lineas.map((linea, i) => (
            <div key={i} className="flex items-center justify-between text-sm">
              <span>
                {linea.cantidad}× {linea.nombre}{" "}
                <span className="text-muted-foreground">({linea.sku})</span>
              </span>
            </div>
          ))}
          <Separator className="my-1" />
          <div className="flex items-center justify-between text-sm font-medium">
            <span>Total</span>
            <span>${pedido.total}</span>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Fechas</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-3 gap-4">
          <Campo label="Creado" value={pedido.creadoEn && new Date(pedido.creadoEn).toLocaleString("es-EC")} />
          <Campo
            label="Confirmado"
            value={pedido.confirmadoEn && new Date(pedido.confirmadoEn).toLocaleString("es-EC")}
          />
          <Campo
            label="Última actualización"
            value={pedido.actualizadoEn && new Date(pedido.actualizadoEn).toLocaleString("es-EC")}
          />
        </CardContent>
      </Card>
    </div>
  );
}
