"use client";

import { Calculator, SlidersHorizontal, TriangleAlert } from "lucide-react";

import { EmptyState } from "@/components/app/empty-state";
import { ListSkeleton } from "@/components/app/list-skeleton";
import { PageHeader } from "@/components/app/page-header";
import { SectionCard } from "@/components/app/section-card";
import { Button } from "@/components/ui/button";
import { useApi } from "@/hooks/use-api";
import type { CambioParametro, ParametrosRespuesta } from "@/types/parametros";

import { AjustesPreciosDialog } from "../catalogo/ajustes-precios-dialog";
import { HistorialParametros } from "./historial-parametros";
import { ParametroFila } from "./parametro-fila";

export default function ParametrosPage() {
  const { data, error, cargando, recargar } = useApi<ParametrosRespuesta>("/parametros");
  const historial = useApi<CambioParametro[]>("/parametros/historial?limite=20");

  const todos = data?.grupos.flatMap((g) => g.parametros) ?? [];
  const alCambiar = () => {
    recargar();
    historial.recargar();
  };

  return (
    <>
      <PageHeader
        title="Parámetros"
        description="Controla desde aquí cómo trabaja el sistema, sin tocar el servidor ni pedir un cambio de código. Cada cambio queda anotado y siempre puedes volver al valor original."
      />

      <div className="flex items-start gap-3 rounded-xl border bg-card p-4 shadow-card">
        <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-status-info-soft text-status-info-ink">
          <SlidersHorizontal className="size-[1.1rem]" aria-hidden />
        </span>
        <div className="space-y-0.5">
          <p className="text-sm font-semibold">Qué valor se usa</p>
          <p className="text-sm text-muted-foreground">
            Primero lo que guardes aquí; si no hay nada, la variable equivalente del servidor (Railway), si existe; y si tampoco, el valor original que trae el
            programa. Mientras no guardes nada aquí, todo funciona como antes.
          </p>
        </div>
      </div>

      {error && !data ? (
        <div role="alert" className="flex flex-wrap items-center gap-3 rounded-xl border border-status-danger/30 bg-status-danger-soft p-4 text-status-danger-ink">
          <TriangleAlert className="size-5 shrink-0" aria-hidden />
          <p className="flex-1 text-sm">No se pudieron cargar los parámetros. {error}</p>
          <Button variant="outline" size="sm" onClick={recargar} className="bg-card text-foreground">
            Reintentar
          </Button>
        </div>
      ) : cargando ? (
        <SectionCard titulo="Cargando parámetros" descripcion="Un momento…">
          <ListSkeleton filas={4} />
        </SectionCard>
      ) : !data || data.grupos.length === 0 ? (
        <EmptyState icon={SlidersHorizontal} title="No hay parámetros para mostrar" description="Vuelve a intentarlo en un momento." />
      ) : (
        data.grupos.map((g) => (
          <SectionCard key={g.clave} titulo={g.nombre} descripcion={g.descripcion}>
            <ul className="divide-y">
              {g.parametros.map((p) => (
                // La clave incluye el valor para que, tras guardar, el control arranque de cero con lo nuevo.
                <ParametroFila key={`${p.clave}:${p.origen}:${String(p.valor)}`} parametro={p} onCambiado={alCambiar} />
              ))}
            </ul>
          </SectionCard>
        ))
      )}

      <SectionCard titulo="Otros ajustes" descripcion="Se editan en su propia pantalla porque tienen reglas entre sí.">
        <div className="flex flex-wrap items-center gap-3 px-4 py-4 sm:px-5">
          <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-status-neutral-soft text-status-neutral-ink">
            <Calculator className="size-[1.1rem]" aria-hidden />
          </span>
          <div className="min-w-0 flex-1 space-y-0.5">
            <p className="text-sm font-semibold">Ajustes de precios y topes diarios</p>
            <p className="text-sm text-muted-foreground">
              Márgenes, envío estimado, redondeo y cuántas redacciones y pruebas con IA se permiten por día.
            </p>
          </div>
          <AjustesPreciosDialog trigger={<Button variant="outline">Abrir ajustes</Button>} />
        </div>
      </SectionCard>

      <HistorialParametros
        cambios={historial.data}
        error={historial.error}
        cargando={historial.cargando}
        recargar={historial.recargar}
        parametros={todos}
      />
    </>
  );
}
