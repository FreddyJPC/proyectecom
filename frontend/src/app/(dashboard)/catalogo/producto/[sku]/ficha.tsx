"use client";

import { ArrowLeft, Loader2, Lock, Sparkles, TriangleAlert } from "lucide-react";
import Link from "next/link";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";

import { PageHeader } from "@/components/app/page-header";
import { SectionCard } from "@/components/app/section-card";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { apiFetch, ApiError } from "@/lib/api";
import { estadoProductoBotInfo } from "@/lib/estados";
import { formatFechaHora, normalizarMonto } from "@/lib/format";
import { METODOS_PAGO, type EditarProductoBotInput, type ProductoBotDetalle } from "@/types/producto-bot";

import { ACCIONES_POR_ESTADO, AccionEstadoBoton } from "../../accion-estado";
import { Campo, descripcionDe } from "./campo";
import { RedactarIADialog } from "./redactar-ia-dialog";
import { DatosRocketfy, HistorialCard, RevisionPanel } from "./secciones";
import { SeccionPrecio } from "./seccion-precio";

// Mismos límites que el backend (backend/src/routes/productos_bot/schemas.py):
// todo lo que se escribe aquí lo lee Victoria en CADA mensaje, por eso es corto.
const LIMITE = {
  nombre: 120,
  descripcion: 1500,
  variantes: 300,
  tiempoEntrega: 200,
  preguntasFrecuentes: 3000,
  temasNoResponder: 1000,
  notasInternas: 2000,
} as const;
const MAX_UNIDADES = 20;

type Formulario = {
  nombre: string;
  descripcion: string;
  precio: string;
  variantes: string;
  tiempoEntrega: string;
  metodosPago: string[];
  preguntasFrecuentes: string;
  temasNoResponder: string;
  maxUnidades: string;
  notasInternas: string;
  precioCompetencia: string;
};

// Los textos se parten de su versión sin espacios sobrantes: al guardar el
// backend también los recorta, y así "sin cambios" significa realmente eso.
function desdeDetalle(d: ProductoBotDetalle): Formulario {
  return {
    nombre: d.nombre.trim(),
    descripcion: d.descripcion.trim(),
    precio: d.precio,
    variantes: (d.variantes ?? "").trim(),
    tiempoEntrega: d.tiempoEntrega.trim(),
    // Solo los métodos que la app conoce, siempre en el mismo orden.
    metodosPago: METODOS_PAGO.map((m) => m.valor).filter((v) => d.metodosPago.includes(v)),
    preguntasFrecuentes: (d.preguntasFrecuentes ?? "").trim(),
    temasNoResponder: (d.temasNoResponder ?? "").trim(),
    maxUnidades: String(d.maxUnidadesPorPedido),
    notasInternas: (d.notasInternas ?? "").trim(),
    precioCompetencia: d.precioCompetencia ?? "",
  };
}

/** Compara lo escrito con lo guardado: devuelve SOLO lo que cambió (el PATCH
 * del backend actualiza únicamente los campos que vengan) y los errores. */
