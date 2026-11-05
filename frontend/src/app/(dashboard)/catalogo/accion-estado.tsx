"use client";

import { Archive, ArchiveRestore, Info, Loader2, Pause, Play, Rocket, TriangleAlert, type LucideIcon } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { apiFetch, ApiError } from "@/lib/api";
import { formatMoney } from "@/lib/format";
import type { AccionProductoBot, EstadoProductoBot, ProductoBotDetalle, Verificacion } from "@/types/producto-bot";

type ProductoMinimo = { sku: string; nombre: string; precio: string };

type Config = {
  boton: string;
  icon: LucideIcon;
  variant: "default" | "outline";
  titulo: (p: ProductoMinimo) => string;
  descripcion: (p: ProductoMinimo) => string;
  confirmar: string;
  exito: string;
};

const CONFIG: Record<AccionProductoBot, Config> = {
  publicar: {
    boton: "Publicar",
    icon: Rocket,
    variant: "default",
    titulo: (p) => `¿Publicar «${p.nombre}»?`,
    descripcion: (p) =>
      `Victoria empezará a vender «${p.nombre}» a ${formatMoney(p.precio)} en cuanto confirmes. Antes se comprueba en Rocketfy que exista y tenga stock.`,
    confirmar: "Sí, publicar",
    exito: "Publicado: Victoria ya puede venderlo.",
  },
  reanudar: {
    boton: "Reanudar",
    icon: Play,
    variant: "default",
    titulo: (p) => `¿Reanudar «${p.nombre}»?`,
    descripcion: (p) =>
      `Victoria volverá a vender «${p.nombre}» a ${formatMoney(p.precio)}. Antes se comprueba en Rocketfy que siga existiendo y tenga stock.`,
    confirmar: "Sí, reanudar",
    exito: "Reanudado: Victoria vuelve a ofrecerlo.",
  },
  pausar: {
    boton: "Pausar",
    icon: Pause,
    variant: "outline",
    titulo: (p) => `¿Pausar «${p.nombre}»?`,
    descripcion: () =>
      "Victoria dejará de ofrecerlo y no podrá cerrar ventas de este producto. No se borra nada: lo reanudas cuando quieras.",
    confirmar: "Sí, pausar",
    exito: "Pausado: Victoria ya no lo ofrece.",
  },
  archivar: {
    boton: "Archivar",
    icon: Archive,
    variant: "outline",
    titulo: (p) => `¿Archivar «${p.nombre}»?`,
    descripcion: () =>
      "Se saca de tu lista y Victoria no lo ofrece. No se borra nada: puedes restaurarlo como borrador.",
    confirmar: "Sí, archivar",
    exito: "Archivado.",
  },
  restaurar: {
    boton: "Restaurar",
    icon: ArchiveRestore,
    variant: "outline",
    titulo: (p) => `¿Restaurar «${p.nombre}»?`,
    descripcion: () =>
      "Vuelve a tu lista como borrador (todavía sin vender). Tendrás que revisarlo y publicarlo otra vez.",
    confirmar: "Sí, restaurar",
    exito: "Restaurado como borrador.",
  },
};

/** Qué acciones se pueden hacer desde cada estado. Espejo de `_TRANSICIONES`
 * en backend/src/routes/productos_bot/services.py; el backend es quien manda
 * (si no se permite, responde 409). La primera es la acción principal. */
export const ACCIONES_POR_ESTADO: Record<EstadoProductoBot, AccionProductoBot[]> = {
  borrador: ["publicar", "archivar"],
  listo: ["publicar", "archivar"],
  activo: ["pausar", "archivar"],
  pausado: ["reanudar", "archivar"],
  agotado: ["reanudar", "archivar"],
  archivado: ["restaurar"],
};

/** Botón de una acción de estado (publicar, pausar…) con su confirmación.
 * Si el backend la rechaza, el motivo se muestra DENTRO del cuadro (junto con
 * la lista de bloqueos, si la hay) y el cuadro sigue abierto. */
export function AccionEstadoBoton({
  accion,
  producto,
  verificacion,
  onHecho,
  deshabilitado,
  variant,
  size = "sm",
  className,
}: {
  accion: AccionProductoBot;
  producto: ProductoMinimo;
  /** La lista de verificación del producto: al publicar o reanudar, sus avisos se muestran
   * antes de confirmar (los bloqueos ya los impiden desde el botón). */
  verificacion?: Verificacion;
  onHecho: (detalle: ProductoBotDetalle) => void;
  deshabilitado?: boolean;
  variant?: "default" | "outline";
  size?: "sm" | "default";
  className?: string;
}) {
  const cfg = CONFIG[accion];
  const Icon = cfg.icon;
  const [abierto, setAbierto] = useState(false);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [bloqueos, setBloqueos] = useState<string[]>([]);
  const avisosPrevios = accion === "publicar" || accion === "reanudar" ? (verificacion?.avisos ?? []) : [];

  function cambiarApertura(v: boolean) {
    if (cargando) return;
    if (v) {
      setError(null);
      setBloqueos([]);
    }
    setAbierto(v);
  }

  async function ejecutar() {
    setCargando(true);
    setError(null);
    setBloqueos([]);
    try {
      const detalle = await apiFetch<ProductoBotDetalle>(`/productos-bot/${encodeURIComponent(producto.sku)}/${accion}`, {
        method: "POST",
      });
      toast.success(cfg.exito);
      setAbierto(false);
      onHecho(detalle);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
        setBloqueos(err.bloqueos);
      } else {
        setError("No se pudo conectar con el servidor.");
      }
    } finally {
      setCargando(false);
    }
  }

  return (
    <AlertDialog open={abierto} onOpenChange={cambiarApertura}>
      <AlertDialogTrigger asChild>
        <Button variant={variant ?? cfg.variant} size={size} disabled={deshabilitado} className={className}>
          <Icon /> {cfg.boton}
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{cfg.titulo(producto)}</AlertDialogTitle>
          <AlertDialogDescription>{cfg.descripcion(producto)}</AlertDialogDescription>
        </AlertDialogHeader>

        {avisosPrevios.length > 0 && (
          <div className="flex items-start gap-2.5 rounded-lg bg-status-warning-soft p-3 text-sm text-status-warning-ink">
            <Info className="mt-0.5 size-4 shrink-0" aria-hidden />
            <div className="min-w-0 space-y-1.5">
              <p className="font-medium">Ten en cuenta antes de confirmar</p>
              <ul className="list-disc space-y-1 pl-4">
                {avisosPrevios.map((a) => (
                  <li key={a}>{a}</li>
                ))}
              </ul>
            </div>
          </div>
        )}

        {error && (
          <div role="alert" className="flex items-start gap-2.5 rounded-lg border border-status-danger/30 bg-status-danger-soft p-3 text-sm text-status-danger-ink">
            <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
            <div className="min-w-0 space-y-1.5">
              <p className="font-medium">{error}</p>
              {bloqueos.length > 0 && (
                <ul className="list-disc space-y-1 pl-4">
                  {bloqueos.map((b) => (
                    <li key={b}>{b}</li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        )}

        <AlertDialogFooter>
          <AlertDialogCancel disabled={cargando}>{error ? "Cerrar" : "Cancelar"}</AlertDialogCancel>
          <Button onClick={ejecutar} disabled={cargando}>
            {cargando ? (
              <>
                <Loader2 className="animate-spin" /> Un momento…
              </>
            ) : (
              cfg.confirmar
            )}
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
