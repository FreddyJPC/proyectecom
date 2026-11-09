"use client";

import { Link2, Megaphone, TriangleAlert } from "lucide-react";
import { useState } from "react";

import { EmptyState } from "@/components/app/empty-state";
import { FilterChips, type Chip } from "@/components/app/filter-chips";
import { InfoAviso, InfoButton } from "@/components/app/info-button";
import { ListSkeleton } from "@/components/app/list-skeleton";
import { PageHeader } from "@/components/app/page-header";
import { SectionCard } from "@/components/app/section-card";
import { Button } from "@/components/ui/button";
import { useApi } from "@/hooks/use-api";
import type { Anuncio, PeriodoAnuncios, ResumenOrigenes } from "@/types/anuncios";
import type { ProductoBotResumen } from "@/types/producto-bot";

import { AnuncioCard } from "./anuncio-card";
import { ResumenOrigenesCard } from "./resumen-origenes";
import { VincularAnuncioDialog } from "./vincular-dialog";

const PERIODOS: Chip[] = [
  { value: "7", label: "7 días" },
  { value: "30", label: "30 días" },
  { value: "90", label: "90 días" },
  { value: "todo", label: "Todo" },
];

/** Anuncios (Click-to-WhatsApp): de dónde vienen tus clientes, qué vende cada anuncio y con qué producto se vincula. */
export default function AnunciosPage() {
  const [periodo, setPeriodo] = useState<PeriodoAnuncios>("30");
  const resumen = useApi<ResumenOrigenes>(`/anuncios/resumen?dias=${periodo}`);
  const anuncios = useApi<Anuncio[]>(`/anuncios?dias=${periodo}`);
  const productos = useApi<ProductoBotResumen[]>("/productos-bot");

  const lista = anuncios.data ?? [];
  const sinVincular = resumen.data?.anunciosSinVincular ?? 0;
  const recargarTodo = () => {
    resumen.recargar();
    anuncios.recargar();
  };

  const botonVincular = (
    <VincularAnuncioDialog
      productos={productos.data ?? []}
      onVinculado={recargarTodo}
      trigger={
        <Button type="button" variant="outline" size="sm">
          <Link2 /> Vincular un anuncio
        </Button>
      }
    />
  );

  return (
    <>
      <PageHeader
        title="Anuncios"
        description="De dónde vienen tus clientes y qué vende cada anuncio."
        info={
          <InfoButton titulo="Cómo funcionan los anuncios">
            <p>
              Cuando un cliente escribe <strong>tocando un anuncio</strong> de Facebook o Instagram (Click-to-WhatsApp), Meta manda los datos del anuncio y el sistema los guarda: título, texto, enlace, imagen, ID y el clic. Así sabes <strong>de dónde viene cada cliente</strong>.
            </p>
            <h3>Qué puedes hacer aquí</h3>
            <ul>
              <li>
                <strong>Vincular cada anuncio con su producto:</strong> Victoria sabe de qué hablar desde el primer mensaje, sin preguntar. Puedes hacerlo antes de que llegue el primer cliente con su ID.
              </li>
              <li>
                <strong>Medir:</strong> cuántos clientes trae cada anuncio, cuántos compran y cuánto dejan. La venta se atribuye al <strong>último anuncio</strong> por el que llegó el cliente antes de comprar.
              </li>
            </ul>
            <h3>Avisos por Telegram</h3>
            <p>Cuando llega un anuncio nuevo que no está vinculado, te avisamos por Telegram para que lo vincules.</p>
            <InfoAviso>
              <p>
                Si un cliente no llegó por un anuncio (o abrió el chat desde WhatsApp Web o de escritorio, donde Meta no manda los datos del anuncio), cuenta como <strong>directo</strong>.
              </p>
            </InfoAviso>
          </InfoButton>
        }
        actions={botonVincular}
      />

      <FilterChips chips={PERIODOS} value={periodo} onChange={(v) => setPeriodo(v as PeriodoAnuncios)} label="Periodo" />

      {sinVincular > 0 && (
        <p role="status" className="flex items-start gap-2.5 rounded-xl bg-status-warning-soft p-3.5 text-sm text-status-warning-ink">
          <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
          {sinVincular === 1 ? "Hay 1 anuncio sin vincular" : `Hay ${sinVincular} anuncios sin vincular`}: Victoria le pregunta al cliente qué producto quiere. Vincúlalos abajo.
        </p>
      )}

      <ResumenOrigenesCard resumen={resumen.data} cargando={resumen.cargando} />

      <SectionCard
        titulo="Tus anuncios"
        descripcion="Los que han traído clientes o que vinculaste de antemano."
        info={
          <InfoButton titulo="Tus anuncios">
            <p>Aparece cada anuncio por el que ha llegado al menos un cliente, y los que vinculaste con su ID aunque todavía no hayan traído a nadie. Los <strong>sin vincular</strong> van primero.</p>
            <ul>
              <li>
                <strong>Clientes:</strong> personas distintas que llegaron por ese anuncio en el periodo.
              </li>
              <li>
                <strong>Ventas, ingresos y ganancia:</strong> de las ventas cerradas en el periodo, sin contar las canceladas.
              </li>
            </ul>
          </InfoButton>
        }
      >
        {anuncios.cargando ? (
          <ListSkeleton filas={3} />
        ) : anuncios.error && !anuncios.data ? (
          <EmptyState
            icon={TriangleAlert}
            tone="danger"
            title="No se pudieron cargar los anuncios"
            description={anuncios.error}
            action={
              <Button variant="outline" onClick={anuncios.recargar}>
                Reintentar
              </Button>
            }
          />
        ) : lista.length === 0 ? (
          <EmptyState
            icon={Megaphone}
            title="Todavía no ha llegado nadie por un anuncio"
            description="Cuando alguien escriba tocando un anuncio de Click-to-WhatsApp aparecerá aquí. También puedes vincular un anuncio por su ID antes de que llegue el primero."
            action={botonVincular}
          />
        ) : (
          <ul className="divide-y">
            {lista.map((a) => (
              <AnuncioCard key={a.idAnuncio} anuncio={a} productos={productos.data ?? []} onCambio={recargarTodo} />
            ))}
          </ul>
        )}
      </SectionCard>
    </>
  );
}
