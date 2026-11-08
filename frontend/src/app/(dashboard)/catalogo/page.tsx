"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { InfoButton } from "@/components/app/info-button";
import { PageHeader } from "@/components/app/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/use-api";
import type { ProductoBotResumen } from "@/types/producto-bot";
import type { SkuMonitoreado } from "@/types/producto";

import { CatalogoTab } from "./catalogo-tab";
import { MisProductosTab } from "./mis-productos-tab";
import { MonitoreadosTab } from "./monitoreados-tab";

const PESTANAS = ["catalogo", "mis-productos", "monitoreados"] as const;
type Pestana = (typeof PESTANAS)[number];

export default function CatalogoPage() {
  // useSearchParams() exige un límite <Suspense> (si no, `next build` falla).
  return (
    <Suspense fallback={<Skeleton className="h-96 w-full" />}>
      <CatalogoContenido />
    </Suspense>
  );
}

function CatalogoContenido() {
  const router = useRouter();
  const searchParams = useSearchParams();

  // La pestaña vive en la URL: al volver desde la ficha de un producto se
  // regresa a "Mis productos" y no a la primera pestaña.
  const pedida = searchParams.get("tab");
  const pestana: Pestana = PESTANAS.find((p) => p === pedida) ?? "catalogo";

  function cambiarPestana(nueva: string) {
    const p = new URLSearchParams(searchParams.toString());
    if (nueva === "catalogo") p.delete("tab");
    else p.set("tab", nueva);
    const qs = p.toString();
    router.replace(qs ? `/catalogo?${qs}` : "/catalogo", { scroll: false });
  }

  // Las listas se piden una sola vez aquí y se comparten con las pestañas: el
  // catálogo marca cuáles ya están vigilados y cuáles ya tienen ficha de
  // ventas; al cambiar algo, todas se actualizan juntas.
  const monitoreados = useApi<SkuMonitoreado[]>("/productos/monitoreados?soloActivos=false");
  const misProductos = useApi<ProductoBotResumen[]>("/productos-bot?incluirArchivados=true");
  const activos = monitoreados.data?.filter((m) => m.activo).length;
  const aLaVenta = misProductos.data?.filter((p) => p.estado === "activo").length;

  return (
    <>
      <PageHeader
        title="Catálogo y stock"
        description="Explora el catálogo, prepara lo que Victoria venderá y vigila el stock."
        info={
          <InfoButton titulo="Cómo funciona el catálogo">
            <p>Esta pantalla tiene tres pestañas:</p>
            <ul>
              <li>
                <strong>Catálogo:</strong> los productos de Rocketfy. Aquí los exploras y pulsas «Preparar para vender» en los que quieres que Victoria venda.
              </li>
              <li>
                <strong>Mis productos:</strong> los que ya preparaste, de Rocketfy y propios. Solo los que están «A la venta» los ve Victoria; el resto son borradores, pausados o archivados.
              </li>
              <li>
                <strong>Vigilados:</strong> los productos que anuncias. Te avisamos en Incidencias cuando su stock baje del mínimo que elijas o cambie su precio, para no pagar publicidad de algo agotado.
              </li>
            </ul>
            <p>Cada hora se actualizan costo y stock de los de Rocketfy, y un producto que se queda sin stock se pausa solo.</p>
          </InfoButton>
        }
      />

      <Tabs value={pestana} onValueChange={cambiarPestana} className="gap-5">
        <TabsList className="w-full sm:w-fit">
          <TabsTrigger value="catalogo" className="px-4">
            Catálogo
          </TabsTrigger>
          <TabsTrigger value="mis-productos" className="px-4">
            Mis productos{aLaVenta ? ` (${aLaVenta})` : ""}
          </TabsTrigger>
          <TabsTrigger value="monitoreados" className="px-4">
            Vigilados{activos ? ` (${activos})` : ""}
          </TabsTrigger>
        </TabsList>
        <TabsContent value="catalogo" className="flex flex-col gap-4">
          <CatalogoTab
            monitoreados={monitoreados.data ?? []}
            onCambio={monitoreados.recargar}
            misProductos={misProductos.data ?? []}
            onProductoPreparado={misProductos.recargar}
          />
        </TabsContent>
        <TabsContent value="mis-productos" className="flex flex-col gap-4">
          <MisProductosTab
            items={misProductos.data}
            cargando={misProductos.cargando}
            error={misProductos.error}
            recargar={misProductos.recargar}
            onIrAlCatalogo={() => cambiarPestana("catalogo")}
          />
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
