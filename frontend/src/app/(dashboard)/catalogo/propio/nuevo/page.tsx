"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";

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
        description="Un producto que vendes tú (zapatos, ropa, lo que quieras), sin pasar por Rocketfy. Victoria lo atiende como a los demás, pero cuando el cliente decide comprar el pedido te llega a ti para que lo gestiones. Se crea como borrador: no se vende hasta que lo publiques."
      />

      <FormularioPropio />
    </>
  );
}