function revisar(inicial: Formulario, actual: Formulario) {
  const cambios: EditarProductoBotInput = {};
  const errores: Partial<Record<keyof Formulario, string>> = {};

  const nombre = actual.nombre.trim();
  if (!nombre) errores.nombre = "El nombre no puede quedar vacío.";
  else if (nombre !== inicial.nombre) cambios.nombre = nombre;

  const descripcion = actual.descripcion.trim();
  if (descripcion !== inicial.descripcion) cambios.descripcion = descripcion;

  const monto = normalizarMonto(actual.precio);
  if (monto == null) errores.precio = "Escribe un precio válido mayor que cero, por ejemplo 24.99 (máximo 2 decimales).";
  else if (monto !== inicial.precio) cambios.precio = monto;

  const variantes = actual.variantes.trim();
  if (variantes !== inicial.variantes) cambios.variantes = variantes || null;

  const tiempoEntrega = actual.tiempoEntrega.trim();
  if (tiempoEntrega !== inicial.tiempoEntrega) cambios.tiempoEntrega = tiempoEntrega;

  if (actual.metodosPago.length === 0) errores.metodosPago = "Elige al menos un método de pago.";
  else if (actual.metodosPago.join(",") !== inicial.metodosPago.join(",")) cambios.metodosPago = actual.metodosPago;

  const faq = actual.preguntasFrecuentes.trim();
  if (faq !== inicial.preguntasFrecuentes) cambios.preguntasFrecuentes = faq || null;

  const temas = actual.temasNoResponder.trim();
  if (temas !== inicial.temasNoResponder) cambios.temasNoResponder = temas || null;

  const unidades = Number(actual.maxUnidades);
  if (!/^\d+$/.test(actual.maxUnidades.trim()) || unidades < 1 || unidades > MAX_UNIDADES) {
    errores.maxUnidades = `Entre 1 y ${MAX_UNIDADES} unidades.`;
  } else if (String(unidades) !== inicial.maxUnidades) {
    cambios.maxUnidadesPorPedido = unidades;
  }

  const notas = actual.notasInternas.trim();
  if (notas !== inicial.notasInternas) cambios.notasInternas = notas || null;

  // Opcional: vacío = sin precio de la competencia (se borra).
  if (actual.precioCompetencia.trim() === "") {
    if (inicial.precioCompetencia !== "") cambios.precioCompetencia = null;
  } else {
    const competencia = normalizarMonto(actual.precioCompetencia);
    if (competencia == null) errores.precioCompetencia = "Escribe un precio válido mayor que cero, por ejemplo 22.50.";
    else if (competencia !== inicial.precioCompetencia) cambios.precioCompetencia = competencia;
  }

  return { cambios, errores };
}

/** La ficha entera. Se vuelve a montar (key = fecha de actualización) cada vez
 * que el servidor devuelve datos nuevos, así el formulario siempre parte de lo
 * que realmente quedó guardado. */
