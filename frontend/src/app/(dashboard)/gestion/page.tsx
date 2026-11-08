"use client";

import { CircleCheck, ClipboardList, TriangleAlert } from "lucide-react";
import { useState } from "react";

import { EmptyState } from "@/components/app/empty-state";
import { FilterChips, type Chip } from "@/components/app/filter-chips";
import { ListSkeleton } from "@/components/app/list-skeleton";
import { PageHeader } from "@/components/app/page-header";
import { useRefrescarContadores } from "@/components/escaladas-context";
import { Button } from "@/components/ui/button";
import { useApi } from "@/hooks/use-api";
import type { Solicitud } from "@/types/gestion";

import { SolicitudCard } from "./solicitud-card";

type Vista = "pendiente" | "atendida";

/** «Por gestionar» (ADR-012): lo que espera al dueño. Un producto propio no crea el pedido solo: cuando un cliente
 * quiere comprar, ver el producto o negociar, aparece aquí. Es el REGISTRO que no se pierde; el aviso de Telegram
 * es solo el timbre. */
export default function GestionPage() {
  const [vista, setVista] = useState<Vista>("pendiente");
  const { data, error, cargando, recargar } = useApi<Solicitud[]>(`/gestion?estado=${vista}`, { intervalo: 30_000 });
  // El contador de «Pendientes» sale de una consulta aparte para que se vea aunque estés en «Atendidas».
  const pendientes = useApi<{ pendientes: number }>("/gestion/resumen", { intervalo: 30_000 });

  const chips: Chip[] = [
    { value: "pendiente", label: "Pendientes", count: pendientes.data?.pendientes, tone: "danger" },
    { value: "atendida", label: "Atendidas" },
  ];

  const refrescarMenu = useRefrescarContadores();
  const alCambiar = () => {
    recargar();
    pendientes.recargar();
    refrescarMenu(); // el contador rojo del menú también, sin esperar al siguiente poll
  };

  return (
    <>
      <PageHeader
        title="Por gestionar"
        description="Clientes que quieren comprar un producto propio o necesitan que los atiendas tú: pedidos cerrados, pedidos de ver el producto, negociaciones… Márcalos como atendidos cuando termines."
      />

      <FilterChips chips={chips} value={vista} onChange={(v) => setVista(v as Vista)} label="Filtrar por estado" />

      {error && !data ? (
        <div role="alert" className="flex flex-wrap items-center gap-3 rounded-xl border border-status-danger/30 bg-status-danger-soft p-4 text-status-danger-ink">
          <TriangleAlert className="size-5 shrink-0" aria-hidden />
          <p className="flex-1 text-sm">No se pudo cargar la lista. {error}</p>
          <Button variant="outline" size="sm" onClick={recargar} className="bg-card text-foreground">
            Reintentar
          </Button>
        </div>
      ) : cargando ? (
        <ListSkeleton filas={3} />
      ) : !data || data.length === 0 ? (
        <div className="rounded-xl border bg-card">
          <EmptyState
            icon={vista === "pendiente" ? CircleCheck : ClipboardList}
            title={vista === "pendiente" ? "No hay nada por gestionar" : "Todavía no has atendido ninguna solicitud"}
            description={
              vista === "pendiente"
                ? "Cuando un cliente quiera comprar un producto propio, o pida verlo o negociarlo, aparecerá aquí y te llegará un aviso por Telegram."
                : "Las solicitudes que marques como atendidas se guardan aquí."
            }
          />
        </div>
      ) : (
        <ul className="grid gap-3 lg:grid-cols-2">
          {data.map((s) => (
            <li key={s.id}>
              <SolicitudCard solicitud={s} onCambio={alCambiar} />
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
