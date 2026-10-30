"use client";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PageHeader } from "@/components/app/page-header";
import { useApi } from "@/hooks/use-api";
import type { SkuMonitoreado } from "@/types/producto";

import { CatalogoTab } from "./catalogo-tab";
import { MonitoreadosTab } from "./monitoreados-tab";

export default function CatalogoPage() {
  // La lista de SKUs vigilados se pide una sola vez aquí y se comparte con las
  // dos pestañas: el catálogo marca cuáles ya están vigilados y la pestaña de
  // vigilados la muestra; al cambiar algo, ambas se actualizan juntas.
  const monitoreados = useApi<SkuMonitoreado[]>("/productos/monitoreados?soloActivos=false");
  const activos = monitoreados.data?.filter((m) => m.activo).length;

  return (
    <>
      <PageHeader
        title="Catálogo y stock"
        description="Explora el catálogo de Rocketfy y elige qué productos vigilar para no pagar publicidad de algo agotado."
      />

      <Tabs defaultValue="catalogo" className="gap-5">
        <TabsList className="w-full sm:w-fit">
          <TabsTrigger value="catalogo" className="px-4">
            Catálogo
          </TabsTrigger>
          <TabsTrigger value="monitoreados" className="px-4">
            Vigilados{activos ? ` (${activos})` : ""}
          </TabsTrigger>
        </TabsList>
        <TabsContent value="catalogo" className="flex flex-col gap-4">
          <CatalogoTab monitoreados={monitoreados.data ?? []} onCambio={monitoreados.recargar} />
        </TabsContent>
        <TabsContent value="monitoreados" className="flex flex-col gap-4">
          <MonitoreadosTab
            items={monitoreados.data}
            cargando={monitoreados.cargando}
            error={monitoreados.error}
            recargar={monitoreados.recargar}
          />
        </TabsContent>
      </Tabs>
    </>
  );
}
