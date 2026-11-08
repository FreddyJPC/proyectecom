"use client";

import { Loader2, TriangleAlert } from "lucide-react";
import { useState, type FormEvent, type ReactNode } from "react";
import { toast } from "sonner";

import { InfoEjemplo, InfoAviso, InfoButton } from "@/components/app/info-button";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/use-api";
import { apiFetch, ApiError } from "@/lib/api";
import { formatMoney, normalizarMonto, normalizarPorcentaje } from "@/lib/format";
import type { AjustesNegocio, GuardarAjustesInput } from "@/types/producto-bot";

import { Campo, descripcionDe } from "./producto/[sku]/campo";

type Formulario = {
  envioEstimado: string;
  margenMinimoPct: string;
  margenObjetivoPct: string;
  otrosCostosFijos: string;
  otrosCostosPct: string;
  terminado99: boolean;
  topeRedaccionesDia: string;
  topePruebasDia: string;
};

function desdeAjustes(a: AjustesNegocio): Formulario {
  return {
    envioEstimado: a.envioEstimado,
    margenMinimoPct: a.margenMinimoPct,
    margenObjetivoPct: a.margenObjetivoPct,
    otrosCostosFijos: a.otrosCostosFijos,
    otrosCostosPct: a.otrosCostosPct,
    terminado99: a.redondeo === "terminado_99",
    topeRedaccionesDia: String(a.topeRedaccionesDia),
    topePruebasDia: String(a.topePruebasDia ?? 100),
  };
}

/** Valida lo escrito y arma el cuerpo del PUT. Los mismos límites que el
 * backend (que es quien manda): 0 a 99.99 % y dinero de 0 a 1000. */
function revisar(f: Formulario): { cuerpo: GuardarAjustesInput | null; errores: Partial<Record<keyof Formulario, string>> } {
  const errores: Partial<Record<keyof Formulario, string>> = {};

  const envio = normalizarMonto(f.envioEstimado, true);
  if (envio == null || Number(envio) > 1000) errores.envioEstimado = "Escribe un monto entre 0 y 1000, por ejemplo 5.00.";

  const minimo = normalizarPorcentaje(f.margenMinimoPct);
  if (minimo == null) errores.margenMinimoPct = "Escribe un porcentaje entre 0 y 99.99, por ejemplo 25.";

  const objetivo = normalizarPorcentaje(f.margenObjetivoPct);
  if (objetivo == null) errores.margenObjetivoPct = "Escribe un porcentaje entre 0 y 99.99, por ejemplo 35.";
  else if (minimo != null && Number(objetivo) < Number(minimo)) errores.margenObjetivoPct = "El margen objetivo no puede ser menor que el mínimo.";

  const fijos = normalizarMonto(f.otrosCostosFijos, true);
  if (fijos == null || Number(fijos) > 1000) errores.otrosCostosFijos = "Escribe un monto entre 0 y 1000 (0 si no aplica).";

  const otros = normalizarPorcentaje(f.otrosCostosPct);
  if (otros == null) errores.otrosCostosPct = "Escribe un porcentaje entre 0 y 99.99 (0 si no aplica).";
  else if (objetivo != null && Number(objetivo) + Number(otros) >= 100) {
    errores.otrosCostosPct = "El margen objetivo más estos costos deben sumar menos de 100 %.";
  }

  // Entero de 1 a 200 (mismo rango que el backend y la base).
  const tope = /^\d{1,3}$/.test(f.topeRedaccionesDia.trim()) ? Number(f.topeRedaccionesDia.trim()) : null;
  if (tope == null || tope < 1 || tope > 200) errores.topeRedaccionesDia = "Escribe un número entero entre 1 y 200.";

  // Entero de 1 a 1000 (mismo rango que el backend y la base).
  const pruebas = /^\d{1,4}$/.test(f.topePruebasDia.trim()) ? Number(f.topePruebasDia.trim()) : null;
  if (pruebas == null || pruebas < 1 || pruebas > 1000) errores.topePruebasDia = "Escribe un número entero entre 1 y 1000.";

  if (Object.keys(errores).length > 0 || envio == null || minimo == null || objetivo == null || fijos == null || otros == null || tope == null || pruebas == null) {
    return { cuerpo: null, errores };
  }
  return {
    cuerpo: {
      envioEstimado: envio,
      margenMinimoPct: minimo,
      margenObjetivoPct: objetivo,
      otrosCostosFijos: fijos,
      otrosCostosPct: otros,
      redondeo: f.terminado99 ? "terminado_99" : "ninguno",
      topeRedaccionesDia: tope,
      topePruebasDia: pruebas,
    },
    errores,
  };
}

