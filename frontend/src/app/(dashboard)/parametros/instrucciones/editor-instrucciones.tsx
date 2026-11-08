"use client";

import { FlaskConical, History, Loader2, Lock, RotateCcw, Rocket, TriangleAlert } from "lucide-react";
import { useId, useState } from "react";
import { toast } from "sonner";

import { SectionCard } from "@/components/app/section-card";
import { InfoButton } from "@/components/app/info-button";
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
import { Textarea } from "@/components/ui/textarea";
import { useApi } from "@/hooks/use-api";
import { ApiError, apiFetch } from "@/lib/api";
import { formatFechaHora, tiempoRelativo } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { Instrucciones, SeccionInstrucciones, VersionInstrucciones } from "@/types/instrucciones";
import type { ProductoBotResumen } from "@/types/producto-bot";

import { ProbarConVictoria } from "../../catalogo/producto/[sku]/probar-victoria";

const RUTA = "/instrucciones-victoria";

type Confirmacion = { tipo: "publicar" } | { tipo: "original" } | { tipo: "descartar" } | { tipo: "cargar"; version: VersionInstrucciones };
type Textos = Record<string, string>;

/** Lo que muestra el editor al arrancar: el borrador si hay, y si no lo que rige hoy. */
function textosBase(d: Instrucciones): Textos {
  return Object.fromEntries(d.secciones.filter((s) => s.editable).map((s) => [s.id, s.borrador ?? s.vigente]));
}

