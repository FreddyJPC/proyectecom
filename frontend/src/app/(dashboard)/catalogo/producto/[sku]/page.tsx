"use client";

import { CircleSlash } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { EmptyState } from "@/components/app/empty-state";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/use-api";
import type { ProductoBotDetalle } from "@/types/producto-bot";

import { Ficha } from "./ficha";

/** El SKU llega de la URL, a veces todavía codificado (espacios, símbolos). */
function decodificar(sku: string): string {
  try {
    return decodeURIComponent(sku);
  } catch {
    return sku;
  }
}

export default function FichaProductoPage() {
  const params = useParams<{ sku: string }>();
  const sku = decodificar(params.sku);
  const { data: detalle, error, cargando, recargar } = useApi<ProductoBotDetalle>(`/productos-bot/${encodeURIComponent(sku)}`);

  if (cargando) {
    return (
      <div className="flex flex-col gap-5" aria-busy="true" aria-label="Cargando la ficha">
        <div className="space-y-2">
          <Skeleton className="h-8 w-64" />
          <Skeleton className="h-4 w-80 max-w-full" />
        </div>
        <div className="grid gap-5 lg:grid-cols-[1fr_22rem]">
          <Skeleton className="h-96 w-full rounded-xl" />
          <Skeleton className="h-64 w-full rounded-xl" />
        </div>
      </div>
    );
  }

  if (!detalle) {
    return (
      <EmptyState
        icon={CircleSlash}
        tone="danger"
        title="No se pudo abrir la ficha"
        description={error ?? `No se encontró el producto ${sku}.`}
        className="py-24"
        action={
          <div className="flex gap-2">
            <Button variant="outline" onClick={recargar}>
              Reintentar
            </Button>
            <Button asChild variant="ghost">
              <Link href="/catalogo?tab=mis-productos">Volver a Mis productos</Link>
            </Button>
          </div>
        }
      />
    );
  }

  // `key`: cuando el servidor devuelve datos nuevos (guardar, publicar,
  // actualizar desde Rocketfy), la ficha se monta de nuevo con lo guardado.
  return <Ficha key={`${detalle.sku}|${detalle.actualizadoEn}|${detalle.estado}`} detalle={detalle} onCambio={recargar} />;
}
