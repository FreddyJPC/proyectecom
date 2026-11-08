"use client";

import { Check, Info, Loader2, RefreshCw, TriangleAlert } from "lucide-react";
import { useState, type FormEvent, type ReactNode } from "react";

import { InfoButton } from "@/components/app/info-button";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useApi } from "@/hooks/use-api";
import { apiFetch, ApiError } from "@/lib/api";
import { ETIQUETAS_CAMPOS_REDACTABLES, fuenteContenidoInfo } from "@/lib/estados";
import { cn } from "@/lib/utils";
import {
  CAMPOS_REDACTABLES,
  type AlertaContenido,
  type BorradorContenido,
  type CampoRedactable,
  type FuenteContenido,
  type GenerarContenidoInput,
  type NotasParaIA,
  type UsoIA,
} from "@/types/producto-bot";

import { Campo } from "./campo";

// Mismos límites que el backend (schemas.py): todo lo que se guarda llega al
// prompt de Victoria en CADA mensaje, así que es corto.
const LIMITE: Record<CampoRedactable, number> = {
  nombre: 120,
  descripcion: 1500,
  variantes: 300,
  preguntasFrecuentes: 3000,
  temasNoResponder: 1000,
};
const FILAS: Record<CampoRedactable, number> = { nombre: 1, descripcion: 6, variantes: 2, preguntasFrecuentes: 7, temasNoResponder: 3 };
const MAX_NOTA_CORTA = 600;
const MAX_NOTA_LARGA = 1500;

type Estado = {
  textos: Partial<Record<CampoRedactable, string>>;
  fuentes: Partial<Record<CampoRedactable, FuenteContenido>>;
  alertas: AlertaContenido[];
};

function TextoDeUso({ uso }: { uso: UsoIA | null }) {
  if (!uso) return <p className="text-xs text-muted-foreground">Consultando cuántos borradores te quedan hoy…</p>;
  return (
    <p role="status" className={cn("text-xs", uso.restantes === 0 ? "font-medium text-status-warning-ink" : "text-muted-foreground")}>
      {uso.restantes === 0
        ? `Llegaste al tope de hoy (${uso.tope} borradores). Puedes subirlo en «Ajustes de precios».`
        : `Te quedan ${uso.restantes} de ${uso.tope} borradores hoy.`}
    </p>
  );
}

