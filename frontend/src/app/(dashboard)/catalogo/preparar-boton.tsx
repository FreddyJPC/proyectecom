"use client";

import { FilePenLine, Loader2, PackagePlus } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { apiFetch, ApiError } from "@/lib/api";
import type { ProductoBotDetalle, ProductoBotResumen } from "@/types/producto-bot";

/** Ruta de la ficha de un producto de ventas. */
export function fichaHref(sku: string): string {
  return `/catalogo/producto/${encodeURIComponent(sku)}`;
}

/** Botón de cada fila del catálogo de Rocketfy. Si el producto aún no tiene
 * ficha de ventas, la crea (como borrador: Victoria NO lo ve todavía) con los
 * datos de Rocketfy y abre la ficha para completarla. Si ya la tiene, solo
 * lleva a ella. */
export function PrepararBoton({
  sku,
  existente,
  onCreado,
  className,
}: {
  sku: string;
  existente?: ProductoBotResumen;
  onCreado: () => void;
  className?: string;
}) {
  const router = useRouter();
  const [creando, setCreando] = useState(false);

  if (existente) {
    return (
      <Button asChild variant="outline" size="sm" className={className}>
        <Link href={fichaHref(existente.sku)}>
          <FilePenLine /> Ver ficha
        </Link>
      </Button>
    );
  }

  async function preparar() {
    setCreando(true);
    try {
      const creado = await apiFetch<ProductoBotDetalle>("/productos-bot", {
        method: "POST",
        body: JSON.stringify({ sku }),
      });
      toast.success("Borrador creado. Completa la ficha y publícalo cuando esté listo.");
      onCreado();
      router.push(fichaHref(creado.sku));
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        // Ya existía (otra persona o pestaña lo creó): se abre su ficha.
        onCreado();
        router.push(fichaHref(sku));
        return;
      }
      toast.error(err instanceof ApiError ? err.message : "No se pudo preparar el producto.");
      setCreando(false);
    }
  }

  return (
    <Button size="sm" onClick={preparar} disabled={creando} className={className}>
      {creando ? <Loader2 className="animate-spin" /> : <PackagePlus />}
      {creando ? "Preparando…" : "Preparar para vender"}
    </Button>
  );
}