export function Ficha({ detalle, onCambio }: { detalle: ProductoBotDetalle; onCambio: () => void }) {
  const inicial = desdeDetalle(detalle);
  const [form, setForm] = useState<Formulario>(inicial);
  const [guardando, setGuardando] = useState(false);
  const [errorGuardar, setErrorGuardar] = useState<{ mensaje: string; motivos: string[] } | null>(null);

  const { cambios, errores } = revisar(inicial, form);
  const hayCambios = Object.keys(cambios).length > 0 || Object.keys(errores).length > 0;
  const soloLectura = detalle.estado === "archivado";
  const estado = estadoProductoBotInfo(detalle.estado);
  const acciones = ACCIONES_POR_ESTADO[detalle.estado];
  const vendiendo = detalle.estado === "activo";

  function poner<K extends keyof Formulario>(campo: K, valor: Formulario[K]) {
    setForm((f) => ({ ...f, [campo]: valor }));
  }

  function alternarMetodo(valor: string, marcado: boolean) {
    setForm((f) => {
      const conjunto = new Set(f.metodosPago);
      if (marcado) conjunto.add(valor);
      else conjunto.delete(valor);
      return { ...f, metodosPago: METODOS_PAGO.map((m) => m.valor).filter((v) => conjunto.has(v)) };
    });
  }

  async function guardar(e: FormEvent) {
    e.preventDefault();
    if (Object.keys(errores).length > 0 || Object.keys(cambios).length === 0) return;
    setGuardando(true);
    setErrorGuardar(null);
    try {
      await apiFetch<ProductoBotDetalle>(`/productos-bot/${encodeURIComponent(detalle.sku)}`, {
        method: "PATCH",
        body: JSON.stringify(cambios),
      });
      toast.success("Cambios guardados.");
      // Al recargar, la ficha se vuelve a montar con lo guardado.
      onCambio();
    } catch (err) {
      setErrorGuardar(
        err instanceof ApiError
          ? { mensaje: err.message, motivos: err.bloqueos }
          : { mensaje: "No se pudo conectar con el servidor.", motivos: [] },
      );
      setGuardando(false);
    }
  }

  return (
    <>
      <Link
        href="/catalogo?tab=mis-productos"
        className="-mb-2 inline-flex min-h-10 w-fit items-center gap-1.5 rounded-md text-sm text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"
      >
        <ArrowLeft className="size-4" aria-hidden /> Mis productos
      </Link>

      <PageHeader
        accionesDebajoEnMovil
        title={detalle.nombre}
        badge={<StatusBadge label={estado.label} variant={estado.variant} />}
        description={
          <>
            <span className="tabular">{detalle.sku}</span> · {estado.explicacion}
            {vendiendo && detalle.publicadoEn && (
              <>
                {" "}
                Publicado {detalle.publicadoPor ? `por ${detalle.publicadoPor} ` : ""}el {formatFechaHora(detalle.publicadoEn)}.
              </>
            )}
          </>
        }
        actions={acciones.map((accion, i) => {
          const exigeSinBloqueos = accion === "publicar" || accion === "reanudar";
          return (
            <AccionEstadoBoton
              key={accion}
              accion={accion}
              producto={detalle}
              onHecho={onCambio}
              size="default"
              variant={i === 0 ? undefined : "outline"}
              deshabilitado={hayCambios || (exigeSinBloqueos && detalle.verificacion.bloqueos.length > 0)}
            />
          );
        })}
      />

      {hayCambios && !soloLectura && (
        <p className="-mt-2 text-sm text-muted-foreground">Tienes cambios sin guardar: guárdalos o descártalos antes de cambiar el estado del producto.</p>
      )}

      {soloLectura && (
        <p role="note" className="flex items-start gap-2.5 rounded-xl border bg-muted/50 p-4 text-sm text-muted-foreground">
          <Lock className="mt-0.5 size-4 shrink-0" aria-hidden />
          Este producto está archivado y no se puede editar. Restáuralo para volver a trabajar en él.
        </p>
      )}

      <div className="grid items-start gap-5 lg:grid-cols-[1fr_22rem] lg:grid-rows-[auto_auto_auto_1fr]">
        {!soloLectura && (
          <div className="lg:col-start-2 lg:row-start-1">
            <RevisionPanel verificacion={detalle.verificacion} vendiendo={vendiendo} />
          </div>
        )}

        <div className="lg:col-start-2 lg:row-start-2">
          <DatosRocketfy detalle={detalle} sinCambiosPendientes={!hayCambios} onActualizado={onCambio} />
        </div>

        <form onSubmit={guardar} noValidate className="flex min-w-0 flex-col gap-5 lg:col-start-1 lg:row-span-4 lg:row-start-1">
          <fieldset disabled={soloLectura || guardando} className="contents">
            <legend className="sr-only">Datos de venta de {detalle.nombre}</legend>

            <SeccionPrecio
              sku={detalle.sku}
              precio={form.precio}
              onPrecio={(v) => poner("precio", v)}
              errorPrecio={errores.precio}
              competencia={form.precioCompetencia}
              onCompetencia={(v) => poner("precioCompetencia", v)}
              errorCompetencia={errores.precioCompetencia}
              onAjustesGuardados={onCambio}
            />

            <SectionCard titulo="Contenido para Victoria" descripcion="Todo lo de esta sección lo lee Victoria y se lo cuenta al cliente. Si algo no está aquí, ella no lo inventa.">
              <div className="space-y-5 p-4 sm:p-5">
                <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg bg-muted/50 p-3">
                  <p className="min-w-0 text-sm text-muted-foreground">
                    ¿Quieres un primer borrador? La IA lo redacta con los datos de Rocketfy y tus notas; tú revisas y aceptas cada campo.
                  </p>
                  <RedactarIADialog
                    sku={detalle.sku}
                    actuales={{
                      nombre: form.nombre,
                      descripcion: form.descripcion,
                      variantes: form.variantes,
                      preguntasFrecuentes: form.preguntasFrecuentes,
                      temasNoResponder: form.temasNoResponder,
                    }}
                    onAceptar={(campo, valor) => poner(campo, valor)}
                    trigger={
                      <Button type="button" variant="outline" size="sm">
                        <Sparkles /> Redactar con IA
                      </Button>
                    }
                  />
                </div>

                <Campo id="nombre" label="Nombre del producto" error={errores.nombre} contador={{ actual: form.nombre.length, maximo: LIMITE.nombre }}>
                  <Input
                    id="nombre"
                    value={form.nombre}
                    maxLength={LIMITE.nombre}
                    onChange={(e) => poner("nombre", e.target.value)}
                    aria-invalid={Boolean(errores.nombre)}
                    aria-describedby={descripcionDe("nombre", false, errores.nombre)}
                  />
                </Campo>

                <Campo
                  id="descripcion"
                  label="Descripción"
                  ayuda="Qué es, para qué sirve y qué incluye. Escribe solo lo que sabes que es cierto: Victoria lo repetirá tal cual."
                  contador={{ actual: form.descripcion.length, maximo: LIMITE.descripcion }}
                >
                  <Textarea
                    id="descripcion"
                    rows={5}
                    value={form.descripcion}
                    maxLength={LIMITE.descripcion}
                    onChange={(e) => poner("descripcion", e.target.value)}
                    aria-describedby="descripcion-ayuda"
                  />
                </Campo>

                <Campo
                  id="variantes"
                  label="Variantes"
                  opcional
                  ayuda="Colores, tallas o modelos disponibles, separados por comas."
                  contador={{ actual: form.variantes.length, maximo: LIMITE.variantes }}
                >
                  <Input
                    id="variantes"
                    value={form.variantes}
                    maxLength={LIMITE.variantes}
                    onChange={(e) => poner("variantes", e.target.value)}
                    aria-describedby="variantes-ayuda"
                  />
                </Campo>

                <Campo
                  id="preguntasFrecuentes"
                  label="Preguntas frecuentes"
                  opcional
                  ayuda="Escribe la pregunta y su respuesta. Así Victoria contesta con tu información y no con suposiciones."
                  contador={{ actual: form.preguntasFrecuentes.length, maximo: LIMITE.preguntasFrecuentes }}
                >
                  <Textarea
                    id="preguntasFrecuentes"
                    rows={4}
                    value={form.preguntasFrecuentes}
                    maxLength={LIMITE.preguntasFrecuentes}
                    onChange={(e) => poner("preguntasFrecuentes", e.target.value)}
                    aria-describedby="preguntasFrecuentes-ayuda"
                  />
                </Campo>

                <Campo
                  id="temasNoResponder"
                  label="Temas que Victoria NO debe responder"
                  opcional
                  ayuda="Cosas sobre las que no quieres que opine ni prometa nada (por ejemplo, garantías que no ofreces)."
                  contador={{ actual: form.temasNoResponder.length, maximo: LIMITE.temasNoResponder }}
                >
                  <Textarea
                    id="temasNoResponder"
                    rows={3}
                    value={form.temasNoResponder}
                    maxLength={LIMITE.temasNoResponder}
                    onChange={(e) => poner("temasNoResponder", e.target.value)}
                    aria-describedby="temasNoResponder-ayuda"
                  />
                </Campo>
              </div>
            </SectionCard>

            <SectionCard titulo="Reglas de venta" descripcion="Cómo y cuánto puede comprar el cliente.">
              <div className="space-y-5 p-4 sm:p-5">
                <Campo
                  id="tiempoEntrega"
                  label="Tiempo de entrega"
                  ayuda="Cómo se lo dice Victoria al cliente, por ejemplo: «2 a 4 días hábiles». Es obligatorio para publicar."
                  contador={{ actual: form.tiempoEntrega.length, maximo: LIMITE.tiempoEntrega }}
                >
                  <Input
                    id="tiempoEntrega"
                    value={form.tiempoEntrega}
                    maxLength={LIMITE.tiempoEntrega}
                    onChange={(e) => poner("tiempoEntrega", e.target.value)}
                    aria-describedby="tiempoEntrega-ayuda"
                  />
                </Campo>

                <Campo
                  id="maxUnidades"
                  label="Unidades máximas por pedido"
                  error={errores.maxUnidades}
                  ayuda="Cuántas unidades puede comprar una persona en un solo pedido. Si pide más, Victoria le explica el máximo."
                >
                  <Input
                    id="maxUnidades"
                    type="number"
                    inputMode="numeric"
                    min={1}
                    max={MAX_UNIDADES}
                    value={form.maxUnidades}
                    onChange={(e) => poner("maxUnidades", e.target.value)}
                    aria-invalid={Boolean(errores.maxUnidades)}
                    aria-describedby={descripcionDe("maxUnidades", true, errores.maxUnidades)}
                    className="tabular w-28"
                  />
                </Campo>

                <fieldset className="grid gap-1.5">
                  <legend className="mb-1.5 text-sm font-medium">Métodos de pago que acepta</legend>
                  <div className="grid gap-2 sm:grid-cols-2">
                    {METODOS_PAGO.map((m) => (
                      <label
                        key={m.valor}
                        htmlFor={`pago-${m.valor}`}
                        className="flex min-h-12 cursor-pointer items-start gap-3 rounded-lg border bg-card p-3 has-[:disabled]:cursor-not-allowed has-[:disabled]:opacity-60"
                      >
                        <Checkbox
                          id={`pago-${m.valor}`}
                          checked={form.metodosPago.includes(m.valor)}
                          onCheckedChange={(c) => alternarMetodo(m.valor, c === true)}
                          className="mt-0.5"
                        />
                        <span className="min-w-0">
                          <span className="block text-sm font-medium">{m.label}</span>
                          <span className="block text-xs text-muted-foreground">{m.ayuda}</span>
                        </span>
                      </label>
                    ))}
                  </div>
                  {errores.metodosPago && (
                    <p role="alert" className="text-xs font-medium text-status-danger-ink">
                      {errores.metodosPago}
                    </p>
                  )}
                </fieldset>
              </div>
            </SectionCard>

            <SectionCard titulo="Notas internas" descripcion="Solo para ti y tu equipo: Victoria no las lee.">
              <div className="p-4 sm:p-5">
                <Campo id="notasInternas" label="Notas" opcional contador={{ actual: form.notasInternas.length, maximo: LIMITE.notasInternas }}>
                  <Textarea
                    id="notasInternas"
                    rows={3}
                    value={form.notasInternas}
                    maxLength={LIMITE.notasInternas}
                    onChange={(e) => poner("notasInternas", e.target.value)}
                  />
                </Campo>
              </div>
            </SectionCard>
          </fieldset>

          {hayCambios && !soloLectura && (
            <div className="sticky bottom-[calc(4.5rem+env(safe-area-inset-bottom))] z-20 md:bottom-4">
              <div className="space-y-3 rounded-xl border bg-card p-3 shadow-lg sm:p-4">
                {errorGuardar && (
                  <div role="alert" className="flex items-start gap-2.5 rounded-lg bg-status-danger-soft p-3 text-sm text-status-danger-ink">
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
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <p className="text-sm font-medium">
                    {Object.keys(errores).length > 0 ? "Revisa los campos marcados" : "Tienes cambios sin guardar"}
                  </p>
                  <div className="flex items-center gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      disabled={guardando}
                      onClick={() => {
                        setForm(inicial);
                        setErrorGuardar(null);
                      }}
                    >
                      Descartar
                    </Button>
                    <Button type="submit" disabled={guardando || Object.keys(errores).length > 0}>
                      {guardando ? (
                        <>
                          <Loader2 className="animate-spin" /> Guardando…
                        </>
                      ) : (
                        "Guardar cambios"
                      )}
                    </Button>
                  </div>
                </div>
              </div>
            </div>
          )}
        </form>

        <div className="lg:col-start-2 lg:row-start-3">
          <HistorialCard historial={detalle.historial} />
        </div>
      </div>
    </>
  );
}
