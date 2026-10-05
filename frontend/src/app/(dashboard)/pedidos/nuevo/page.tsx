"use client";

import { Plus, X } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState, type FormEvent } from "react";
import { toast } from "sonner";

import { UbicacionSelector } from "@/components/ubicacion-selector";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { apiFetch, ApiError } from "@/lib/api";
import type { LineaPedido } from "@/types/pedido";
import type { Producto } from "@/types/producto";

import { AgregarProductoDialog } from "./agregar-producto-dialog";

// Solo aplica a pedidos contraentrega -- espejo de
// backend/src/integrations/rocketfy/constants.py::RECAUDO_MINIMO_CONTRAENTREGA.
// Es un aviso adelantado nada más: el backend valida esto de verdad.
const RECAUDO_MINIMO_CONTRAENTREGA = 10;

/** Módulo de Conversaciones (Fase 3.2): permite prefillear este
 * formulario desde el detalle de una conversación ("Crear pedido manual
 * con estos datos"), vía querystring -- ver
 * app/(dashboard)/conversaciones/[id]/page.tsx. Este formulario no
 * existía con soporte de prefill antes; se agregó acá en vez de duplicar
 * el formulario. useSearchParams() exige un límite <Suspense> alrededor
 * (si no, `next build` falla) -- por eso el default export de más abajo
 * es un wrapper delgado.*/
export default function NuevoPedidoPage() {
  return (
    <Suspense fallback={<div className="text-sm text-muted-foreground">Cargando…</div>}>
      <NuevoPedidoFormulario />
    </Suspense>
  );
}

