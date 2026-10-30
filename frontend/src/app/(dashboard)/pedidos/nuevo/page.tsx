"use client";

import { Info, Loader2, Minus, PackagePlus, Plus, Trash2, TriangleAlert } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState, type FormEvent, type ReactNode } from "react";
import { toast } from "sonner";

import { PageHeader } from "@/components/app/page-header";
import { UbicacionSelector } from "@/components/ubicacion-selector";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { apiFetch, ApiError } from "@/lib/api";
import { formatMoney } from "@/lib/format";
import type { LineaPedido } from "@/types/pedido";
import type { Producto } from "@/types/producto";

import { AgregarProductoDialog } from "./agregar-producto-dialog";

// Solo aplica a pedidos contraentrega -- espejo de
// backend/src/integrations/rocketfy/constants.py::RECAUDO_MINIMO_CONTRAENTREGA.
// Es un aviso adelantado nada más: el backend valida esto de verdad.
const RECAUDO_MINIMO_CONTRAENTREGA = 10;

function Seccion({ titulo, descripcion, children, accion }: { titulo: string; descripcion?: string; children: ReactNode; accion?: ReactNode }) {
  return (
    <Card className="gap-0 py-0">
      <div className="flex items-center justify-between gap-3 border-b px-4 py-3.5 sm:px-5">
        <div>
          <h2 className="text-sm font-semibold">{titulo}</h2>
          {descripcion && <p className="text-xs text-muted-foreground">{descripcion}</p>}
        </div>
        {accion}
      </div>
      <div className="p-4 sm:p-5">{children}</div>
    </Card>
  );
}

/** Módulo de Conversaciones (Fase 3.2): permite prefillear este
 * formulario desde el detalle de una conversación ("Crear pedido con estos
 * datos"), vía querystring -- ver
 * app/(dashboard)/conversaciones/[id]/page.tsx. useSearchParams() exige un
 * límite <Suspense> alrededor (si no, `next build` falla) -- por eso el
 * default export de más abajo es un wrapper delgado.*/
