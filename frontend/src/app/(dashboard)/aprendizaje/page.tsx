"use client";

import { ClipboardCheck, GraduationCap, MessageSquareWarning, TrendingUp } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { EmptyState } from "@/components/app/empty-state";
import { FilterChips, type Chip } from "@/components/app/filter-chips";
import { InfoButton } from "@/components/app/info-button";
import { ListSkeleton } from "@/components/app/list-skeleton";
import { PageHeader } from "@/components/app/page-header";
import { PaginationBar } from "@/components/app/pagination-bar";
import { StatCard } from "@/components/app/stat-card";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useApi } from "@/hooks/use-api";
import { estadoAprendizajeInfo } from "@/lib/estados";
import { formatFechaHora } from "@/lib/format";
import type { CasoAprendizaje, ListaAprendizaje, ResumenAprendizaje } from "@/types/aprendizaje";

import { RevisarCasoDialog } from "./revisar-caso-dialog";

const POR_PAGINA = 20;

const ESTADOS: Chip[] = [
  { value: "pendiente", label: "Por revisar" },
  { value: "revisado", label: "Revisados" },
  { value: "resuelto", label: "Mejorados" },
  { value: "descartado", label: "Descartados" },
  { value: "todos", label: "Todos" },
];

const ETAPAS: Record<string, string> = {
  producto: "eligiendo producto",
  datos: "dando sus datos",
  entrega: "definiendo la entrega",
  pago: "en el pago",
  confirmacion: "confirmando el resumen",
  cierre: "al cerrar",
  postventa: "después de la compra",
};

const ORIGENES: Record<string, string> = { victoria: "Lo decidió Victoria", sistema: "Regla del sistema", dueno: "Tuviste que intervenir" };

/** «Aprendizaje de Victoria»: cada vez que se trabó, no entendió o pasó la conversación a un asesor, con el porqué y el mensaje
 * exacto del cliente. Se revisa aquí y se anota qué se mejoró. */
