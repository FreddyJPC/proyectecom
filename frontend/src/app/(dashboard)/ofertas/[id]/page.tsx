"use client";

import { Tag } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { EmptyState } from "@/components/app/empty-state";
import { ListSkeleton } from "@/components/app/list-skeleton";
import { PageHeader } from "@/components/app/page-header";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { useApi } from "@/hooks/use-api";
import { situacionOfertaInfo } from "@/lib/estados";
import { formatMoney } from "@/lib/format";
import type { Oferta } from "@/types/precios";

import { FormularioOferta } from "../formulario-oferta";

export default function EditarOfertaPage() {
  const { id } = useParams<{ id: string }>();
  const oferta = useApi<Oferta>(/^\d+$/.test(id) ? `/precios/ofertas/${id}` : null);

  if (!/^\d+$/.test(id) || (oferta.error && !oferta.data)) {
    return (
      <EmptyState
        icon={Tag}
        tone="danger"
        title="No se pudo abrir la oferta"
        description={oferta.error ?? "Esa oferta no existe."}
        action={
          <div className="flex gap-2">
            <Button variant="outline" onClick={oferta.recargar}>
              Reintentar
            </Button>
            <Button asChild>
              <Link href="/ofertas">Ver ofertas</Link>
            </Button>
          </div>
        }
      />
    );
  }
  if (oferta.cargando || !oferta.data) return <ListSkeleton filas={4} />;

  const o = oferta.data;
  return (
    <>
      <PageHeader
        title={o.nombre}
        description={`${o.ventas} venta${o.ventas === 1 ? "" : "s"} · ${formatMoney(o.ingreso)} vendidos`}
        badge={<StatusBadge {...situacionOfertaInfo(o.situacion)} />}
      />
      <FormularioOferta key={JSON.stringify(o)} oferta={o} onGuardada={oferta.recargar} />
    </>
  );
}
