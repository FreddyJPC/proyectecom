"use client";

import { Loader2, Plus } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useApi } from "@/hooks/use-api";
import { apiFetch, ApiError } from "@/lib/api";
import type { Categoria } from "@/types/producto-bot";

const SIN_CATEGORIA = "0";

/** Elige la categoría del producto (calzado, ropa…): sirve para medir qué tipo de producto deja más. Se puede
 * crear una nueva sin salir de la ficha. */
export function SelectorCategoria({
  id,
  valor,
  onCambio,
  deshabilitado,
  describedBy,
}: {
  id: string;
  valor: number | null;
  onCambio: (categoriaId: number | null) => void;
  deshabilitado?: boolean;
  describedBy?: string;
}) {
  const { data, error, recargar } = useApi<Categoria[]>("/categorias-producto");
  const [creando, setCreando] = useState(false);
  const [nombre, setNombre] = useState("");
  const [guardando, setGuardando] = useState(false);
  const categorias = data ?? [];

  async function crear() {
    const limpio = nombre.trim();
    if (!limpio) return;
    setGuardando(true);
    try {
      const nueva = await apiFetch<Categoria>("/categorias-producto", { method: "POST", body: JSON.stringify({ nombre: limpio }) });
      recargar();
      onCambio(nueva.id);
      setNombre("");
      setCreando(false);
      toast.success(`Categoría «${nueva.nombre}» creada.`);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo crear la categoría.");
    } finally {
      setGuardando(false);
    }
  }

  return (
    <div className="grid gap-2">
      <Select value={valor == null ? SIN_CATEGORIA : String(valor)} onValueChange={(v) => onCambio(v === SIN_CATEGORIA ? null : Number(v))} disabled={deshabilitado}>
        <SelectTrigger id={id} className="w-full sm:w-80" aria-describedby={describedBy}>
          <SelectValue placeholder="Sin categoría" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={SIN_CATEGORIA}>Sin categoría</SelectItem>
          {categorias.map((c) => (
            <SelectItem key={c.id} value={String(c.id)}>
              {c.nombre}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {error && <p className="text-xs text-status-warning-ink">No se pudieron cargar las categorías: {error}</p>}

      {creando ? (
        <div className="flex flex-wrap items-center gap-2">
          <Input
            aria-label="Nombre de la nueva categoría"
            value={nombre}
            maxLength={60}
            placeholder="Por ejemplo: Calzado"
            disabled={guardando}
            onChange={(e) => setNombre(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                void crear();
              }
            }}
            className="w-full sm:w-56"
          />
          <Button type="button" size="sm" disabled={guardando || !nombre.trim()} onClick={() => void crear()}>
            {guardando && <Loader2 className="animate-spin" />}
            Crear
          </Button>
          <Button type="button" size="sm" variant="ghost" disabled={guardando} onClick={() => setCreando(false)}>
            Cancelar
          </Button>
        </div>
      ) : (
        <Button type="button" variant="ghost" size="sm" className="w-fit" disabled={deshabilitado} onClick={() => setCreando(true)}>
          <Plus /> Nueva categoría
        </Button>
      )}
    </div>
  );
}
