"use client";

import { Loader2, Plus, Trash2, TriangleAlert } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { InfoButton } from "@/components/app/info-button";
import { SectionCard } from "@/components/app/section-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/use-api";
import { apiFetch, ApiError } from "@/lib/api";
import { aCentavos, deCentavos, formatMoney, normalizarMonto, normalizarPorcentaje } from "@/lib/format";
import type { ReglasPrecio, TipoRegateo, TipoTransferencia } from "@/types/precios";

const MAXIMO_ESCALAS = 6;

type Fila = { cantidad: string; precioTotal: string };
type Estado = {
  transferenciaTipo: TipoTransferencia | "ninguno";
  transferenciaValor: string;
  regateoTipo: TipoRegateo | "ninguno";
  regateoValor: string;
  envioUnidades: string;
  envioMonto: string;
  escalas: Fila[];
};

function inicial(r: ReglasPrecio): Estado {
  return {
    transferenciaTipo: r.transferenciaTipo ?? "ninguno",
    transferenciaValor: r.transferenciaValor ?? "",
    regateoTipo: r.regateoTipo ?? "ninguno",
    regateoValor: r.regateoValor ?? "",
    envioUnidades: r.envioGratisDesdeUnidades != null ? String(r.envioGratisDesdeUnidades) : "",
    envioMonto: r.envioGratisDesdeMonto ?? "",
    escalas: r.escalas.map((e) => ({ cantidad: String(e.cantidad), precioTotal: e.precioTotal })),
  };
}

/** Valor de una regla en centavos (monto) o en centésimas de punto (porcentaje), o null si no es válido. */
function leer(tipo: string, texto: string): string | null {
  if (tipo === "porcentaje") return normalizarPorcentaje(texto);
  return normalizarMonto(texto);
}

/** Precio por unidad pagando por transferencia, en centavos (solo para mostrar; lo que vale lo calcula el servidor). */
function conTransferencia(precio: number, tipo: Estado["transferenciaTipo"], valor: string | null): number | null {
  if (tipo === "ninguno" || valor === null) return null;
  const v = aCentavos(valor);
  if (v === null) return null;
  if (tipo === "precio") return v;
  if (tipo === "monto") return precio - v;
  return Math.round((precio * (10000 - v)) / 10000);
}

/** «Precios y descuentos» del producto (ADR-017): lo que Victoria PUEDE ofrecer. Todo vacío = se vende como siempre. */
export function SeccionDescuentos({ sku, soloLectura }: { sku: string; soloLectura: boolean }) {
  const reglas = useApi<ReglasPrecio>(`/precios/productos/${encodeURIComponent(sku)}`);

  return (
    <SectionCard
      titulo="Precios y descuentos"
      descripcion="Lo que Victoria puede ofrecer de este producto."
      info={
        <InfoButton titulo="Precios y descuentos">
          <p>Aquí decides qué rebajas puede ofrecer Victoria con <strong>este</strong> producto. Si lo dejas vacío, se vende como siempre.</p>
          <ul>
            <li><strong>Precio por transferencia:</strong> un precio menor si el cliente paga por transferencia (ej.: $25 contra entrega, $20 transfiriendo).</li>
            <li><strong>Regateo:</strong> hasta cuánto puede bajar Victoria si el cliente pide rebaja. Ella nunca ve tu mínimo: lo decide el sistema.</li>
            <li><strong>Precio por cantidad:</strong> «2 por $45», «3 por $60».</li>
            <li><strong>Envío gratis:</strong> solo si el envío se cobra aparte.</li>
          </ul>
          <p>Ningún descuento baja de tu <strong>precio mínimo</strong> (costo + envío + tu margen mínimo de Ajustes). Si un precio queda por debajo, te pedimos confirmarlo.</p>
          <p>El regateo y el precio por transferencia no se suman: el cliente paga el menor de los dos.</p>
        </InfoButton>
      }
    >
      {reglas.cargando ? (
        <div className="space-y-3 p-4 sm:p-5">
          <Skeleton className="h-9 w-full" />
          <Skeleton className="h-9 w-full" />
        </div>
      ) : reglas.error || !reglas.data ? (
        <div role="alert" className="flex flex-wrap items-center gap-3 p-4 text-sm text-status-danger-ink sm:p-5">
          <span>{reglas.error ?? "No se pudieron leer los precios."}</span>
          <Button size="sm" variant="outline" onClick={reglas.recargar}>
            Reintentar
          </Button>
        </div>
      ) : (
        <Formulario key={JSON.stringify(reglas.data)} reglas={reglas.data} soloLectura={soloLectura} onGuardado={reglas.recargar} />
      )}
    </SectionCard>
  );
}

