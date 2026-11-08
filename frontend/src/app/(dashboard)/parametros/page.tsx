"use client";

import { Calculator, MessageSquareText, SlidersHorizontal, TriangleAlert } from "lucide-react";
import Link from "next/link";

import { EmptyState } from "@/components/app/empty-state";
import { InfoButton } from "@/components/app/info-button";
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
        description="Controla cómo trabaja el sistema, sin tocar el servidor."
        info={
          <InfoButton titulo="Cómo funcionan los parámetros">
            <p>
              Desde aquí controlas cómo trabaja el sistema <strong>sin tocar el servidor ni pedir un cambio de código</strong>. Cada ajuste explica para qué sirve
              con su propio botón ⓘ.
            </p>
            <h3>Qué valor se usa</h3>
            <ol>
              <li>
                <strong>Lo que guardes aquí.</strong>
              </li>
              <li>Si no hay nada guardado, la variable equivalente del servidor (Railway), si existe.</li>
              <li>Si tampoco, el valor original que trae el programa.</li>
            </ol>
            <p>Mientras no guardes nada aquí, todo funciona como antes.</p>
            <h3>Cambios y seguridad</h3>
            <ul>
              <li>Cada cambio queda anotado en el historial, al final de la pantalla.</li>
              <li>Siempre puedes volver al valor original con «Restaurar original».</li>
              <li>Los ajustes sensibles piden confirmación antes de guardarse.</li>
            </ul>
          </InfoButton>
        }
      />

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

      <SectionCard
        titulo="Otros ajustes"
        descripcion="Se editan en su propia pantalla."
        info={
          <InfoButton titulo="Por qué estos ajustes van aparte">
            <p>
              Estos ajustes tienen <strong>reglas entre sí</strong> (por ejemplo, un margen mínimo no puede ser mayor que el objetivo, o un texto de Victoria tiene que
              pasar una revisión antes de publicarse), así que se editan en su propia pantalla, con sus validaciones y su prueba.
            </p>
          </InfoButton>
        }
      >
        <div className="flex flex-wrap items-center gap-3 border-b px-4 py-4 sm:px-5">
          <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-status-neutral-soft text-status-neutral-ink">
            <MessageSquareText className="size-[1.1rem]" aria-hidden />
          </span>
          <div className="min-w-0 flex-1 space-y-0.5">
            <p className="text-sm font-semibold">Instrucciones de Victoria</p>
            <p className="text-sm text-muted-foreground">Su personalidad, su objetivo y sus reglas.</p>
          </div>
          <Button asChild variant="outline">
            <Link href="/parametros/instrucciones">Abrir instrucciones</Link>
          </Button>
        </div>
        <div className="flex flex-wrap items-center gap-3 px-4 py-4 sm:px-5">
          <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-status-neutral-soft text-status-neutral-ink">
            <Calculator className="size-[1.1rem]" aria-hidden />
          </span>
          <div className="min-w-0 flex-1 space-y-0.5">
            <p className="text-sm font-semibold">Ajustes de precios y topes diarios</p>
            <p className="text-sm text-muted-foreground">Márgenes, envío, redondeo y topes de IA por día.</p>
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