function Alertas({ alertas, titulo }: { alertas: AlertaContenido[]; titulo?: string }) {
  if (alertas.length === 0) return null;
  return (
    <div className="flex items-start gap-2.5 rounded-lg bg-status-warning-soft p-3 text-sm text-status-warning-ink">
      <Info className="mt-0.5 size-4 shrink-0" aria-hidden />
      <div className="min-w-0 space-y-1">
        {titulo && <p className="font-medium">{titulo}</p>}
        <ul className="list-disc space-y-1 pl-4">
          {alertas.map((a, i) => (
            <li key={`${i}-${a.texto}`}>
              {a.texto}
              {a.origen === "verificacion" && <span className="text-xs"> (revisión automática)</span>}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

/** «Redactar con IA»: la IA propone un BORRADOR a partir de Rocketfy y tus
 * notas. Nada cambia hasta que aceptas un campo (pasa al formulario de la
 * ficha) y luego guardas la ficha: la IA nunca publica ni guarda sola. */
export function RedactarIADialog({
  sku,
  actuales,
  onAceptar,
  trigger,
}: {
  sku: string;
  /** Lo que hay ahora en el formulario de la ficha, para comparar. */
  actuales: Record<CampoRedactable, string>;
  onAceptar: (campo: CampoRedactable, valor: string) => void;
  trigger: ReactNode;
}) {
  const [abierto, setAbierto] = useState(false);
  const [notas, setNotas] = useState<NotasParaIA>({ dirigidoA: "", destacar: "", evitar: "", otrosDatos: "" });
  const [productoDeSalud, setProductoDeSalud] = useState(false);
  const [borrador, setBorrador] = useState<Estado | null>(null);
  const [aplicados, setAplicados] = useState<Partial<Record<CampoRedactable, string>>>({});
  const [generando, setGenerando] = useState<"todo" | CampoRedactable | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [usoLocal, setUsoLocal] = useState<UsoIA | null>(null);

  // Cuántos borradores quedan: se pide al abrir, y después lo manda cada respuesta.
  const usoApi = useApi<UsoIA>(abierto ? "/productos-bot/contenido/uso" : null);
  const uso = usoLocal ?? usoApi.data;
  const sinUsos = uso != null && uso.restantes <= 0;

  async function pedir(campo?: CampoRedactable) {
    setGenerando(campo ?? "todo");
    setError(null);
    const cuerpo: GenerarContenidoInput = { notas, productoDeSalud, ...(campo ? { campos: [campo] } : {}) };
    try {
      const res = await apiFetch<BorradorContenido>(`/productos-bot/${encodeURIComponent(sku)}/contenido/generar`, {
        method: "POST",
        body: JSON.stringify(cuerpo),
      });
      setUsoLocal(res.uso);
      setBorrador((previo) => {
        if (!campo || !previo) return { textos: { ...res.campos }, fuentes: { ...res.fuentes }, alertas: res.alertas };
        // «Regenerar» un campo: se reemplaza solo ese campo y sus alertas.
        const conservadas = previo.alertas.filter((a) => a.campo !== campo);
        const nuevasGenerales = res.alertas.filter((a) => a.campo === null && !conservadas.some((c) => c.campo === null && c.texto === a.texto));
        return {
          textos: { ...previo.textos, ...res.campos },
          fuentes: { ...previo.fuentes, ...res.fuentes },
          alertas: [...conservadas, ...res.alertas.filter((a) => a.campo === campo), ...nuevasGenerales],
        };
      });
      setAplicados((previos) => {
        if (!campo) return {};
        const copia = { ...previos };
        delete copia[campo];
        return copia;
      });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo conectar con el servidor.");
      if (err instanceof ApiError && err.status === 429) usoApi.recargar();
    } finally {
      setGenerando(null);
    }
  }

  function aceptar(campo: CampoRedactable) {
    const valor = (borrador?.textos[campo] ?? "").trim();
    if (campo === "nombre" && !valor) return;
    onAceptar(campo, valor);
    setAplicados((previos) => ({ ...previos, [campo]: valor }));
  }

  function aceptarTodo() {
    if (!borrador) return;
    for (const campo of CAMPOS_REDACTABLES) {
      const valor = borrador.textos[campo];
      if (valor === undefined || aplicados[campo] === valor.trim()) continue;
      if (campo === "nombre" && !valor.trim()) continue;
      aceptar(campo);
    }
  }

  function enviarNotas(e: FormEvent) {
    // Este cuadro vive dentro de la ficha (otro formulario): sin esto, React haría subir el
    // «enviar» y guardaría también la ficha.
    e.preventDefault();
    e.stopPropagation();
    if (!sinUsos && generando === null) void pedir();
  }

  const camposDelBorrador = borrador ? CAMPOS_REDACTABLES.filter((c) => borrador.textos[c] !== undefined) : [];
  const generales = borrador?.alertas.filter((a) => a.campo === null) ?? [];
  const pendientes = camposDelBorrador.filter((c) => aplicados[c] !== (borrador?.textos[c] ?? "").trim());

  return (
    <Dialog
      open={abierto}
      onOpenChange={(v) => {
        setAbierto(v);
        // Lo escrito y el borrador se conservan al cerrar y abrir; un error viejo no.
        if (v) setError(null);
      }}
    >
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent className="max-h-[92dvh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <div className="flex items-center gap-1 pr-8">
            <DialogTitle>Redactar con IA</DialogTitle>
            <InfoButton titulo="Cómo funciona «Redactar con IA»">
              <p>La IA propone un borrador con lo que dice Rocketfy y lo que tú le cuentes. No inventa datos: marca de dónde sale cada texto y avisa de lo que no pudo comprobar.</p>
              <ul>
                <li>
                  <strong>Nada cambia solo:</strong> cada campo que aceptas pasa al formulario de la ficha, y recién se guarda cuando guardas la ficha. La IA nunca publica ni guarda por su cuenta.
                </li>
                <li>
                  <strong>Cuántos borradores:</strong> cada uno cuenta para un tope diario que se reinicia a medianoche. Puedes subirlo en «Ajustes de precios».
                </li>
                <li>
                  <strong>La revisión final siempre es tuya:</strong> revisa los textos antes de aceptarlos.
                </li>
              </ul>
            </InfoButton>
          </div>
          <DialogDescription>
            La IA propone un borrador. <strong className="font-medium text-foreground">Nada cambia hasta que aceptes cada campo y guardes la ficha.</strong>
          </DialogDescription>
        </DialogHeader>

        {borrador === null ? (
          <form onSubmit={enviarNotas} noValidate className="grid gap-4">
            <Campo id="ia-dirigidoA" label="¿A quién va dirigido?" opcional contador={{ actual: notas.dirigidoA.length, maximo: MAX_NOTA_CORTA }}>
              <Input id="ia-dirigidoA" value={notas.dirigidoA} maxLength={MAX_NOTA_CORTA} onChange={(e) => setNotas({ ...notas, dirigidoA: e.target.value })} />
            </Campo>
            <Campo id="ia-destacar" label="¿Qué quieres destacar?" opcional contador={{ actual: notas.destacar.length, maximo: MAX_NOTA_CORTA }}>
              <Textarea id="ia-destacar" rows={2} value={notas.destacar} maxLength={MAX_NOTA_CORTA} onChange={(e) => setNotas({ ...notas, destacar: e.target.value })} />
            </Campo>
            <Campo id="ia-evitar" label="¿Qué debe evitar?" opcional contador={{ actual: notas.evitar.length, maximo: MAX_NOTA_CORTA }}>
              <Textarea id="ia-evitar" rows={2} value={notas.evitar} maxLength={MAX_NOTA_CORTA} onChange={(e) => setNotas({ ...notas, evitar: e.target.value })} />
            </Campo>
            <Campo
              id="ia-otrosDatos"
              label="Otros datos que sepas del producto"
              opcional
              ayuda="Medidas, qué incluye, garantía, materiales…"
              info={
                <InfoButton titulo="Otros datos que sepas del producto">
                  <p>Además de lo que dice Rocketfy, esto es lo único que la IA puede usar como hechos.</p>
                  <p>Si un dato no está aquí ni en Rocketfy, la IA no lo dirá: así no inventa medidas, garantías ni materiales.</p>
                </InfoButton>
              }
              contador={{ actual: notas.otrosDatos.length, maximo: MAX_NOTA_LARGA }}
            >
              <Textarea id="ia-otrosDatos" rows={4} value={notas.otrosDatos} maxLength={MAX_NOTA_LARGA} onChange={(e) => setNotas({ ...notas, otrosDatos: e.target.value })} aria-describedby="ia-otrosDatos-ayuda" />
            </Campo>

            <div className="flex min-h-12 items-start gap-3 rounded-lg border bg-card p-3">
              <Checkbox id="ia-salud" checked={productoDeSalud} onCheckedChange={(c) => setProductoDeSalud(c === true)} className="mt-0.5" />
              <Label htmlFor="ia-salud" className="block min-w-0 flex-1 cursor-pointer text-sm font-medium leading-snug">
                Es un producto de salud, bienestar o un suplemento
              </Label>
              <InfoButton titulo="Productos de salud o bienestar">
                <p>Si marcas esta casilla, la IA aplica una regla estricta: nada de beneficios ni promesas de resultados.</p>
                <p>Además, la app marca cualquier frase de ese tipo que se le cuele al borrador. La revisión final siempre es tuya.</p>
              </InfoButton>
            </div>

            {error && (
              <div role="alert" className="flex items-start gap-2.5 rounded-lg bg-status-danger-soft p-3 text-sm text-status-danger-ink">
                <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
                <p className="font-medium">{error}</p>
              </div>
            )}

            <TextoDeUso uso={uso} />

            <DialogFooter>
              <DialogClose asChild>
                <Button variant="outline" type="button" disabled={generando !== null}>
                  Cancelar
                </Button>
              </DialogClose>
              <Button type="submit" disabled={sinUsos || generando !== null}>
                {generando !== null ? (
                  <>
                    <Loader2 className="animate-spin" /> Redactando… (unos segundos)
                  </>
                ) : (
                  "Redactar borrador"
                )}
              </Button>
            </DialogFooter>
          </form>
        ) : (
          <div className="grid gap-4" aria-busy={generando !== null}>
            <Alertas alertas={generales} titulo="Para revisar antes de aceptar" />

            {camposDelBorrador.map((campo) => {
              const texto = borrador.textos[campo] ?? "";
              const fuente = fuenteContenidoInfo(borrador.fuentes[campo]);
              const alertasDelCampo = borrador.alertas.filter((a) => a.campo === campo);
              const aplicado = aplicados[campo] === texto.trim();
              const ahora = (actuales[campo] ?? "").trim();
              const id = `ia-borrador-${campo}`;
              const regenerando = generando === campo;
              return (
                <section key={campo} aria-label={ETIQUETAS_CAMPOS_REDACTABLES[campo]} className="grid gap-2 rounded-xl border p-3 sm:p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <Label htmlFor={id}>{ETIQUETAS_CAMPOS_REDACTABLES[campo]}</Label>
                    <span title={fuente.ayuda}>
                      <StatusBadge label={fuente.label} variant={fuente.variant} />
                    </span>
                  </div>

                  {campo === "nombre" ? (
                    <Input
                      id={id}
                      value={texto}
                      maxLength={LIMITE[campo]}
                      onChange={(e) => setBorrador({ ...borrador, textos: { ...borrador.textos, [campo]: e.target.value } })}
                    />
                  ) : (
                    <Textarea
                      id={id}
                      rows={FILAS[campo]}
                      value={texto}
                      maxLength={LIMITE[campo]}
                      onChange={(e) => setBorrador({ ...borrador, textos: { ...borrador.textos, [campo]: e.target.value } })}
                    />
                  )}
                  <p className="tabular text-right text-xs text-muted-foreground">
                    {texto.length}/{LIMITE[campo]}
                  </p>

                  <Alertas alertas={alertasDelCampo} />

                  {ahora && ahora !== texto.trim() && (
                    <p className="text-xs text-muted-foreground">
                      <span className="font-medium">Ahora en la ficha:</span> <span className="line-clamp-2 break-words">{ahora}</span>
                    </p>
                  )}

                  <div className="flex flex-wrap items-center gap-2">
                    <Button type="button" size="sm" variant={aplicado ? "secondary" : "default"} disabled={aplicado || (campo === "nombre" && !texto.trim()) || generando !== null} onClick={() => aceptar(campo)}>
                      {aplicado ? (
                        <>
                          <Check /> Aplicado a la ficha
                        </>
                      ) : (
                        "Aceptar"
                      )}
                    </Button>
                    <Button type="button" size="sm" variant="outline" disabled={sinUsos || generando !== null} onClick={() => void pedir(campo)}>
                      {regenerando ? <Loader2 className="animate-spin" /> : <RefreshCw />}
                      {regenerando ? "Redactando…" : "Regenerar"}
                    </Button>
                    {aplicado && <span className="text-xs text-muted-foreground">Falta guardar la ficha.</span>}
                  </div>
                </section>
              );
            })}

            {error && (
              <div role="alert" className="flex items-start gap-2.5 rounded-lg bg-status-danger-soft p-3 text-sm text-status-danger-ink">
                <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
                <p className="font-medium">{error}</p>
              </div>
            )}

            <TextoDeUso uso={uso} />

            <DialogFooter>
              <Button type="button" variant="outline" disabled={generando !== null} onClick={() => setBorrador(null)}>
                Cambiar las notas
              </Button>
              <Button type="button" variant="outline" disabled={generando !== null || pendientes.length === 0} onClick={aceptarTodo}>
                Aceptar todo
              </Button>
              <DialogClose asChild>
                <Button type="button" disabled={generando !== null}>
                  Listo
                </Button>
              </DialogClose>
            </DialogFooter>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