/** Los números del negocio con los que la calculadora recomienda precios. Solo
 * tú los conoces: por eso la app los pide y avisa mientras sigan siendo los de
 * partida. */
export function AjustesPreciosDialog({ trigger, onGuardado }: { trigger: ReactNode; onGuardado?: () => void }) {
  const [abierto, setAbierto] = useState(false);
  // Se pide al abrir (no antes) y siempre fresco.
  const { data, error, cargando, recargar } = useApi<AjustesNegocio>(abierto ? "/ajustes/negocio" : null);

  return (
    <Dialog open={abierto} onOpenChange={setAbierto}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent className="max-h-[92dvh] overflow-y-auto">
        <DialogHeader>
          <div className="flex items-center gap-1 pr-8">
            <DialogTitle>Ajustes de precios</DialogTitle>
            <InfoButton titulo="Ajustes de precios">
              <p>Son los números con los que la app recomienda precios, y los topes de uso de la IA.</p>
              <InfoAviso>
                <p>Revísalos con los datos reales de tu negocio: si no son correctos, las recomendaciones tampoco lo serán.</p>
              </InfoAviso>
              <p>Valen para todos los productos. El costo de envío de un producto en particular se cambia en la sección «Envío» de su ficha.</p>
            </InfoButton>
          </div>
          <DialogDescription>Los números con los que la app recomienda precios y limita el uso de la IA.</DialogDescription>
        </DialogHeader>

        {cargando ? (
          <div className="grid gap-4 py-2" aria-busy="true" aria-label="Cargando ajustes">
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-16 w-full" />
          </div>
        ) : !data ? (
          <div role="alert" className="flex items-start gap-2.5 rounded-lg bg-status-danger-soft p-3 text-sm text-status-danger-ink">
            <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
            <div className="space-y-2">
              <p className="font-medium">{error ?? "No se pudieron cargar los ajustes."}</p>
              <Button type="button" variant="outline" size="sm" onClick={recargar}>
                Reintentar
              </Button>
            </div>
          </div>
        ) : (
          <FormularioAjustes
            key={data.actualizadoEn ?? "partida"}
            ajustes={data}
            onGuardado={() => {
              setAbierto(false);
              onGuardado?.();
            }}
          />
        )}
      </DialogContent>
    </Dialog>
  );
}

