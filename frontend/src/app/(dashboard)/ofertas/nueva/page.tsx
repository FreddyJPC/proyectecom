"use client";

import { PageHeader } from "@/components/app/page-header";

import { FormularioOferta } from "../formulario-oferta";

export default function NuevaOfertaPage() {
  return (
    <>
      <PageHeader title="Nueva oferta" description="Un combo o una promoción con su precio." />
      <FormularioOferta />
    </>
  );
}
