"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";

import { InfoAviso, InfoButton } from "@/components/app/info-button";
import { PageHeader } from "@/components/app/page-header";

import { FormularioPropio } from "./formulario-propio";

export default function PublicarProductoPropioPage() {
  return (
    <>
      <Link
        href="/catalogo?tab=mis-productos"
        className="-mb-2 inline-flex min-h-10 w-fit items-center gap-1.5 rounded-md text-sm text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"
      >
        <ArrowLeft className="size-4" aria-hidden /> Mis productos
      </Link>

      <PageHeader
        title="Publicar producto propio"
        description="Un producto que vendes tú, sin pasar por Rocketfy."
        info={
          <InfoButton titulo="Qué es un producto propio">
            <p>Es un producto que vendes tú (zapatos, ropa, lo que quieras), sin pasar por Rocketfy.</p>
            <p>
              Victoria lo atiende como a los demás, pero cuando el cliente decide comprar <strong>el pedido te llega a ti</strong> («Por gestionar») para que lo gestiones: no se crea ningún pedido en Rocketfy.
            </p>
            <InfoAviso>
              <p>Se crea como borrador: no se vende hasta que lo publiques.</p>
            </InfoAviso>
          </InfoButton>
        }
      />

      <FormularioPropio />
    </>
  );
}