function FormularioAjustes({ ajustes, onGuardado }: { ajustes: AjustesNegocio; onGuardado: () => void }) {
  const [form, setForm] = useState<Formulario>(desdeAjustes(ajustes));
  const [guardando, setGuardando] = useState(false);
  const [errorGuardar, setErrorGuardar] = useState<{ mensaje: string; motivos: string[] } | null>(null);

  const { cuerpo, errores } = revisar(form);
  const calibracion = ajustes.calibracionEnvio;

  function poner<K extends keyof Formulario>(campo: K, valor: Formulario[K]) {
    setForm((f) => ({ ...f, [campo]: valor }));
  }

  async function guardar(e: FormEvent) {
    // Este cuadro vive dentro de la ficha del producto (que también es un
    // formulario): sin esto, React haría subir el "enviar" y guardaría también la ficha.
    e.preventDefault();
    e.stopPropagation();
    if (!cuerpo) return;
    setGuardando(true);
    setErrorGuardar(null);
    try {
      await apiFetch<AjustesNegocio>("/ajustes/negocio", { method: "PUT", body: JSON.stringify(cuerpo) });
      toast.success("Ajustes de precios guardados.");
      onGuardado();
    } catch (err) {
      setErrorGuardar(
        err instanceof ApiError ? { mensaje: err.message, motivos: err.bloqueos } : { mensaje: "No se pudo conectar con el servidor.", motivos: [] },
      );
      setGuardando(false);
    }
  }

  return (
    <form onSubmit={guardar} noValidate>
      {!ajustes.confirmado && (
        <p role="note" className="mb-4 rounded-lg bg-status-warning-soft p-3 text-sm text-status-warning-ink">
          Son valores de partida. Revísalos y guárdalos (aunque no cambies nada) para confirmarlos.
        </p>
      )}

      <div className="grid gap-5 py-1">
        <Campo
          id="envioEstimado"
          label="Costo de envío estimado (USD)"
          error={errores.envioEstimado}
          ayuda="Un promedio de lo que te cobran por envío."
          info={
            <InfoButton titulo="Costo de envío estimado">
              <p>Rocketfy no cotiza el envío antes de vender, así que la app usa un valor estimado para calcular tu precio mínimo y tu margen.</p>
              <p>Pon un promedio de lo que te cobran por tus envíos: lo ves en el panel de Rocketfy.</p>
              <p>Si un producto pesa mucho o poco, anota su flete propio en su ficha (sección «Envío»): ese número reemplaza a este estimado solo para ese producto.</p>
            </InfoButton>
          }
        >
          <Input
            id="envioEstimado"
            inputMode="decimal"
            autoComplete="off"
            value={form.envioEstimado}
            onChange={(e) => poner("envioEstimado", e.target.value)}
            aria-invalid={Boolean(errores.envioEstimado)}
            aria-describedby={descripcionDe("envioEstimado", true, errores.envioEstimado)}
            className="tabular max-w-40"
          />
        </Campo>

        {calibracion && (
          <div className="-mt-2 rounded-lg bg-status-info-soft p-3 text-sm text-status-info-ink">
            <p>
              Rocketfy rechazó {calibracion.observaciones === 1 ? "1 pedido" : `${calibracion.observaciones} pedidos`} por importe mínimo. Eso sugiere un envío de{" "}
              <strong className="tabular">{formatMoney(calibracion.minimo)}</strong>
              {calibracion.minimo !== calibracion.maximo && (
                <>
                  {" "}
                  a <strong className="tabular">{formatMoney(calibracion.maximo)}</strong> (mediana <span className="tabular">{formatMoney(calibracion.mediana)}</span>)
                </>
              )}
              . Es orientativo.
            </p>
            <Button type="button" variant="outline" size="sm" className="mt-2" onClick={() => poner("envioEstimado", calibracion.mediana)}>
              Usar {formatMoney(calibracion.mediana)}
            </Button>
          </div>
        )}

        <div className="grid gap-5 sm:grid-cols-2">
          <Campo
            id="margenMinimoPct"
            label="Margen mínimo (%)"
            error={errores.margenMinimoPct}
            ayuda="Como % del precio."
            info={
              <InfoButton titulo="Margen mínimo">
                <p>Lo menos que aceptas ganar por una venta, como porcentaje del precio. Con él se calcula el precio mínimo para publicar.</p>
                <InfoEjemplo>
                  <p>Con un margen mínimo de 25 %, de cada $100 que cobras te quedan $25 de ganancia.</p>
                </InfoEjemplo>
              </InfoButton>
            }
          >
            <Input
              id="margenMinimoPct"
              inputMode="decimal"
              autoComplete="off"
              value={form.margenMinimoPct}
              onChange={(e) => poner("margenMinimoPct", e.target.value)}
              aria-invalid={Boolean(errores.margenMinimoPct)}
              aria-describedby={descripcionDe("margenMinimoPct", true, errores.margenMinimoPct)}
              className="tabular max-w-32"
            />
          </Campo>
          <Campo
            id="margenObjetivoPct"
            label="Margen objetivo (%)"
            error={errores.margenObjetivoPct}
            ayuda="Como % del precio."
            info={
              <InfoButton titulo="Margen objetivo">
                <p>Lo que quieres ganar normalmente. Con este margen se calcula el precio «Recomendado».</p>
                <p>No puede ser menor que el margen mínimo.</p>
              </InfoButton>
            }
          >
            <Input
              id="margenObjetivoPct"
              inputMode="decimal"
              autoComplete="off"
              value={form.margenObjetivoPct}
              onChange={(e) => poner("margenObjetivoPct", e.target.value)}
              aria-invalid={Boolean(errores.margenObjetivoPct)}
              aria-describedby={descripcionDe("margenObjetivoPct", true, errores.margenObjetivoPct)}
              className="tabular max-w-32"
            />
          </Campo>
        </div>

        <div className="grid gap-5 sm:grid-cols-2">
          <Campo
            id="otrosCostosFijos"
            label="Otros costos por unidad (USD)"
            error={errores.otrosCostosFijos}
            ayuda="0 si no aplica."
            info={
              <InfoButton titulo="Otros costos por unidad">
                <p>Empaque, etiquetas u otro gasto fijo por cada unidad vendida. Se suma al costo del producto al calcular tu precio mínimo y tu margen.</p>
              </InfoButton>
            }
          >
            <Input
              id="otrosCostosFijos"
              inputMode="decimal"
              autoComplete="off"
              value={form.otrosCostosFijos}
              onChange={(e) => poner("otrosCostosFijos", e.target.value)}
              aria-invalid={Boolean(errores.otrosCostosFijos)}
              aria-describedby={descripcionDe("otrosCostosFijos", true, errores.otrosCostosFijos)}
              className="tabular max-w-32"
            />
          </Campo>
          <Campo
            id="otrosCostosPct"
            label="Otros costos (% del precio)"
            error={errores.otrosCostosPct}
            ayuda="0 si no aplica."
            info={
              <InfoButton titulo="Otros costos como % del precio">
                <p>Comisiones o impuestos que dependen del precio de venta (por ejemplo, la comisión de un medio de pago).</p>
                <p>Junto con el margen objetivo deben sumar menos de 100 %.</p>
              </InfoButton>
            }
          >
            <Input
              id="otrosCostosPct"
              inputMode="decimal"
              autoComplete="off"
              value={form.otrosCostosPct}
              onChange={(e) => poner("otrosCostosPct", e.target.value)}
              aria-invalid={Boolean(errores.otrosCostosPct)}
              aria-describedby={descripcionDe("otrosCostosPct", true, errores.otrosCostosPct)}
              className="tabular max-w-32"
            />
          </Campo>
        </div>

        <div className="flex min-h-12 items-start gap-3 rounded-lg border bg-card p-3">
          <Checkbox id="terminado99" checked={form.terminado99} onCheckedChange={(c) => poner("terminado99", c === true)} className="mt-0.5" />
          <Label htmlFor="terminado99" className="block min-w-0 flex-1 cursor-pointer text-sm font-medium leading-snug">
            Terminar los precios en .99
          </Label>
          <InfoButton titulo="Terminar los precios en .99">
            <p>Los precios recomendados suben siempre al siguiente .99 (por ejemplo, de $14.20 a $14.99).</p>
            <p>Nunca bajan, para no recortar tu margen.</p>
          </InfoButton>
        </div>

        <div className="grid gap-2 border-t pt-5">
          <div className="flex items-center gap-1">
            <h3 className="text-sm font-semibold">Uso de la IA</h3>
            <InfoButton titulo="Uso de la IA">
              <p>Cada borrador que pides con «Redactar con IA» y cada mensaje que envías en «Probar con Victoria» llaman a la IA igual que un mensaje real, y eso tiene costo.</p>
              <p>Aquí pones el máximo que quieres usar al día. Los contadores se reinician a medianoche (hora de Ecuador).</p>
            </InfoButton>
          </div>
          <Campo
            id="topeRedaccionesDia"
            label="Borradores de IA por día"
            error={errores.topeRedaccionesDia}
            ayuda="De 1 a 200."
          >
            <Input
              id="topeRedaccionesDia"
              inputMode="numeric"
              autoComplete="off"
              value={form.topeRedaccionesDia}
              onChange={(e) => poner("topeRedaccionesDia", e.target.value)}
              aria-invalid={Boolean(errores.topeRedaccionesDia)}
              aria-describedby={descripcionDe("topeRedaccionesDia", true, errores.topeRedaccionesDia)}
              className="tabular max-w-32"
            />
          </Campo>
          <Campo
            id="topePruebasDia"
            label="Mensajes de prueba con Victoria por día"
            error={errores.topePruebasDia}
            ayuda="De 1 a 1000."
          >
            <Input
              id="topePruebasDia"
              inputMode="numeric"
              autoComplete="off"
              value={form.topePruebasDia}
              onChange={(e) => poner("topePruebasDia", e.target.value)}
              aria-invalid={Boolean(errores.topePruebasDia)}
              aria-describedby={descripcionDe("topePruebasDia", true, errores.topePruebasDia)}
              className="tabular max-w-32"
            />
          </Campo>
        </div>
      </div>

      {errorGuardar && (
        <div role="alert" className="mt-4 flex items-start gap-2.5 rounded-lg bg-status-danger-soft p-3 text-sm text-status-danger-ink">
          <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
          <div className="min-w-0 space-y-1">
            <p className="font-medium">{errorGuardar.mensaje}</p>
            {errorGuardar.motivos.length > 0 && (
              <ul className="list-disc space-y-1 pl-4">
                {errorGuardar.motivos.map((m) => (
                  <li key={m}>{m}</li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}

      <DialogFooter className="mt-5">
        <DialogClose asChild>
          <Button variant="outline" type="button" disabled={guardando}>
            Cancelar
          </Button>
        </DialogClose>
        <Button type="submit" disabled={guardando || !cuerpo}>
          {guardando ? (
            <>
              <Loader2 className="animate-spin" /> Guardando…
            </>
          ) : (
            "Guardar ajustes"
          )}
        </Button>
      </DialogFooter>
    </form>
  );
}