function NuevoPedidoFormulario() {
  const router = useRouter();
  const searchParams = useSearchParams();
  // Único por corrida, igual que tools/rocketfy_order_smoke_test.py
  // (int(time.time())) -- el dueño del negocio no tiene por qué inventar
  // un ID.
  const [idLocal] = useState(() => Math.floor(Date.now() / 1000));

  const [nombreCliente, setNombreCliente] = useState(() => searchParams.get("nombreCliente") ?? "");
  const [telefono, setTelefono] = useState(() => searchParams.get("telefono") ?? "");
  const [email, setEmail] = useState("");
  const [direccion, setDireccion] = useState(() => searchParams.get("direccion") ?? "");
  const [direccion2, setDireccion2] = useState("");
  const [provincia, setProvincia] = useState(() => searchParams.get("provincia") ?? "");
  const [canton, setCanton] = useState(() => searchParams.get("canton") ?? "");
  const [codigoPostal, setCodigoPostal] = useState("");
  const [noContraEntrega, setNoContraEntrega] = useState(false);
  const [total, setTotal] = useState(() => searchParams.get("total") ?? "");
  const [observaciones, setObservaciones] = useState("");
  const [lineas, setLineas] = useState<LineaPedido[]>(() => {
    const sku = searchParams.get("productoSku");
    const nombre = searchParams.get("productoNombre");
    return sku && nombre ? [{ sku, nombre, cantidad: 1 }] : [];
  });
  const [enviando, setEnviando] = useState(false);

  function agregarLinea(producto: Producto) {
    if (lineas.some((l) => l.sku === producto.sku)) {
      toast.info("Ese producto ya está en el pedido.");
      return;
    }
    setLineas([...lineas, { sku: producto.sku, nombre: producto.name, cantidad: 1 }]);
  }

  function actualizarCantidad(sku: string, cantidad: number) {
    setLineas(lineas.map((l) => (l.sku === sku ? { ...l, cantidad } : l)));
  }

  function quitarLinea(sku: string) {
    setLineas(lineas.filter((l) => l.sku !== sku));
  }

  const totalNumerico = Number(total || "0");
  const avisoRecaudoMinimo =
    !noContraEntrega && total !== "" && totalNumerico < RECAUDO_MINIMO_CONTRAENTREGA;

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (lineas.length === 0) {
      toast.error("Agrega al menos un producto.");
      return;
    }
    if (!provincia || !canton) {
      toast.error("Selecciona provincia y cantón.");
      return;
    }

    setEnviando(true);
    const payload = {
      idLocal,
      nombreCliente,
      telefono,
      email: email || null,
      direccion,
      direccion2,
      canton,
      provincia,
      codigoPostal: codigoPostal || null,
      total: totalNumerico,
      noContraEntrega,
      observacionesTransportista: observaciones,
      lineas,
    };

    try {
      await apiFetch("/pedidos", { method: "POST", body: JSON.stringify(payload) });
      toast.success("Pedido creado y confirmado.");
      router.push(`/pedidos/${idLocal}`);
      return;
    } catch (err) {
      const mensaje = err instanceof ApiError ? err.message : "No se pudo crear el pedido.";
      // Algunos errores (ej. Rocketfy rechaza la confirmación) igual dejan
      // un pedido real creado -- si existe, lo mejor es llevar al usuario
      // a verlo, no dejarlo perdido en el formulario.
      try {
        await apiFetch(`/pedidos/${idLocal}`);
        toast.warning("El pedido quedó creado, pero necesita revisión.", { description: mensaje });
        router.push(`/pedidos/${idLocal}`);
        return;
      } catch {
        toast.error(mensaje);
      }
    } finally {
      setEnviando(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">Nuevo pedido</h2>
          <p className="text-sm text-muted-foreground">
            Respaldo manual mientras no exista el bot de WhatsApp. ID interno:{" "}
            <span className="font-mono">{idLocal}</span> (generado automáticamente).
          </p>
        </div>
        <Button type="submit" disabled={enviando}>
          {enviando ? "Creando…" : "Crear y confirmar pedido"}
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Cliente y entrega</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="grid gap-1.5">
            <Label htmlFor="nombreCliente">Nombre completo</Label>
            <Input id="nombreCliente" required value={nombreCliente} onChange={(e) => setNombreCliente(e.target.value)} />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="telefono">Teléfono</Label>
            <Input id="telefono" required value={telefono} onChange={(e) => setTelefono(e.target.value)} />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="email">Correo (opcional)</Label>
            <Input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="codigoPostal">Código postal (opcional)</Label>
            <Input id="codigoPostal" value={codigoPostal} onChange={(e) => setCodigoPostal(e.target.value)} />
          </div>
          <div className="grid gap-1.5 sm:col-span-2">
            <Label htmlFor="direccion">Dirección</Label>
            <Input id="direccion" required value={direccion} onChange={(e) => setDireccion(e.target.value)} />
          </div>
          <div className="grid gap-1.5 sm:col-span-2">
            <Label htmlFor="direccion2">Referencia (opcional)</Label>
            <Input id="direccion2" value={direccion2} onChange={(e) => setDireccion2(e.target.value)} />
          </div>
          <div className="sm:col-span-2">
            <UbicacionSelector
              provincia={provincia}
              canton={canton}
              onProvinciaChange={setProvincia}
              onCantonChange={setCanton}
            />
          </div>
          <div className="grid gap-1.5 sm:col-span-2">
            <Label htmlFor="observaciones">Observaciones para el transportista (opcional)</Label>
            <Textarea id="observaciones" value={observaciones} onChange={(e) => setObservaciones(e.target.value)} />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-sm">Productos</CardTitle>
          <AgregarProductoDialog
            onSeleccionar={agregarLinea}
            trigger={
              <Button type="button" variant="outline" size="sm">
                <Plus /> Agregar producto
              </Button>
            }
          />
        </CardHeader>
        <CardContent className="flex flex-col gap-2">
          {lineas.length === 0 && (
            <p className="py-4 text-center text-sm text-muted-foreground">Ningún producto agregado todavía.</p>
          )}
          {lineas.map((linea) => (
            <div key={linea.sku} className="flex items-center gap-3 rounded-md border p-2">
              <div className="flex-1">
                <p className="text-sm font-medium">{linea.nombre}</p>
                <p className="font-mono text-xs text-muted-foreground">{linea.sku}</p>
              </div>
              <Input
                type="number"
                min={1}
                value={linea.cantidad}
                onChange={(e) => actualizarCantidad(linea.sku, Math.max(1, Number(e.target.value)))}
                className="w-20"
              />
              <Button type="button" variant="ghost" size="icon" onClick={() => quitarLinea(linea.sku)}>
                <X />
              </Button>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Cobro</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="flex items-center gap-2">
            <Checkbox
              id="noContraEntrega"
              checked={noContraEntrega}
              onCheckedChange={(v) => setNoContraEntrega(v === true)}
            />
            <Label htmlFor="noContraEntrega" className="text-sm font-normal">
              El cliente ya pagó (prepagado, no contraentrega)
            </Label>
          </div>
          <div className="grid max-w-40 gap-1.5">
            <Label htmlFor="total">Total a cobrar (USD)</Label>
            <Input
              id="total"
              type="number"
              step="0.01"
              min={0}
              required
              value={total}
              onChange={(e) => setTotal(e.target.value)}
            />
          </div>
          {avisoRecaudoMinimo && (
            <p className="text-sm text-status-warning">
              Rocketfy exige un mínimo de ${RECAUDO_MINIMO_CONTRAENTREGA} para confirmar un pedido
              contraentrega — con este total seguro no se confirma. Sube el total o marca &ldquo;ya
              pagó&rdquo;.
            </p>
          )}
          {!noContraEntrega && (
            <p className="text-xs text-muted-foreground">
              Nota: el mínimo real puede ser más alto que ${RECAUDO_MINIMO_CONTRAENTREGA} — Rocketfy
              también exige cubrir el costo de envío al destino, y no hay forma de consultarlo de
              antemano (limitación conocida del proveedor). Si Rocketfy rechaza la confirmación por
              esto, el pedido queda creado y podrás revisarlo y decidir qué hacer.
            </p>
          )}
        </CardContent>
      </Card>
    </form>
  );
}
