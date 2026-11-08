"use client";

import { ArrowRight, History, TriangleAlert } from "lucide-react";

import { EmptyState } from "@/components/app/empty-state";
import { ListSkeleton } from "@/components/app/list-skeleton";
import { SectionCard } from "@/components/app/section-card";
import { Button } from "@/components/ui/button";
import { formatFechaHora, tiempoRelativo } from "@/lib/format";
import { formatearTextoGuardado } from "@/lib/parametros";
import type { CambioParametro, Parametro } from "@/types/parametros";

/** Quién cambió qué y cuándo: es el «deshacer» del módulo (el valor anterior queda a la vista). */
export function HistorialParametros({
  cambios,
  error,
  cargando,
  recargar,
  parametros,
}: {
  cambios: CambioParametro[] | null;
  error: string | null;
  cargando: boolean;
  recargar: () => void;
  parametros: Parametro[];
}) {
  const porClave = new Map(parametros.map((p) => [p.clave, p]));

  return (
    <SectionCard titulo="Historial de cambios" descripcion="Los últimos 20 cambios. Si algo salió mal, aquí ves qué valor tenía antes.">
      {cargando ? (
        <ListSkeleton filas={3} />
      ) : error && !cambios ? (
        <EmptyState
          icon={TriangleAlert}
          tone="danger"
          title="No se pudo cargar el historial"
          description={error}
          action={
            <Button variant="outline" size="sm" onClick={recargar}>
              Reintentar
            </Button>
          }
        />
      ) : !cambios || cambios.length === 0 ? (
        <EmptyState icon={History} title="Todavía no hay cambios" description="Cuando guardes o restaures un parámetro, quedará anotado aquí." />
      ) : (
        <ul className="divide-y">
          {cambios.map((c, i) => {
            const p = porClave.get(c.clave);
            return (
              <li key={`${c.clave}-${c.creadoEn}-${i}`} className="grid grid-cols-[minmax(0,1fr)] gap-1 px-4 py-3 sm:px-5">
                <p className="text-sm font-medium">{c.nombre}</p>
                <p className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-sm text-muted-foreground">
                  <span className="min-w-0 break-words">{formatearTextoGuardado(p, c.valorAnterior)}</span>
                  <ArrowRight className="size-3.5 shrink-0" aria-label="cambió a" />
                  <span className="min-w-0 break-words font-medium text-foreground">{formatearTextoGuardado(p, c.valorNuevo)}</span>
                </p>
                <p className="text-xs text-muted-foreground">
                  {c.usuario ?? "Alguien"} · <time dateTime={c.creadoEn} title={formatFechaHora(c.creadoEn)}>{tiempoRelativo(c.creadoEn)}</time>
                </p>
              </li>
            );
          })}
        </ul>
      )}
    </SectionCard>
  );
}