export default function NuevoPedidoPage() {
  return (
    <Suspense fallback={<Skeleton className="h-96 w-full" />}>
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
  const vieneDeConversacion = Boolean(searchParams.get("nombreCliente"));

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
    setLineas(lineas.map((l) => (l.sku === sku ? { ...l, cantidad: Math.max(1, cantidad) } : l)));
  }

  function quitarLinea(sku: string) {
    setLineas(lineas.filter((l) => l.sku !== sku));
  }

  const totalNumerico = Number(total || "0");
  const avisoRecaudoMinimo = !noContraEntrega && total !== "" && totalNumerico < RECAUDO_MINIMO_CONTRAENTREGA;
  const unidades = lineas.reduce((n, l) => n + l.cantidad, 0);

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

  const botonEnviar = (
    <Button type="submit" size="lg" disabled={enviando} className="w-full">
      {enviando ? (
        <>
          <Loader2 className="animate-spin" /> Creando pedido…
        </>
      ) : (
        "Crear y confirmar pedido"
      )}
    </Button>
  );

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-5">
      <PageHeader
        title="Nuevo pedido"
        description={
          <>
            Crea un pedido a mano en Rocketfy: una venta cerrada fuera de WhatsApp o una que Victoria no pudo completar.{" "}
            <span className="whitespace-nowrap text-xs">
              ID interno <span className="tabular" suppressHydrationWarning>{idLocal}</span>
            </span>
          </>
        }
      />

      {vieneDeConversacion && (
        <div className="flex items-start gap-3 rounded-xl border border-status-info/30 bg-status-info-soft p-3.5 text-sm text-status-info-ink">
          <Info className="mt-0.5 size-4 shrink-0" aria-hidden />
          <p>Datos precargados desde la conversación. Revísalos antes de crear el pedido.</p>
        </div>
      )}

      <div className="grid items-start gap-5 lg:grid-cols-[1fr_22rem]">
        <div className="flex flex-col gap-5">
          <Seccion titulo="Cliente" descripcion="Quién recibe el pedido.">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="grid gap-1.5 sm:col-span-2">
                <Label htmlFor="nombreCliente">Nombre completo</Label>
                <Input id="nombreCliente" required autoComplete="name" value={nombreCliente} onChange={(e) => setNombreCliente(e.target.value)} />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="telefono">Teléfono</Label>
                <Input id="telefono" required type="tel" inputMode="tel" autoComplete="tel" placeholder="593 9X XXX XXXX" value={telefono} onChange={(e) => setTelefono(e.target.value)} />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="email">
                  Correo <span className="font-normal text-muted-foreground">(opcional)</span>
                </Label>
                <Input id="email" type="email" inputMode="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} />
              </div>
            </div>
          </Seccion>

          <Seccion titulo="Entrega" descripcion="Dónde se entrega. La ciudad se valida antes de enviarla a Rocketfy.">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="grid gap-1.5 sm:col-span-2">
                <Label htmlFor="direccion">Dirección</Label>
                <Input id="direccion" required autoComplete="street-address" value={direccion} onChange={(e) => setDireccion(e.target.value)} />
              </div>
              <div className="grid gap-1.5 sm:col-span-2">
                <Label htmlFor="direccion2">
                  Referencia <span className="font-normal text-muted-foreground">(opcional)</span>
                </Label>
                <Input id="direccion2" placeholder="Ej.: frente al parque, casa blanca" value={direccion2} onChange={(e) => setDireccion2(e.target.value)} />
              </div>
              <div className="sm:col-span-2">
                <UbicacionSelector provincia={provincia} canton={canton} onProvinciaChange={setProvincia} onCantonChange={setCanton} />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="codigoPostal">
                  Código postal <span className="font-normal text-muted-foreground">(opcional)</span>
                </Label>
                <Input id="codigoPostal" inputMode="numeric" value={codigoPostal} onChange={(e) => setCodigoPostal(e.target.value)} />
              </div>
              <div className="grid gap-1.5 sm:col-span-2">
                <Label htmlFor="observaciones">
                  Observaciones para el transportista <span className="font-normal text-muted-foreground">(opcional)</span>
                </Label>
                <Textarea id="observaciones" rows={2} value={observaciones} onChange={(e) => setObservaciones(e.target.value)} />
              </div>
            </div>
          </Seccion>
        </div>

        <div className="flex flex-col gap-5 lg:sticky lg:top-20">
          <Seccion
            titulo="Productos"
            descripcion={unidades > 0 ? `${unidades} ${unidades === 1 ? "unidad" : "unidades"}` : undefined}
            accion={
              <AgregarProductoDialog
                onSeleccionar={agregarLinea}
                trigger={
                  <Button type="button" variant="outline" size="sm">
                    <Plus /> Agregar
                  </Button>
                }
              />
            }
          >
            {lineas.length === 0 ? (
              <div className="flex flex-col items-center gap-2 py-6 text-center">
                <span className="flex size-11 items-center justify-center rounded-full bg-muted text-muted-foreground">
                  <PackagePlus className="size-5" aria-hidden />
                </span>
                <p className="text-sm text-muted-foreground">Agrega al menos un producto del catálogo de Rocketfy.</p>
              </div>
            ) : (
              <ul className="flex flex-col gap-3">
                {lineas.map((linea) => (
                  <li key={linea.sku} className="rounded-lg border bg-muted/30 p-3">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="font-medium">{linea.nombre}</p>
                        <p className="tabular text-xs text-muted-foreground">{linea.sku}</p>
                      </div>
                      <Button type="button" variant="ghost" size="icon-sm" onClick={() => quitarLinea(linea.sku)} aria-label={`Quitar ${linea.nombre}`} className="-mt-1 -mr-1 text-muted-foreground hover:text-destructive">
                        <Trash2 />
                      </Button>
                    </div>
                    <div className="mt-2 inline-flex items-center rounded-lg border bg-card">
                      <Button type="button" variant="ghost" size="icon-sm" onClick={() => actualizarCantidad(linea.sku, linea.cantidad - 1)} disabled={linea.cantidad <= 1} aria-label="Una unidad menos">
                        <Minus />
                      </Button>
                      <span className="tabular w-9 text-center text-sm font-semibold" aria-live="polite">
                        {linea.cantidad}
                      </span>
                      <Button type="button" variant="ghost" size="icon-sm" onClick={() => actualizarCantidad(linea.sku, linea.cantidad + 1)} aria-label="Una unidad más">
                        <Plus />
                      </Button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </Seccion>

          <Seccion titulo="Cobro">
            <div className="flex flex-col gap-4">
              <div className="flex items-start gap-3">
                <Checkbox id="noContraEntrega" checked={noContraEntrega} onCheckedChange={(v) => setNoContraEntrega(v === true)} className="mt-0.5 size-5" />
                <Label htmlFor="noContraEntrega" className="text-sm leading-snug font-normal">
                  El cliente ya pagó (prepagado, no contraentrega)
                </Label>
              </div>

              <div className="grid gap-1.5">
                <Label htmlFor="total">Total a cobrar (USD)</Label>
                <div className="relative">
                  <span className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-muted-foreground">$</span>
                  <Input id="total" type="number" inputMode="decimal" step="0.01" min={0} required value={total} onChange={(e) => setTotal(e.target.value)} className="tabular pl-7 text-base font-semibold" />
                </div>
              </div>

              {avisoRecaudoMinimo && (
                <div role="alert" className="flex items-start gap-2.5 rounded-lg border border-status-warning/40 bg-status-warning-soft p-3 text-sm text-status-warning-ink">
                  <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
                  <p>
                    Rocketfy exige un mínimo de {formatMoney(String(RECAUDO_MINIMO_CONTRAENTREGA))} para confirmar un pedido contraentrega: con este total
                    seguro no se confirma. Sube el total o marca «ya pagó».
                  </p>
                </div>
              )}
              {!noContraEntrega && (
                <p className="text-xs leading-relaxed text-muted-foreground">
                  El mínimo real puede ser más alto que {formatMoney(String(RECAUDO_MINIMO_CONTRAENTREGA))}: Rocketfy también exige cubrir el costo de envío al
                  destino y no hay forma de consultarlo de antemano. Si rechaza la confirmación por esto, el pedido queda creado y podrás revisarlo.
                </p>
              )}
            </div>
          </Seccion>

          <div className="hidden lg:block">{botonEnviar}</div>
        </div>
      </div>

      {/* Móvil: barra fija sobre la navegación con el total y el botón de crear */}
      <div className="sticky bottom-[calc(4.25rem+env(safe-area-inset-bottom))] z-20 -mx-4 flex items-center gap-3 border-t bg-card/95 p-3 backdrop-blur lg:hidden">
        <div className="shrink-0 pl-1">
          <p className="text-xs text-muted-foreground">Total</p>
          <p className="tabular text-lg leading-tight font-semibold">{total ? formatMoney(total) : "—"}</p>
        </div>
        <div className="flex-1">{botonEnviar}</div>
      </div>
    </form>
  );
}