/** Las mismas reglas que el backend (que es quien manda), para avisar sin esperar al servidor. */
function errorDe(s: SeccionInstrucciones, texto: string): string | null {
  const limpio = texto.trim();
  if (!limpio) return "No puede quedar vacía.";
  if (limpio.length > s.maximo) return `Es demasiado larga: máximo ${s.maximo} caracteres (tiene ${limpio.length}).`;
  if (/^#{1,6}\s/m.test(limpio)) return "No uses títulos con «#»: los títulos de cada sección los pone el sistema.";
  return null;
}

function etiquetaDeVersion(v: VersionInstrucciones): string {
  return `Versión ${v.id}`;
}

export function EditorInstrucciones({ data, onCambiado }: { data: Instrucciones; onCambiado: () => void }) {
  const id = useId();
  const base = textosBase(data);
  const [textos, setTextos] = useState<Textos>(base);
  const [nota, setNota] = useState("");
  const [trabajando, setTrabajando] = useState<string | null>(null);
  const [errores, setErrores] = useState<string[]>([]);
  const [confirmando, setConfirmando] = useState<Confirmacion | null>(null);
  const [skuPrueba, setSkuPrueba] = useState<string | null>(null);

  const productos = useApi<ProductoBotResumen[]>("/productos-bot");
  const paraProbar = (productos.data ?? []).filter((p) => p.estado !== "archivado");
  const productoElegido = paraProbar.find((p) => p.sku === skuPrueba) ?? paraProbar[0] ?? null;

  const editables = data.secciones.filter((s) => s.editable);
  const hayBorrador = data.borrador !== null;
  const hayCambios = editables.some((s) => textos[s.id] !== base[s.id]);
  const erroresPorSeccion = Object.fromEntries(editables.map((s) => [s.id, errorDe(s, textos[s.id] ?? "")]));
  const hayErrores = Object.values(erroresPorSeccion).some(Boolean);
  const total = data.caracteresFijos + editables.reduce((suma, s) => suma + (textos[s.id] ?? "").trim().length, 0);
  const tokens = Math.ceil(total / 4);
  const excede = total > data.maximoTotal;
  const ocupado = trabajando !== null;

  async function llamar(accion: string, ruta: string, metodo: "POST" | "PUT" | "DELETE", cuerpo: unknown, exito: string) {
    setErrores([]);
    setConfirmando(null);
    setTrabajando(accion);
    try {
      await apiFetch<Instrucciones>(`${RUTA}${ruta}`, { method: metodo, ...(cuerpo !== undefined ? { body: JSON.stringify(cuerpo) } : {}) });
      toast.success(exito);
      setNota("");
      onCambiado();
    } catch (err) {
      const mensaje = err instanceof ApiError ? err.message : "No se pudo conectar con el servidor.";
      setErrores(err instanceof ApiError && err.bloqueos.length > 0 ? [mensaje, ...err.bloqueos] : [mensaje]);
      toast.error("No se pudo completar la acción.", { description: mensaje });
    } finally {
      setTrabajando(null);
    }
  }

  const guardarBorrador = () => llamar("guardar", "/borrador", "PUT", { secciones: textos, nota: nota.trim() || null }, "Borrador guardado. Los clientes todavía no ven nada.");
  const publicar = () => llamar("publicar", "/publicar", "POST", { nota: nota.trim() || null }, "Publicado: Victoria ya usa estas instrucciones con los clientes.");
  const volverALaOriginal = () => llamar("original", "/volver-a-la-original", "POST", undefined, "Victoria volvió a usar las instrucciones originales.");
  const descartar = () => llamar("descartar", "/borrador", "DELETE", undefined, "Borrador descartado.");
  const cargarVersion = (v: VersionInstrucciones) => llamar("cargar", `/versiones/${v.id}/cargar`, "POST", undefined, `${etiquetaDeVersion(v)} cargada en el borrador. Pruébala y publícala cuando quieras.`);

  const puedeProbarOPublicar = hayBorrador && !hayCambios && !hayErrores && !excede;

  return (
    <>
      {/* ------------------------------------------------------- qué rige hoy */}
      <SectionCard
        titulo="Qué usa Victoria hoy"
        descripcion="Lo que se aplica ahora mismo con los clientes reales."
        info={
          <InfoButton titulo="Qué instrucciones usa Victoria hoy">
            <p>
              Victoria usa la <strong>versión publicada</strong> más reciente. Si todavía no publicaste nada, usa las <strong>instrucciones originales</strong>: las que trae el
              programa (un archivo del código). Mientras no publiques nada, Victoria sigue exactamente como siempre.
            </p>
            <p>«Volver a las originales» hace que use al instante el texto del programa; las versiones publicadas no se pierden.</p>
          </InfoButton>
        }
      >
        <div className="flex flex-wrap items-center gap-3 px-4 py-4 sm:px-5">
          <div className="min-w-0 flex-1 space-y-1">
            <p className="flex flex-wrap items-center gap-2 text-sm font-semibold">
              {data.usando === "publicada" && data.publicada ? (
                <>
                  <StatusBadge label="Versión publicada" variant="info" /> {etiquetaDeVersion(data.publicada)}
                </>
              ) : (
                <StatusBadge label="Instrucciones originales" variant="neutral" />
              )}
            </p>
            <p className="text-sm text-muted-foreground">
              {data.usando === "publicada" && data.publicada
                ? `Publicada ${tiempoRelativo(data.publicada.publicadaEn)} por ${data.publicada.creadoPor ?? "alguien"}${data.publicada.nota ? `: «${data.publicada.nota}»` : ""}.`
                : "Son las que trae el programa."}
            </p>
          </div>
          {data.usando === "publicada" && (
            <Button type="button" variant="outline" disabled={ocupado} onClick={() => setConfirmando({ tipo: "original" })}>
              {trabajando === "original" ? <Loader2 className="animate-spin" aria-hidden /> : <RotateCcw aria-hidden />}
              Volver a las originales
            </Button>
          )}
        </div>
      </SectionCard>

      {/* ------------------------------------------------------------ secciones */}
      <ol className="grid grid-cols-[minmax(0,1fr)] gap-4" aria-label="Secciones de las instrucciones, en el orden en que las lee Victoria">
        {data.secciones.map((s) =>
          s.editable ? (
            <li key={s.id}>
              <SeccionEditable
                seccion={s}
                idBase={`${id}-${s.id}`}
                texto={textos[s.id] ?? ""}
                error={erroresPorSeccion[s.id]}
                cambiada={(textos[s.id] ?? "").trim() !== s.vigente.trim()}
                deshabilitado={ocupado}
                onCambio={(valor) => setTextos((previos) => ({ ...previos, [s.id]: valor }))}
              />
            </li>
          ) : (
            <li key={s.id}>
              <SeccionBloqueada seccion={s} />
            </li>
          ),
        )}
      </ol>

      {/* --------------------------------------------------- borrador y acciones */}
      <SectionCard titulo="Borrador" descripcion="Los clientes no ven nada hasta que publiques.">
        <div className="grid grid-cols-[minmax(0,1fr)] gap-4 px-4 py-4 sm:px-5">
          <div className="flex items-center gap-1">
            <p role="status" className={cn("text-sm", excede ? "font-medium text-status-danger-ink" : "text-muted-foreground")}>
              Largo total: <span className="tabular font-medium">{total.toLocaleString("es-EC")}</span> de {data.maximoTotal.toLocaleString("es-EC")} caracteres (≈{" "}
              <span className="tabular">{tokens.toLocaleString("es-EC")}</span> «tokens»)
              {excede && ": te pasas del máximo"}
            </p>
            <InfoButton titulo="Por qué importa el largo de las instrucciones">
              <p>
                Las instrucciones completas se envían <strong>en cada mensaje</strong> que Victoria responde, así que cuanto más largas, <strong>más lento y más caro</strong>{" "}
                sale cada respuesta.
              </p>
              <p>
                Un «token» es el trozo de texto que cuenta la IA (≈ 4 caracteres). El máximo de {data.maximoTotal.toLocaleString("es-EC")} caracteres incluye las partes que no
                se editan (la ficha del producto, cómo usa sus herramientas, etc.).
              </p>
            </InfoButton>
          </div>

          <div className="grid gap-1.5">
            <Label htmlFor={`${id}-nota`}>
              ¿Qué cambiaste y por qué? <span className="font-normal text-muted-foreground">(opcional)</span>
            </Label>
            <Input id={`${id}-nota`} value={nota} maxLength={200} onChange={(e) => setNota(e.target.value)} disabled={ocupado} placeholder="Ej.: tono más cercano, sin emojis en las reglas" />
          </div>

          {errores.length > 0 && (
            <div role="alert" className="flex items-start gap-2.5 rounded-lg bg-status-danger-soft p-3 text-sm text-status-danger-ink">
              <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
              <ul className="min-w-0 list-none space-y-1 break-words">
                {errores.map((e, i) => (
                  <li key={i} className={i === 0 ? "font-medium" : undefined}>
                    {e}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="flex flex-wrap items-center gap-2">
            <Button type="button" onClick={guardarBorrador} disabled={ocupado || !hayCambios || hayErrores || excede}>
              {trabajando === "guardar" && <Loader2 className="animate-spin" aria-hidden />}
              Guardar borrador
            </Button>
            <Button type="button" variant="default" onClick={() => setConfirmando({ tipo: "publicar" })} disabled={ocupado || !puedeProbarOPublicar}>
              {trabajando === "publicar" ? <Loader2 className="animate-spin" aria-hidden /> : <Rocket aria-hidden />}
              Publicar
            </Button>
            {hayBorrador && (
              <Button type="button" variant="outline" onClick={() => setConfirmando({ tipo: "descartar" })} disabled={ocupado}>
                Descartar borrador
              </Button>
            )}
          </div>
          {!puedeProbarOPublicar && (
            <p className="text-xs text-muted-foreground">
              {!hayBorrador
                ? "Para probar o publicar, primero guarda un borrador."
                : hayCambios
                  ? "Tienes cambios sin guardar: guárdalos para poder probarlos o publicarlos."
                  : "Corrige lo marcado en rojo para poder publicar."}
            </p>
          )}
        </div>
      </SectionCard>

      {/* ----------------------------------------------------------------- prueba */}
      <div className="grid grid-cols-[minmax(0,1fr)] gap-3">
        {productos.cargando ? (
          <SectionCard titulo="Probar el borrador con Victoria" descripcion="Cargando tus productos…">
            <div className="p-4 text-sm text-muted-foreground" aria-busy="true">
              Un momento…
            </div>
          </SectionCard>
        ) : !productoElegido ? (
          <SectionCard titulo="Probar el borrador con Victoria" descripcion="Se prueba con la ficha de uno de tus productos.">
            <p className="flex items-start gap-2 p-4 text-sm text-muted-foreground sm:px-5">
              <FlaskConical className="mt-0.5 size-4 shrink-0" aria-hidden />
              Todavía no tienes productos para probar. Crea uno en Catálogo → Mis productos y vuelve.
            </p>
          </SectionCard>
        ) : (
          <>
            {paraProbar.length > 1 && (
              <div className="grid gap-1.5">
                <Label htmlFor={`${id}-producto`}>Producto con el que quieres probar</Label>
                <Select value={productoElegido.sku} onValueChange={setSkuPrueba}>
                  <SelectTrigger id={`${id}-producto`} className="w-full sm:w-96">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {paraProbar.map((p) => (
                      <SelectItem key={p.sku} value={p.sku}>
                        {p.nombre} ({p.sku})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
            {/* Con cambios sin guardar, o sin borrador, la prueba no tendría qué probar. */}
            <ProbarConVictoria sku={productoElegido.sku} nombre={productoElegido.nombre} sinCambiosPendientes={puedeProbarOPublicar} usarBorrador />
          </>
        )}
      </div>

      {/* --------------------------------------------------------------- historial */}
      <SectionCard
        titulo="Versiones publicadas"
        descripcion="Las que ya publicaste."
        info={
          <InfoButton titulo="Cómo volver a una versión anterior">
            <p>
              Para volver a una versión anterior: <strong>cárgala en el borrador</strong>, pruébala con «Probar con Victoria» y publícala. Así ningún cambio llega a un
              cliente sin haberse probado, tampoco volver atrás.
            </p>
          </InfoButton>
        }
      >
        {data.versiones.length === 0 ? (
          <p className="flex items-start gap-2 p-4 text-sm text-muted-foreground sm:px-5">
            <History className="mt-0.5 size-4 shrink-0" aria-hidden />
            Todavía no has publicado ninguna versión. Cuando publiques, quedará aquí.
          </p>
        ) : (
          <ul className="divide-y">
            {data.versiones.map((v) => (
              <li key={v.id} className="flex flex-wrap items-center gap-3 px-4 py-3 sm:px-5">
                <div className="min-w-0 flex-1 space-y-0.5">
                  <p className="flex flex-wrap items-center gap-2 text-sm font-medium">
                    {etiquetaDeVersion(v)}
                    {v.estado === "publicada" ? <StatusBadge label="Rige hoy" variant="success" /> : <StatusBadge label="Archivada" variant="neutral" />}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {v.creadoPor ?? "Alguien"} · <time dateTime={v.publicadaEn ?? v.creadoEn} title={formatFechaHora(v.publicadaEn ?? v.creadoEn)}>{tiempoRelativo(v.publicadaEn ?? v.creadoEn)}</time>
                    {v.nota ? ` · «${v.nota}»` : ""}
                  </p>
                </div>
                {v.estado !== "publicada" && (
                  <Button type="button" variant="outline" size="sm" disabled={ocupado} onClick={() => (hayBorrador ? setConfirmando({ tipo: "cargar", version: v }) : void cargarVersion(v))}>
                    Cargar en el borrador
                  </Button>
                )}
              </li>
            ))}
          </ul>
        )}
      </SectionCard>

      {/* ------------------------------------------------------- confirmaciones */}
      <AlertDialog open={confirmando !== null} onOpenChange={(abierto) => !abierto && setConfirmando(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {confirmando?.tipo === "publicar" && "¿Publicar estas instrucciones?"}
              {confirmando?.tipo === "original" && "¿Volver a las instrucciones originales?"}
              {confirmando?.tipo === "descartar" && "¿Descartar el borrador?"}
              {confirmando?.tipo === "cargar" && `¿Cargar la ${etiquetaDeVersion(confirmando.version).toLowerCase()}?`}
            </AlertDialogTitle>
            <AlertDialogDescription asChild>
              <div className="space-y-2 text-sm">
                {confirmando?.tipo === "publicar" && (
                  <>
                    <p>
                      Desde el siguiente mensaje, <strong>Victoria hablará con los clientes reales con este texto</strong>. Si ya lo probaste en «Probar el borrador con Victoria», adelante.
                    </p>
                    <p>La versión que rige hoy se archiva y puedes volver a ella cuando quieras. El dinero, el stock y las cantidades siguen controlados por el sistema: estas instrucciones no pueden saltarse esas reglas.</p>
                  </>
                )}
                {confirmando?.tipo === "original" && (
                  <p>
                    Victoria volverá <strong>al instante</strong> a usar el texto original del programa. Tu versión publicada se archiva y puedes cargarla de nuevo.
                  </p>
                )}
                {confirmando?.tipo === "descartar" && <p>Se borra el borrador que tienes guardado. Lo que rige con los clientes no cambia.</p>}
                {confirmando?.tipo === "cargar" && <p>Tu borrador actual se reemplaza por el de esa versión. Lo que rige con los clientes no cambia hasta que publiques.</p>}
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (!confirmando) return;
                if (confirmando.tipo === "publicar") void publicar();
                if (confirmando.tipo === "original") void volverALaOriginal();
                if (confirmando.tipo === "descartar") void descartar();
                if (confirmando.tipo === "cargar") void cargarVersion(confirmando.version);
              }}
            >
              {confirmando?.tipo === "publicar" && "Sí, publicar"}
              {confirmando?.tipo === "original" && "Sí, volver a las originales"}
              {confirmando?.tipo === "descartar" && "Sí, descartar"}
              {confirmando?.tipo === "cargar" && "Sí, cargar"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}

function SeccionEditable({
  seccion: s,
  idBase,
  texto,
  error,
  cambiada,
  deshabilitado,
  onCambio,
}: {
  seccion: SeccionInstrucciones;
  idBase: string;
  texto: string;
  error: string | null;
  cambiada: boolean;
  deshabilitado: boolean;
  onCambio: (valor: string) => void;
}) {
  const largo = texto.trim().length;
  return (
    <section className="grid grid-cols-[minmax(0,1fr)] gap-2 rounded-xl border bg-card p-4 shadow-card sm:p-5" aria-labelledby={`${idBase}-titulo`}>
      <div className="flex flex-wrap items-center gap-x-1.5 gap-y-1.5">
        <h2 id={`${idBase}-titulo`} className="text-sm font-semibold">
          {s.nombre}
        </h2>
        <InfoButton titulo={s.nombre}>
          <p>{s.ayuda}</p>
        </InfoButton>
        {cambiada && <StatusBadge label="Distinta de la que rige hoy" variant="info" />}
      </div>
      <Label htmlFor={idBase} className="sr-only">
        {s.nombre}
      </Label>
      <Textarea
        id={idBase}
        value={texto}
        rows={5}
        onChange={(e) => onCambio(e.target.value)}
        disabled={deshabilitado}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? `${idBase}-error` : undefined}
        className="max-h-[28rem] overflow-y-auto leading-relaxed"
      />
      <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-1 text-xs">
        <div className="min-w-0 space-y-1">
          {error && (
            <p id={`${idBase}-error`} role="alert" className="font-medium text-status-danger-ink">
              {error}
            </p>
          )}
          {texto.trim() !== s.original.trim() && (
            <button
              type="button"
              onClick={() => onCambio(s.original)}
              disabled={deshabilitado}
              className="inline-flex min-h-8 items-center gap-1 rounded-md px-1 font-medium text-primary outline-none hover:underline focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
            >
              <RotateCcw className="size-3" aria-hidden /> Poner el texto original de esta sección
            </button>
          )}
        </div>
        <span className={cn("tabular shrink-0 text-muted-foreground", largo > s.maximo && "font-medium text-status-danger-ink")}>
          {largo}/{s.maximo}
        </span>
      </div>
    </section>
  );
}

function SeccionBloqueada({ seccion: s }: { seccion: SeccionInstrucciones }) {
  return (
    <details className="group rounded-xl border bg-muted/40 p-4 sm:px-5">
      <summary className="flex min-h-8 cursor-pointer list-none items-center gap-2.5 rounded-md text-sm font-semibold outline-none focus-visible:ring-2 focus-visible:ring-ring [&::-webkit-details-marker]:hidden">
        <Lock className="size-4 shrink-0 text-muted-foreground" aria-hidden />
        <span className="min-w-0 flex-1">{s.nombre}</span>
        <StatusBadge label="Solo lectura" variant="neutral" />
      </summary>
      <div className="mt-3 grid grid-cols-[minmax(0,1fr)] gap-2">
        <p className="text-sm text-muted-foreground">{s.ayuda}</p>
        <pre className="max-h-72 overflow-auto whitespace-pre-wrap break-words rounded-lg border bg-card p-3 text-xs leading-relaxed text-muted-foreground" tabIndex={0}>
          {s.vigente}
        </pre>
      </div>
    </details>
  );
}
