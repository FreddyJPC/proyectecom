"use client";

import { InfoButton } from "@/components/app/info-button";
import { SectionCard } from "@/components/app/section-card";
import { StatusBadge } from "@/components/status-badge";
import { Skeleton } from "@/components/ui/skeleton";
import { formatMoney } from "@/lib/format";
import type { CifrasDeOrigen, ResumenOrigenes } from "@/types/anuncios";

function Cifra({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-0.5">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="tabular text-lg font-semibold">{children}</dd>
    </div>
  );
}

function Origen({ titulo, variante, cifras }: { titulo: string; variante: "info" | "neutral"; cifras: CifrasDeOrigen }) {
  return (
    <div className="space-y-3 rounded-xl border bg-card p-4">
      <StatusBadge label={titulo} variant={variante} />
      <dl className="grid grid-cols-2 gap-x-4 gap-y-3">
        <Cifra label="Clientes nuevos">{cifras.conversaciones}</Cifra>
        <Cifra label="Ventas">{cifras.ventas}</Cifra>
        <Cifra label="Ingresos">{formatMoney(cifras.ingresos)}</Cifra>
        <Cifra label="Ganancia">{formatMoney(cifras.ganancia)}</Cifra>
      </dl>
    </div>
  );
}

/** «De dónde vienen tus clientes»: anuncio frente a directo, con las ventas de cada uno. */
export function ResumenOrigenesCard({ resumen, cargando }: { resumen: ResumenOrigenes | null; cargando: boolean }) {
  return (
    <SectionCard
      titulo="De dónde vienen tus clientes"
      descripcion="Por anuncio frente a directo."
      info={
        <InfoButton titulo="De dónde vienen tus clientes">
          <ul>
            <li>
              <strong>Por anuncio:</strong> clientes que escribieron tocando un anuncio de Click-to-WhatsApp en este periodo. Si un cliente que ya existía vuelve por un anuncio, también cuenta aquí.
            </li>
            <li>
              <strong>Directo:</strong> clientes nuevos del periodo que nunca llegaron por un anuncio.
            </li>
            <li>
              <strong>Ventas, ingresos y ganancia:</strong> las ventas cerradas en el periodo (sin contar las canceladas), separadas por el origen que tenía el cliente al comprar.
            </li>
          </ul>
          <p>
            La <strong>ganancia</strong> suma solo las ventas cuyo costo se conoce, así que puede quedar corta si a alguna le falta el costo.
          </p>
        </InfoButton>
      }
    >
      <div className="p-4 sm:p-5">
        {cargando || !resumen ? (
          <div className="grid gap-4 sm:grid-cols-2" aria-busy="true" aria-label="Cargando el resumen">
            <Skeleton className="h-36 w-full rounded-xl" />
            <Skeleton className="h-36 w-full rounded-xl" />
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2">
            <Origen titulo="Por anuncio" variante="info" cifras={resumen.anuncio} />
            <Origen titulo="Directo" variante="neutral" cifras={resumen.directo} />
          </div>
        )}
      </div>
    </SectionCard>
  );
}
