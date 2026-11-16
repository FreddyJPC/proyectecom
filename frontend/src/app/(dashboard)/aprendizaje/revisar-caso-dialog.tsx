"use client";

import { Loader2 } from "lucide-react";
import { useState, type ReactNode } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { apiFetch, ApiError } from "@/lib/api";
import { formatHora } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { CasoAprendizaje, ResumenAprendizaje } from "@/types/aprendizaje";

const ROLES: Record<string, string> = { cliente: "Cliente", bot: "Victoria", humano: "Tú", sistema: "Aviso interno" };

/** Leer el caso (los últimos mensajes) y anotar qué se hizo con él. */
export function RevisarCasoDialog({
  caso,
  acciones,
  trigger,
  onRevisado,
}: {
  caso: CasoAprendizaje;
  acciones: ResumenAprendizaje["acciones"];
  trigger: ReactNode;
  onRevisado: () => void;
}) {
  const [abierto, setAbierto] = useState(false);
  const [estado, setEstado] = useState<string>(caso.estado === "pendiente" ? "revisado" : caso.estado);
  const [accion, setAccion] = useState<string>(caso.accion ?? "ninguna");
  const [categoria, setCategoria] = useState(caso.categoria ?? "");
  const [nota, setNota] = useState(caso.nota ?? "");
  const [guardando, setGuardando] = useState(false);

  async function guardar() {
    setGuardando(true);
    try {
      await apiFetch(`/aprendizaje/${caso.id}`, {
        method: "PATCH",
        body: JSON.stringify({ estado, accion: estado === "pendiente" ? null : accion, categoria: categoria.trim() || null, nota: nota.trim() || null }),
      });
      toast.success("Caso guardado.");
      setAbierto(false);
      onRevisado();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo guardar.");
    } finally {
      setGuardando(false);
    }
  }

  return (
    <Dialog open={abierto} onOpenChange={setAbierto}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent className="max-h-[92dvh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{caso.tipoNombre}</DialogTitle>
          <DialogDescription>{caso.motivo}</DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 py-2">
          {caso.mensajes.length > 0 && (
            <section aria-label="Últimos mensajes" className="max-h-64 space-y-2 overflow-y-auto rounded-lg bg-muted p-3">
              {caso.mensajes.map((m, i) => (
                <div key={i} className={cn("text-sm", m.rol === "cliente" ? "" : "text-muted-foreground")}>
                  <span className="font-medium text-foreground">{ROLES[m.rol] ?? m.rol}</span>
                  {m.en ? <span className="text-xs"> · {formatHora(m.en)}</span> : null}
                  <p className="whitespace-pre-wrap break-words">{m.texto}</p>
                </div>
              ))}
            </section>
          )}

          <div className="grid gap-4">
            <div className="grid min-w-0 gap-1.5">
              <Label htmlFor={`caso-estado-${caso.id}`}>Resultado</Label>
              <Select value={estado} onValueChange={setEstado} disabled={guardando}>
                <SelectTrigger id={`caso-estado-${caso.id}`} className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="resuelto">Mejorado</SelectItem>
                  <SelectItem value="revisado">Revisado, sin cambios todavía</SelectItem>
                  <SelectItem value="descartado">No había nada que mejorar</SelectItem>
                  <SelectItem value="pendiente">Dejar por revisar</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid min-w-0 gap-1.5">
              <Label htmlFor={`caso-accion-${caso.id}`}>Qué se hizo</Label>
              <Select value={accion} onValueChange={setAccion} disabled={guardando || estado === "pendiente"}>
                <SelectTrigger id={`caso-accion-${caso.id}`} className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {acciones.map((a) => (
                    <SelectItem key={a.accion} value={a.accion}>
                      {a.nombre}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor={`caso-categoria-${caso.id}`}>
              Categoría <span className="font-normal text-muted-foreground">(opcional)</span>
            </Label>
            <Input id={`caso-categoria-${caso.id}`} value={categoria} onChange={(e) => setCategoria(e.target.value)} maxLength={80} placeholder="Ej.: pregunta de compatibilidad" disabled={guardando} />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor={`caso-nota-${caso.id}`}>
              Nota <span className="font-normal text-muted-foreground">(opcional)</span>
            </Label>
            <Textarea id={`caso-nota-${caso.id}`} rows={2} value={nota} onChange={(e) => setNota(e.target.value)} maxLength={1000} disabled={guardando} />
          </div>
        </div>

        <DialogFooter>
          <DialogClose asChild>
            <Button type="button" variant="outline" disabled={guardando}>
              Cancelar
            </Button>
          </DialogClose>
          <Button type="button" onClick={() => void guardar()} disabled={guardando}>
            {guardando ? <Loader2 className="animate-spin" /> : null} Guardar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
