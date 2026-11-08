"use client";

import { Loader2, RotateCcw, TriangleAlert } from "lucide-react";
import { useId, useState } from "react";
import { toast } from "sonner";

import { StatusBadge } from "@/components/status-badge";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { ApiError, apiFetch } from "@/lib/api";
import { tiempoRelativo } from "@/lib/format";
import { borradorInicial, formatearValor, haCambiado, revisarBorrador, type Borrador } from "@/lib/parametros";
import type { OrigenParametro, Parametro } from "@/types/parametros";

const ORIGEN: Record<OrigenParametro, { label: string; variant: "info" | "neutral" }> = {
  app: { label: "Cambiado en la app", variant: "info" },
  servidor: { label: "Valor del servidor", variant: "neutral" },
  original: { label: "Valor original", variant: "neutral" },
};

/** Un parámetro: qué es, para qué sirve, su control y sus botones. Lo escrito es un
 * borrador hasta pulsar «Guardar»; los parámetros sensibles piden confirmación antes. */
export function ParametroFila({ parametro: p, onCambiado }: { parametro: Parametro; onCambiado: () => void }) {
  const id = useId();
  const [borrador, setBorrador] = useState<Borrador>(() => borradorInicial(p));
  const [tocado, setTocado] = useState(false);
  const [trabajando, setTrabajando] = useState<"guardando" | "restaurando" | null>(null);
  const [errorServidor, setErrorServidor] = useState<string | null>(null);
  const [confirmando, setConfirmando] = useState<"guardar" | "restaurar" | null>(null);

  const revision = revisarBorrador(p, borrador);
  const cambiado = haCambiado(p, revision);
  const errorVisible = tocado ? revision.error : null;
  const ocupado = trabajando !== null;

  async function ejecutar(accion: "guardar" | "restaurar") {
    setConfirmando(null);
    setErrorServidor(null);
    setTrabajando(accion === "guardar" ? "guardando" : "restaurando");
    try {
      const ruta = `/parametros/${encodeURIComponent(p.clave)}`;
      if (accion === "guardar") {
        await apiFetch<Parametro>(ruta, { method: "PUT", body: JSON.stringify({ valor: revision.valor }) });
        toast.success(`«${p.nombre}» guardado.`, { description: p.aplica });
      } else {
        await apiFetch<Parametro>(ruta, { method: "DELETE" });
        toast.success(`«${p.nombre}» volvió a su valor original.`);
      }
      onCambiado();
    } catch (err) {
      const mensaje = err instanceof ApiError ? err.message : "No se pudo conectar con el servidor.";
      setErrorServidor(mensaje);
      toast.error("No se pudo guardar el cambio.", { description: mensaje });
    } finally {
      setTrabajando(null);
    }
  }

  function pedirGuardar() {
    setTocado(true);
    if (revision.valor === null || !cambiado) return;
    if (p.sensible) setConfirmando("guardar");
    else void ejecutar("guardar");
  }

  const idControl = `${id}-control`;
  const idAyuda = `${id}-ayuda`;
  const idError = `${id}-error`;
  const describedBy = [idAyuda, errorVisible ? idError : null].filter(Boolean).join(" ");

  const notaDeLaOpcion = p.tipo === "opcion" ? p.opciones.find((o) => o.valor === borrador)?.nota : undefined;
  // Un valor que viene del servidor y no está en la lista cerrada igual debe poder mostrarse.
  const opciones =
    p.tipo === "opcion" && !p.opciones.some((o) => o.valor === p.valor)
      ? [{ valor: String(p.valor), etiqueta: `${p.valor} (configurado en el servidor)`, nota: "" }, ...p.opciones]
      : p.opciones;

  return (
    <li className="grid grid-cols-[minmax(0,1fr)] gap-3 px-4 py-4 sm:px-5">
      <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1.5">
        <h3 className="text-sm font-semibold">{p.nombre}</h3>
        <StatusBadge label={ORIGEN[p.origen].label} variant={ORIGEN[p.origen].variant} />
      </div>

      <p id={idAyuda} className="text-sm text-pretty text-muted-foreground">
        {p.paraQueSirve}
      </p>

      {p.avisos.length > 0 && (
        <ul className="grid gap-1.5" aria-label="Avisos de este parámetro">
          {p.avisos.map((aviso) => (
            <li key={aviso} className="flex items-start gap-2 rounded-lg bg-status-warning-soft p-2.5 text-xs text-status-warning-ink">
              <TriangleAlert className="mt-0.5 size-3.5 shrink-0" aria-hidden />
              <span>{aviso}</span>
            </li>
          ))}
        </ul>
      )}

      {/* ----------------------------------------------------------- control */}
      <div className="grid grid-cols-[minmax(0,1fr)] gap-1.5">
        {p.tipo === "booleano" && (
          <div className="flex items-center gap-3">
            <Switch
              id={idControl}
              checked={borrador === true}
              onCheckedChange={(valor) => setBorrador(valor)}
              disabled={ocupado}
              aria-describedby={idAyuda}
            />
            <Label htmlFor={idControl} className="text-sm font-medium">
              {borrador === true ? "Encendido" : "Apagado"}
            </Label>
          </div>
        )}

        {p.tipo === "entero" && (
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
            <Label htmlFor={idControl} className="sr-only">
              {p.nombre}
            </Label>
            <Input
              id={idControl}
              inputMode="numeric"
              autoComplete="off"
              value={String(borrador)}
              onChange={(e) => setBorrador(e.target.value)}
              onBlur={() => setTocado(true)}
              disabled={ocupado}
              aria-invalid={errorVisible ? true : undefined}
              aria-describedby={describedBy}
              className="w-28 tabular"
            />
            <span className="text-sm text-muted-foreground">
              {p.unidad} (de {p.minimo} a {p.maximo})
            </span>
          </div>
        )}

        {p.tipo === "texto" && (
          <>
            <Label htmlFor={idControl} className="sr-only">
              {p.nombre}
            </Label>
            <Textarea
              id={idControl}
              rows={3}
              value={String(borrador)}
              onChange={(e) => setBorrador(e.target.value)}
              onBlur={() => setTocado(true)}
              disabled={ocupado}
              aria-invalid={errorVisible ? true : undefined}
              aria-describedby={describedBy}
            />
            {p.largoMaximo != null && (
              <p className="tabular text-right text-xs text-muted-foreground">
                {String(borrador).trim().length}/{p.largoMaximo}
              </p>
            )}
          </>
        )}

        {p.tipo === "opcion" && (
          <>
            <Label htmlFor={idControl} className="sr-only">
              {p.nombre}
            </Label>
            <Select value={String(borrador)} onValueChange={setBorrador} disabled={ocupado}>
              <SelectTrigger id={idControl} className="w-full sm:w-80" aria-describedby={idAyuda}>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {opciones.map((o) => (
                  <SelectItem key={o.valor} value={o.valor}>
                    {o.etiqueta}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {notaDeLaOpcion && <p className="text-xs text-muted-foreground">{notaDeLaOpcion}</p>}
          </>
        )}

        {errorVisible && (
          <p id={idError} role="alert" className="text-xs font-medium text-status-danger-ink">
            {errorVisible}
          </p>
        )}
        {errorServidor && (
          <p role="alert" className="text-xs font-medium text-status-danger-ink">
            {errorServidor}
          </p>
        )}
      </div>

      {p.sensible && p.aviso && (
        <p className="flex items-start gap-2 text-xs text-status-warning-ink">
          <TriangleAlert className="mt-0.5 size-3.5 shrink-0" aria-hidden />
          <span>{p.aviso}</span>
        </p>
      )}

      {/* ------------------------------------------------------------- datos */}
      <dl className="grid gap-x-4 gap-y-0.5 text-xs text-muted-foreground sm:grid-cols-[auto_minmax(0,1fr)]">
        <dt className="font-medium">Valor original</dt>
        <dd className="min-w-0 break-words">
          {formatearValor(p, p.valorOriginal)}
          {p.valorServidor !== null && p.variableServidor && <> (viene de la variable {p.variableServidor} del servidor)</>}
        </dd>
        <dt className="font-medium">Se aplica</dt>
        <dd>{p.aplica}</dd>
        {p.origen === "app" && (
          <>
            <dt className="font-medium">Último cambio</dt>
            <dd className="min-w-0 break-words">
              {p.actualizadoPor ?? "Alguien"} · {tiempoRelativo(p.actualizadoEn)}
            </dd>
          </>
        )}
      </dl>

      {/* ----------------------------------------------------------- botones */}
      <div className="flex flex-wrap items-center gap-2">
        <Button type="button" onClick={pedirGuardar} disabled={ocupado || !cambiado || revision.valor === null}>
          {trabajando === "guardando" && <Loader2 className="animate-spin" aria-hidden />}
          Guardar
        </Button>
        {p.origen === "app" && (
          <Button type="button" variant="outline" onClick={() => (p.sensible ? setConfirmando("restaurar") : void ejecutar("restaurar"))} disabled={ocupado}>
            {trabajando === "restaurando" ? <Loader2 className="animate-spin" aria-hidden /> : <RotateCcw aria-hidden />}
            Restaurar original
          </Button>
        )}
        {cambiado && !ocupado && (
          <Button type="button" variant="ghost" onClick={() => { setBorrador(borradorInicial(p)); setTocado(false); setErrorServidor(null); }}>
            Descartar cambio
          </Button>
        )}
      </div>

      {/* ------------------------------------------------------ confirmación */}
      <AlertDialog open={confirmando !== null} onOpenChange={(abierto) => !abierto && setConfirmando(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {confirmando === "restaurar" ? `¿Volver «${p.nombre}» a su valor original?` : `¿Cambiar «${p.nombre}»?`}
            </AlertDialogTitle>
            <AlertDialogDescription asChild>
              <div className="space-y-2 text-sm">
                {confirmando === "restaurar" ? (
                  <p>
                    Pasará de <strong>{formatearValor(p, p.valor)}</strong> a <strong>{formatearValor(p, p.valorOriginal)}</strong>.
                  </p>
                ) : (
                  <p>
                    Pasará de <strong>{formatearValor(p, p.valor)}</strong> a <strong>{formatearValor(p, revision.valor)}</strong>.
                  </p>
                )}
                {p.aviso && <p>{p.aviso}</p>}
                <p>{p.aplica}</p>
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction onClick={() => void ejecutar(confirmando === "restaurar" ? "restaurar" : "guardar")}>
              {confirmando === "restaurar" ? "Sí, restaurar" : "Sí, cambiar"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </li>
  );
}