function Formulario({ reglas, soloLectura, onGuardado }: { reglas: ReglasPrecio; soloLectura: boolean; onGuardado: () => void }) {
  const [e, setE] = useState<Estado>(() => inicial(reglas));
  const [intento, setIntento] = useState(false);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<{ mensaje: string; motivos: string[] } | null>(null);
  const [bajoMargen, setBajoMargen] = useState<string[] | null>(null);

  const precio = aCentavos(reglas.precio) ?? 0;
  const minimo = aCentavos(reglas.precioMinimo);
  const cambio = JSON.stringify(e) !== JSON.stringify(inicial(reglas));
  const set = (parcial: Partial<Estado>) => setE((actual) => ({ ...actual, ...parcial }));

  // Validación local (el servidor vuelve a validar todo).
  const errTransferencia = e.transferenciaTipo !== "ninguno" && leer(e.transferenciaTipo, e.transferenciaValor) === null ? "Escribe un valor válido." : undefined;
  const errRegateo = e.regateoTipo !== "ninguno" && leer(e.regateoTipo, e.regateoValor) === null ? "Escribe un valor válido." : undefined;
  const errEscalas = e.escalas.map((f) => {
    const c = Number(f.cantidad);
    if (!/^\d+$/.test(f.cantidad.trim()) || c < 2) return "La cantidad debe ser 2 o más.";
    if (c > reglas.maxUnidades) return `El máximo por pedido es ${reglas.maxUnidades}.`;
    const t = normalizarMonto(f.precioTotal);
    if (t === null) return "Escribe el precio total.";
    if ((aCentavos(t) ?? 0) >= precio * c) return "Debe ser menor que comprarlos por separado.";
    return undefined;
  });
  const errUnidades = e.envioUnidades.trim() !== "" && !/^\d+$/.test(e.envioUnidades.trim()) ? "Escribe un número entero." : undefined;
  const errMonto = e.envioMonto.trim() !== "" && normalizarMonto(e.envioMonto) === null ? "Escribe un monto válido." : undefined;
  const hayErrores = Boolean(errTransferencia || errRegateo || errUnidades || errMonto || errEscalas.some(Boolean));

  const transferencia = conTransferencia(precio, e.transferenciaTipo, e.transferenciaTipo === "ninguno" ? null : leer(e.transferenciaTipo, e.transferenciaValor));
  const limiteRegateo = (() => {
    if (e.regateoTipo === "ninguno") return null;
    const v = aCentavos(leer(e.regateoTipo, e.regateoValor));
    if (v === null) return null;
    return e.regateoTipo === "monto" ? v : Math.round((precio * v) / 10000);
  })();
  const pisoRegateo = limiteRegateo === null ? null : Math.max(precio - limiteRegateo, minimo ?? 0);

  async function guardar(confirmarBajoMargen = false) {
    setIntento(true);
    setError(null);
    if (hayErrores) return;
    setGuardando(true);
    try {
      await apiFetch<ReglasPrecio>(`/precios/productos/${encodeURIComponent(reglas.sku)}`, {
        method: "PUT",
        body: JSON.stringify({
          transferenciaTipo: e.transferenciaTipo === "ninguno" ? null : e.transferenciaTipo,
          transferenciaValor: e.transferenciaTipo === "ninguno" ? null : leer(e.transferenciaTipo, e.transferenciaValor),
          regateoTipo: e.regateoTipo === "ninguno" ? null : e.regateoTipo,
          regateoValor: e.regateoTipo === "ninguno" ? null : leer(e.regateoTipo, e.regateoValor),
          envioGratisDesdeUnidades: e.envioUnidades.trim() === "" ? null : Number(e.envioUnidades),
          envioGratisDesdeMonto: e.envioMonto.trim() === "" ? null : normalizarMonto(e.envioMonto),
          escalas: e.escalas.map((f) => ({ cantidad: Number(f.cantidad), precioTotal: normalizarMonto(f.precioTotal) })),
          confirmarBajoMargen,
        }),
      });
      toast.success("Precios y descuentos guardados.");
      setBajoMargen(null);
      onGuardado();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) setBajoMargen(err.bloqueos);
      else setError(err instanceof ApiError ? { mensaje: err.message, motivos: err.bloqueos } : { mensaje: "No se pudo conectar con el servidor.", motivos: [] });
    } finally {
      setGuardando(false);
    }
  }

  const deshabilitado = soloLectura || guardando;

  return (
    <div className="space-y-5 p-4 sm:p-5">
      <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-3">
        <div>
          <dt className="text-muted-foreground">Precio normal</dt>
          <dd className="tabular font-medium">{formatMoney(reglas.precio)}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Tu precio mínimo</dt>
          <dd className="tabular font-medium">{reglas.precioMinimo ? formatMoney(reglas.precioMinimo) : "—"}</dd>
        </div>
        {!reglas.margenConfirmado && <p className="col-span-2 text-xs text-muted-foreground sm:col-span-1">Confirma tus Ajustes de precios para calcular el mínimo.</p>}
      </dl>

      <fieldset className="grid gap-3 border-t pt-4 sm:grid-cols-[minmax(0,14rem)_minmax(0,10rem)_1fr] sm:items-end">
        <legend className="mb-2 text-sm font-medium">Precio por transferencia</legend>
        <div className="grid gap-1.5">
          <Label htmlFor="trans-tipo">Tipo</Label>
          <Select value={e.transferenciaTipo} onValueChange={(v) => set({ transferenciaTipo: v as Estado["transferenciaTipo"] })} disabled={deshabilitado}>
            <SelectTrigger id="trans-tipo" className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="ninguno">Sin precio especial</SelectItem>
              <SelectItem value="precio">Precio fijo</SelectItem>
              <SelectItem value="porcentaje">Porcentaje menos</SelectItem>
              <SelectItem value="monto">Dólares menos</SelectItem>
            </SelectContent>
          </Select>
        </div>
        {e.transferenciaTipo !== "ninguno" && (
          <div className="grid gap-1.5">
            <Label htmlFor="trans-valor">{e.transferenciaTipo === "porcentaje" ? "Porcentaje (%)" : "Monto ($)"}</Label>
            <Input
              id="trans-valor"
              inputMode="decimal"
              value={e.transferenciaValor}
              onChange={(ev) => set({ transferenciaValor: ev.target.value })}
              aria-invalid={intento && Boolean(errTransferencia)}
              aria-describedby="trans-ayuda"
              disabled={deshabilitado}
              className="tabular"
            />
          </div>
        )}
        <p id="trans-ayuda" className="text-sm text-muted-foreground" aria-live="polite">
          {intento && errTransferencia ? (
            <span className="text-status-danger-ink">{errTransferencia}</span>
          ) : transferencia !== null ? (
            <>Transfiriendo paga <strong className="tabular text-foreground">{formatMoney(deCentavos(transferencia))}</strong> por unidad.</>
          ) : (
            "Sin rebaja por transferencia."
          )}
        </p>
      </fieldset>

      <fieldset className="grid gap-3 border-t pt-4 sm:grid-cols-[minmax(0,14rem)_minmax(0,10rem)_1fr] sm:items-end">
        <legend className="mb-2 text-sm font-medium">Regateo</legend>
        <div className="grid gap-1.5">
          <Label htmlFor="reg-tipo">Victoria puede bajar</Label>
          <Select value={e.regateoTipo} onValueChange={(v) => set({ regateoTipo: v as Estado["regateoTipo"] })} disabled={deshabilitado}>
            <SelectTrigger id="reg-tipo" className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="ninguno">No regatea</SelectItem>
              <SelectItem value="porcentaje">Hasta un porcentaje</SelectItem>
              <SelectItem value="monto">Hasta un monto por unidad</SelectItem>
            </SelectContent>
          </Select>
        </div>
        {e.regateoTipo !== "ninguno" && (
          <div className="grid gap-1.5">
            <Label htmlFor="reg-valor">{e.regateoTipo === "porcentaje" ? "Hasta (%)" : "Hasta ($)"}</Label>
            <Input
              id="reg-valor"
              inputMode="decimal"
              value={e.regateoValor}
              onChange={(ev) => set({ regateoValor: ev.target.value })}
              aria-invalid={intento && Boolean(errRegateo)}
              aria-describedby="reg-ayuda"
              disabled={deshabilitado}
              className="tabular"
            />
          </div>
        )}
        <p id="reg-ayuda" className="text-sm text-muted-foreground" aria-live="polite">
          {intento && errRegateo ? (
            <span className="text-status-danger-ink">{errRegateo}</span>
          ) : pisoRegateo !== null ? (
            <>Nunca baja de <strong className="tabular text-foreground">{formatMoney(deCentavos(pisoRegateo))}</strong> por unidad.</>
          ) : (
            "Victoria mantiene el precio."
          )}
        </p>
      </fieldset>

      <fieldset className="space-y-3 border-t pt-4">
        <legend className="mb-2 text-sm font-medium">Precio por cantidad</legend>
        {e.escalas.length === 0 && <p className="text-sm text-muted-foreground">Sin precio por cantidad.</p>}
        {e.escalas.map((f, i) => {
          const total = aCentavos(normalizarMonto(f.precioTotal));
          const c = Number(f.cantidad);
          const ahorro = total !== null && c >= 2 ? precio * c - total : null;
          return (
            <div key={i} className="grid grid-cols-[minmax(0,6rem)_minmax(0,9rem)_auto] items-end gap-2 sm:grid-cols-[6rem_9rem_1fr_auto]">
              <div className="grid gap-1.5">
                <Label htmlFor={`esc-c-${i}`}>Unidades</Label>
                <Input
                  id={`esc-c-${i}`}
                  inputMode="numeric"
                  value={f.cantidad}
                  onChange={(ev) => set({ escalas: e.escalas.map((x, j) => (j === i ? { ...x, cantidad: ev.target.value } : x)) })}
                  aria-invalid={intento && Boolean(errEscalas[i])}
                  disabled={deshabilitado}
                  className="tabular"
                />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor={`esc-p-${i}`}>Precio total ($)</Label>
                <Input
                  id={`esc-p-${i}`}
                  inputMode="decimal"
                  value={f.precioTotal}
                  onChange={(ev) => set({ escalas: e.escalas.map((x, j) => (j === i ? { ...x, precioTotal: ev.target.value } : x)) })}
                  aria-invalid={intento && Boolean(errEscalas[i])}
                  disabled={deshabilitado}
                  className="tabular"
                />
              </div>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="size-10 sm:order-last"
                aria-label={`Quitar el precio para ${f.cantidad || "esta cantidad"}`}
                disabled={deshabilitado}
                onClick={() => set({ escalas: e.escalas.filter((_, j) => j !== i) })}
              >
                <Trash2 />
              </Button>
              <p className="col-span-3 text-xs sm:col-span-1 sm:self-center">
                {intento && errEscalas[i] ? (
                  <span className="text-status-danger-ink">{errEscalas[i]}</span>
                ) : ahorro !== null && ahorro > 0 ? (
                  <span className="text-muted-foreground">El cliente ahorra {formatMoney(deCentavos(ahorro))}.</span>
                ) : null}
              </p>
            </div>
          );
        })}
        {!soloLectura && e.escalas.length < MAXIMO_ESCALAS && (
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={deshabilitado || reglas.maxUnidades < 2}
            onClick={() => set({ escalas: [...e.escalas, { cantidad: String(Math.min(reglas.maxUnidades, (e.escalas.length || 0) + 2)), precioTotal: "" }] })}
          >
            <Plus /> Agregar precio por cantidad
          </Button>
        )}
        {reglas.maxUnidades < 2 && <p className="text-xs text-muted-foreground">Este producto se vende de a 1 por pedido: sube el máximo de unidades para usar precio por cantidad.</p>}
      </fieldset>

      {!reglas.envioIncluido && (
        <fieldset className="grid gap-3 border-t pt-4 sm:grid-cols-2">
          <legend className="mb-2 text-sm font-medium">Envío gratis</legend>
          <div className="grid gap-1.5">
            <Label htmlFor="envio-u">Desde unidades</Label>
            <Input id="envio-u" inputMode="numeric" value={e.envioUnidades} onChange={(ev) => set({ envioUnidades: ev.target.value })} aria-invalid={intento && Boolean(errUnidades)} disabled={deshabilitado} className="tabular" placeholder="Ej.: 2" />
            {intento && errUnidades && <p className="text-xs text-status-danger-ink">{errUnidades}</p>}
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="envio-m">Desde compras de ($)</Label>
            <Input id="envio-m" inputMode="decimal" value={e.envioMonto} onChange={(ev) => set({ envioMonto: ev.target.value })} aria-invalid={intento && Boolean(errMonto)} disabled={deshabilitado} className="tabular" placeholder="Ej.: 50" />
            {intento && errMonto && <p className="text-xs text-status-danger-ink">{errMonto}</p>}
          </div>
        </fieldset>
      )}

      {bajoMargen && (
        <div role="alert" className="space-y-2 rounded-lg bg-status-warning-soft p-3 text-sm text-status-warning-ink">
          <p className="flex items-start gap-2 font-medium">
            <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden /> Esto queda bajo tu margen mínimo:
          </p>
          <ul className="list-disc space-y-1 pl-6">
            {bajoMargen.map((m) => (
              <li key={m}>{m}</li>
            ))}
          </ul>
          <Button type="button" size="sm" variant="outline" className="bg-card text-foreground" disabled={guardando} onClick={() => void guardar(true)}>
            Guardar igual, a propósito
          </Button>
        </div>
      )}
      {error && (
        <div role="alert" className="flex items-start gap-2.5 rounded-lg bg-status-danger-soft p-3 text-sm text-status-danger-ink">
          <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
          <div className="min-w-0 space-y-1">
            <p className="font-medium">{error.mensaje}</p>
            {error.motivos.length > 0 && (
              <ul className="list-disc space-y-1 pl-4">
                {error.motivos.map((m) => (
                  <li key={m}>{m}</li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}

      {!soloLectura && (
        <div className="flex flex-wrap items-center justify-end gap-2 border-t pt-4">
          <Button type="button" variant="outline" disabled={!cambio || guardando} onClick={() => { setE(inicial(reglas)); setIntento(false); setError(null); setBajoMargen(null); }}>
            Descartar
          </Button>
          <Button type="button" disabled={!cambio || guardando} onClick={() => void guardar()}>
            {guardando ? (
              <>
                <Loader2 className="animate-spin" /> Guardando…
              </>
            ) : (
              "Guardar precios"
            )}
          </Button>
        </div>
      )}
    </div>
  );
}