export default function AprendizajePage() {
  const [estado, setEstado] = useState("pendiente");
  const [tipo, setTipo] = useState("todos");
  const [pagina, setPagina] = useState(1);
  const consulta = new URLSearchParams({ pagina: String(pagina), porPagina: String(POR_PAGINA) });
  if (estado !== "todos") consulta.set("estado", estado);
  if (tipo !== "todos") consulta.set("tipo", tipo);
  const lista = useApi<ListaAprendizaje>(`/aprendizaje?${consulta.toString()}`);
  const resumen = useApi<ResumenAprendizaje>("/aprendizaje/resumen?dias=30");
  const masFrecuente = resumen.data?.porTipo[0];

  function recargar() {
    lista.recargar();
    resumen.recargar();
  }

  return (
    <>
      <PageHeader
        title="Aprendizaje de Victoria"
        description="Cuándo se trabó o pasó a un asesor, y por qué."
        info={
          <InfoButton titulo="Para qué sirve">
            <p>
              Cada vez que Victoria no entiende algo, no tiene la respuesta, pasa la conversación a un asesor o algo frena una venta, queda
              aquí un caso con el <strong>porqué</strong>, el <strong>mensaje exacto del cliente</strong> y los últimos mensajes.
            </p>
            <ul>
              <li><strong>Revísalo:</strong> lee el caso y anota qué hiciste (completar la ficha del producto, cambiar sus instrucciones, un parámetro…).</li>
              <li><strong>Lo que más se repite</strong> es lo primero que conviene mejorar.</li>
              <li>También se anota cuando tú tuviste que tomar una conversación que ella atendía.</li>
            </ul>
            <p>Las conversaciones de «Probar con Victoria» no se anotan.</p>
          </InfoButton>
        }
      />

      <div className="flex flex-col gap-5 pb-28 md:pb-6">
        <div className="grid gap-3 sm:grid-cols-3">
          <StatCard label="Por revisar" value={resumen.data?.pendientes ?? "—"} icon={ClipboardCheck} tono="warning" cargando={resumen.cargando} />
          <StatCard label="Casos en 30 días" value={resumen.data?.total ?? "—"} icon={MessageSquareWarning} tono="neutral" cargando={resumen.cargando} />
          <StatCard
            label="Lo más frecuente"
            value={masFrecuente ? masFrecuente.tipoNombre : "—"}
            hint={masFrecuente ? `${masFrecuente.cantidad} caso${masFrecuente.cantidad === 1 ? "" : "s"}` : undefined}
            icon={TrendingUp}
            tono="info"
            cargando={resumen.cargando}
          />
        </div>

        <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
          <FilterChips
            chips={ESTADOS}
            value={estado}
            onChange={(v) => {
              setEstado(v);
              setPagina(1);
            }}
            label="Filtrar por revisión"
          />
          <div className="grid gap-1.5 md:w-64">
            <Label htmlFor="filtro-tipo">Motivo</Label>
            <Select
              value={tipo}
              onValueChange={(v) => {
                setTipo(v);
                setPagina(1);
              }}
            >
              <SelectTrigger id="filtro-tipo" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="todos">Todos los motivos</SelectItem>
                {(resumen.data?.tipos ?? []).map((t) => (
                  <SelectItem key={t.tipo} value={t.tipo}>
                    {t.nombre}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        {lista.cargando ? (
          <ListSkeleton />
        ) : lista.error ? (
          <EmptyState
            icon={GraduationCap}
            tone="danger"
            title="No se pudieron cargar los casos"
            description={lista.error}
            action={
              <Button variant="outline" onClick={lista.recargar}>
                Reintentar
              </Button>
            }
          />
        ) : !lista.data || lista.data.casos.length === 0 ? (
          <EmptyState
            icon={GraduationCap}
            title={estado === "pendiente" ? "No hay casos por revisar" : "No hay casos aquí"}
            description="Aparecerán cuando Victoria pase una conversación a un asesor o algo frene una venta."
          />
        ) : (
          <>
            <ul className="grid gap-3">
              {lista.data.casos.map((c) => (
                <li key={c.id}>
                  <TarjetaCaso caso={c} acciones={resumen.data?.acciones ?? []} onRevisado={recargar} />
                </li>
              ))}
            </ul>
            <PaginationBar page={pagina} pageSize={POR_PAGINA} total={lista.data.total} onPage={setPagina} />
          </>
        )}
      </div>
    </>
  );
}

function TarjetaCaso({ caso, acciones, onRevisado }: { caso: CasoAprendizaje; acciones: ResumenAprendizaje["acciones"]; onRevisado: () => void }) {
  return (
    <article className="rounded-xl bg-card p-4 shadow-card ring-1 ring-border">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <h2 className="font-medium">{caso.tipoNombre}</h2>
          <p className="text-xs text-muted-foreground">
            {formatFechaHora(caso.creadoEn)} · {ORIGENES[caso.origen] ?? caso.origen}
            {caso.etapa ? ` · ${ETAPAS[caso.etapa] ?? caso.etapa}` : ""}
          </p>
        </div>
        <StatusBadge {...estadoAprendizajeInfo(caso.estado)} />
      </div>
      <p className="mt-2 text-sm">{caso.motivo}</p>
      {caso.mensajeCliente && (
        <blockquote className="mt-2 rounded-lg bg-muted px-3 py-2 text-sm">
          <span className="sr-only">El cliente escribió: </span>«{caso.mensajeCliente}»
        </blockquote>
      )}
      {(caso.categoria || caso.nota) && (
        <p className="mt-2 text-xs text-muted-foreground">
          {caso.categoria ? `${caso.categoria}. ` : ""}
          {caso.nota}
        </p>
      )}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <RevisarCasoDialog
          caso={caso}
          acciones={acciones}
          onRevisado={onRevisado}
          trigger={
            <Button type="button" size="sm" variant={caso.estado === "pendiente" ? "default" : "outline"}>
              {caso.estado === "pendiente" ? "Revisar" : "Ver revisión"}
            </Button>
          }
        />
        {caso.conversacionId && (
          <Button asChild size="sm" variant="ghost">
            <Link href={`/conversaciones/${caso.conversacionId}`}>Ver conversación{caso.cliente ? ` con ${caso.cliente}` : ""}</Link>
          </Button>
        )}
      </div>
    </article>
  );
}
