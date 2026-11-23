"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { PageHeader } from "@/components/app/page-header";
import { apiFetch, ApiError } from "@/lib/api";
import type { InmuebleDetalle } from "@/types/inmueble";

import { FichaForm } from "../ficha-form";

/** Crear una propiedad: primero lo mínimo (código, título, tipo); el resto de la ficha se completa después en su página. */
export default function NuevaPropiedadPage() {
  const router = useRouter();
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function crear(cuerpo: Record<string, unknown>) {
    setGuardando(true);
    setError(null);
    try {
      const creada = await apiFetch<InmuebleDetalle>("/inmuebles", { method: "POST", body: JSON.stringify(cuerpo) });
      toast.success("Propiedad creada. Completa su ficha.");
      router.push(`/inmuebles/${creada.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo crear la propiedad.");
      setGuardando(false);
    }
  }

  return (
    <>
      <PageHeader title="Nueva propiedad" description="Empieza con lo básico; el resto de la ficha va después." />
      <div className="pb-28 md:pb-6">
        <FichaForm guardando={guardando} error={error} onGuardar={(c) => void crear(c)} textoGuardar="Crear propiedad" />
      </div>
    </>
  );
}
