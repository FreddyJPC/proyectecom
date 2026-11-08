"use client";

import { Loader2, TriangleAlert } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";

import { InfoButton } from "@/components/app/info-button";
import { SectionCard } from "@/components/app/section-card";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { apiFetch, ApiError } from "@/lib/api";
import { normalizarMonto } from "@/lib/format";
import { METODOS_PAGO, type CrearProductoPropioInput, type ProductoBotDetalle } from "@/types/producto-bot";

import { Campo, descripcionDe } from "../../producto/[sku]/campo";
import {
  InfoCategoria,
  InfoControlaStock,
  InfoCostoPropio,
  InfoDescripcion,
  InfoMaxUnidades,
  InfoMetodosPago,
  InfoPreguntasFrecuentes,
  InfoTemasNoResponder,
  InfoTiempoEntrega,
} from "../../producto/[sku]/info-campos";
import { EditorEntregas, aOpciones, type EntregaBorrador } from "../../editor-entregas";
import { SelectorCategoria } from "../../selector-categoria";

// Mismos límites que el backend (backend/src/routes/productos_bot/schemas.py).
const LIMITE = { nombre: 120, descripcion: 1500, variantes: 300, tiempoEntrega: 200, preguntasFrecuentes: 3000, temasNoResponder: 1000 } as const;
const MAX_UNIDADES = 20;
const MAX_STOCK = 1_000_000;

type Formulario = {
  nombre: string;
  descripcion: string;
  categoriaId: number | null;
  precio: string;
  costoPropio: string;
  controlaStock: boolean;
  stock: string;
  variantes: string;
  tiempoEntrega: string;
  metodosPago: string[];
  maxUnidades: string;
  preguntasFrecuentes: string;
  temasNoResponder: string;
  envioIncluido: boolean;
  costoFlete: string;
  entregas: EntregaBorrador[];
};

const INICIAL: Formulario = {
  nombre: "",
  descripcion: "",
  categoriaId: null,
  precio: "",
  costoPropio: "",
  controlaStock: true,
  stock: "",
  variantes: "",
  tiempoEntrega: "",
  metodosPago: ["contraentrega"],
  maxUnidades: "1",
  preguntasFrecuentes: "",
  temasNoResponder: "",
  // Lo normal en un producto propio es cobrar el envío aparte (cuesta distinto según el destino).
  envioIncluido: false,
  costoFlete: "",
  entregas: [],
};

type Errores = Partial<Record<keyof Formulario | "entregas", string>>;

function revisar(f: Formulario) {
  const errores: Errores = {};
  if (!f.nombre.trim()) errores.nombre = "Escribe el nombre del producto.";
  if (!f.descripcion.trim()) errores.descripcion = "La descripción es lo que Victoria sabe del producto: escríbela.";

  const precio = normalizarMonto(f.precio);
  if (precio == null) errores.precio = "Escribe un precio válido mayor que cero, por ejemplo 24.99 (máximo 2 decimales).";

  let costoPropio: string | null = null;
  if (f.costoPropio.trim()) {
    costoPropio = normalizarMonto(f.costoPropio, true);
    if (costoPropio == null) errores.costoPropio = "Escribe un monto válido, por ejemplo 18.00.";
  }

  let stock: number | null = null;
  if (f.controlaStock) {
    if (!/^\d+$/.test(f.stock.trim()) || Number(f.stock) > MAX_STOCK) errores.stock = "Escribe cuántas unidades tienes (un número entero, 0 o más).";
    else stock = Number(f.stock);
  }

  if (!f.tiempoEntrega.trim()) errores.tiempoEntrega = "Indica en cuánto tiempo llega, por ejemplo «1 a 2 días».";
  if (f.metodosPago.length === 0) errores.metodosPago = "Elige al menos un método de pago.";

  const unidades = Number(f.maxUnidades);
  if (!/^\d+$/.test(f.maxUnidades.trim()) || unidades < 1 || unidades > MAX_UNIDADES) errores.maxUnidades = `Entre 1 y ${MAX_UNIDADES} unidades.`;

  let costoFlete: string | null = null;
  if (f.envioIncluido && f.costoFlete.trim()) {
    costoFlete = normalizarMonto(f.costoFlete, true);
    if (costoFlete == null) errores.costoFlete = "Escribe un monto válido, por ejemplo 4.50.";
  }

  const { opciones, errores: erroresEntregas } = aOpciones(f.entregas);
  const mensajesEntregas = f.envioIncluido ? [] : erroresEntregas;
  if (mensajesEntregas.some(Boolean)) errores.entregas = "Revisa las opciones de entrega marcadas.";

  return { errores, precio, costoPropio, stock, unidades, costoFlete, opciones: f.envioIncluido ? [] : opciones, erroresEntregas: mensajesEntregas };
}

/** Formulario para publicar un producto propio (no Rocketfy): todo lo que Victoria necesita para venderlo y lo que tú
 * necesitas para gestionarlo (costo, stock, envío). Se crea como borrador y se completa en su ficha. */
export function FormularioPropio() {
  const router = useRouter();
  const [f, setF] = useState<Formulario>(INICIAL);
  const [intento, setIntento] = useState(false);
  const [guardando, setGuardando] = useState(false);
  const [errorGuardar, setErrorGuardar] = useState<{ mensaje: string; motivos: string[] } | null>(null);

  const r = revisar(f);
  const mostrar = (campo: keyof Errores) => (intento ? r.errores[campo] : undefined);

  function poner<K extends keyof Formulario>(campo: K, valor: Formulario[K]) {
    setF((previo) => ({ ...previo, [campo]: valor }));
  }

  function alternarMetodo(valor: string, marcado: boolean) {
    setF((previo) => {
      const conjunto = new Set(previo.metodosPago);
      if (marcado) conjunto.add(valor);
      else conjunto.delete(valor);
      return { ...previo, metodosPago: METODOS_PAGO.map((m) => m.valor).filter((v) => conjunto.has(v)) };
    });
  }

  async function guardar(e: FormEvent) {
    e.preventDefault();
    setIntento(true);
    setErrorGuardar(null);
    if (Object.keys(r.errores).length > 0 || r.precio == null) return;

    const cuerpo: CrearProductoPropioInput = {
      nombre: f.nombre.trim(),
      descripcion: f.descripcion.trim(),
      precio: r.precio,
      costoPropio: r.costoPropio,
      controlaStock: f.controlaStock,
      stock: r.stock,
      categoriaId: f.categoriaId,
      variantes: f.variantes.trim() || null,
      tiempoEntrega: f.tiempoEntrega.trim(),
      metodosPago: f.metodosPago,
      preguntasFrecuentes: f.preguntasFrecuentes.trim() || null,
      temasNoResponder: f.temasNoResponder.trim() || null,
      maxUnidadesPorPedido: r.unidades,
      envioIncluido: f.envioIncluido,
      costoFleteEstimado: r.costoFlete,
      entregas: r.opciones,
    };

    setGuardando(true);
    try {
      const creado = await apiFetch<ProductoBotDetalle>("/productos-bot/propios", { method: "POST", body: JSON.stringify(cuerpo) });
      toast.success("Producto creado como borrador. Revísalo, pruébalo con Victoria y publícalo.");
      router.push(`/catalogo/producto/${encodeURIComponent(creado.sku)}`);
    } catch (err) {
      setErrorGuardar(err instanceof ApiError ? { mensaje: err.message, motivos: err.bloqueos } : { mensaje: "No se pudo conectar con el servidor.", motivos: [] });
      setGuardando(false);
    }
  }

  return (
    <form onSubmit={guardar} noValidate className="flex max-w-3xl flex-col gap-5">
      <fieldset disabled={guardando} className="contents">
        <legend className="sr-only">Datos del producto propio</legend>

        <SectionCard
          titulo="El producto"
          descripcion="Lo que Victoria sabe y le cuenta al cliente."
          info={
            <InfoButton titulo="El producto">
              <p>
                Todo lo de esta sección lo lee Victoria y <strong>se lo cuenta al cliente tal cual</strong>. Si algo no está aquí, ella no lo inventa: dice que no lo sabe y te pasa la conversación.
              </p>
              <p>Mientras más clara y verdadera sea la ficha, mejor vende Victoria.</p>
            </InfoButton>
          }
        >
          <div className="space-y-5 p-4 sm:p-5">
            <Campo id="nombre" label="Nombre del producto" error={mostrar("nombre")} contador={{ actual: f.nombre.length, maximo: LIMITE.nombre }}>
              <Input id="nombre" value={f.nombre} maxLength={LIMITE.nombre} onChange={(e) => poner("nombre", e.target.value)} aria-invalid={Boolean(mostrar("nombre"))} aria-describedby={descripcionDe("nombre", false, mostrar("nombre"))} />
            </Campo>

            <Campo
              id="descripcion"
              label="Descripción"
              error={mostrar("descripcion")}
              info={<InfoDescripcion />}
              contador={{ actual: f.descripcion.length, maximo: LIMITE.descripcion }}
            >
              <Textarea id="descripcion" rows={5} value={f.descripcion} maxLength={LIMITE.descripcion} onChange={(e) => poner("descripcion", e.target.value)} aria-invalid={Boolean(mostrar("descripcion"))} aria-describedby={descripcionDe("descripcion", false, mostrar("descripcion"))} />
            </Campo>

            <Campo id="categoria" label="Categoría" opcional info={<InfoCategoria />}>
              <SelectorCategoria id="categoria" valor={f.categoriaId} onCambio={(v) => poner("categoriaId", v)} />
            </Campo>

            <Campo
              id="variantes"
              label="Variantes"
              opcional
              ayuda="Separadas por comas."
              info={
                <InfoButton titulo="Variantes">
                  <p>Las tallas, colores o modelos disponibles, separados por comas. Victoria le pregunta al cliente cuál prefiere.</p>
                  <p>El stock es el total del producto: tú verificas la variante al gestionar el pedido.</p>
                </InfoButton>
              }
              contador={{ actual: f.variantes.length, maximo: LIMITE.variantes }}
            >
              <Input id="variantes" value={f.variantes} maxLength={LIMITE.variantes} placeholder="Talla 38, 39, 40, 41, 42" onChange={(e) => poner("variantes", e.target.value)} aria-describedby="variantes-ayuda" />
            </Campo>
          </div>
        </SectionCard>

        <SectionCard
          titulo="Precio, costo y stock"
          descripcion="Lo que paga el cliente y lo que es para ti."
          info={
            <InfoButton titulo="Precio, costo y stock">
              <p>
                El <strong>precio</strong> es lo que paga el cliente por unidad. El <strong>costo</strong> y el <strong>stock</strong> son para ti: Victoria no los menciona.
              </p>
            </InfoButton>
          }
        >
          <div className="space-y-5 p-4 sm:p-5">
            <div className="grid gap-5 sm:grid-cols-2">
              <Campo id="precio" label="Precio de venta ($)" error={mostrar("precio")} ayuda="Por unidad, sin el envío.">
                <Input id="precio" inputMode="decimal" value={f.precio} onChange={(e) => poner("precio", e.target.value)} placeholder="30.00" aria-invalid={Boolean(mostrar("precio"))} aria-describedby={descripcionDe("precio", true, mostrar("precio"))} className="tabular" />
              </Campo>
              <Campo id="costoPropio" label="Lo que te cuesta ($)" opcional error={mostrar("costoPropio")} ayuda="Por unidad." info={<InfoCostoPropio />}>
                <Input id="costoPropio" inputMode="decimal" value={f.costoPropio} onChange={(e) => poner("costoPropio", e.target.value)} placeholder="18.00" aria-invalid={Boolean(mostrar("costoPropio"))} aria-describedby={descripcionDe("costoPropio", true, mostrar("costoPropio"))} className="tabular" />
              </Campo>
            </div>

            <div className="flex items-start gap-3 rounded-lg border bg-card p-3">
              <Switch id="controlaStock" checked={f.controlaStock} onCheckedChange={(c) => poner("controlaStock", c)} className="mt-0.5" aria-describedby="controlaStock-ayuda" />
              <div className="min-w-0">
                <div className="flex items-center gap-1">
                  <label htmlFor="controlaStock" className="text-sm font-medium">
                    Llevar la cuenta de las unidades
                  </label>
                  <InfoControlaStock />
                </div>
                <p id="controlaStock-ayuda" className="text-xs text-muted-foreground">
                  {f.controlaStock ? "Cada venta descuenta del stock." : "Siempre disponible."}
                </p>
              </div>
            </div>

            {f.controlaStock && (
              <Campo id="stock" label="Unidades que tienes" error={mostrar("stock")} ayuda="Total, sumando todas las variantes.">
                <Input id="stock" type="number" inputMode="numeric" min={0} max={MAX_STOCK} value={f.stock} onChange={(e) => poner("stock", e.target.value)} aria-invalid={Boolean(mostrar("stock"))} aria-describedby={descripcionDe("stock", true, mostrar("stock"))} className="tabular w-32" />
              </Campo>
            )}
          </div>
        </SectionCard>

        <SectionCard
          titulo="Envío"
          descripcion="Cómo se entrega y cuánto cobras."
          info={
            <InfoButton titulo="Envío de este producto">
              <p>Defínelo para este producto: cuánto cobras, dónde entregas y si el cliente puede retirar. Cada producto tiene su propio envío.</p>
              <p>Podrás cambiarlo después desde la ficha del producto.</p>
            </InfoButton>
          }
        >
          <div className="p-4 sm:p-5">
            <EditorEntregas
              envioIncluido={f.envioIncluido}
              onEnvioIncluido={(v) => poner("envioIncluido", v)}
              entregas={f.entregas}
              onEntregas={(v) => poner("entregas", v)}
              errores={intento ? r.erroresEntregas : []}
              costoFlete={f.costoFlete}
              onCostoFlete={(v) => poner("costoFlete", v)}
              errorFlete={mostrar("costoFlete")}
            />
          </div>
        </SectionCard>

        <SectionCard titulo="Reglas de venta" descripcion="Cómo y cuánto puede comprar el cliente.">
          <div className="space-y-5 p-4 sm:p-5">
            <Campo id="tiempoEntrega" label="Tiempo de entrega" error={mostrar("tiempoEntrega")} ayuda="Por ejemplo: «1 a 2 días en Cuenca, 3 a 5 días fuera»." info={<InfoTiempoEntrega />} contador={{ actual: f.tiempoEntrega.length, maximo: LIMITE.tiempoEntrega }}>
              <Input id="tiempoEntrega" value={f.tiempoEntrega} maxLength={LIMITE.tiempoEntrega} onChange={(e) => poner("tiempoEntrega", e.target.value)} aria-invalid={Boolean(mostrar("tiempoEntrega"))} aria-describedby={descripcionDe("tiempoEntrega", true, mostrar("tiempoEntrega"))} />
            </Campo>

            <Campo id="maxUnidades" label="Unidades máximas por pedido" error={mostrar("maxUnidades")} info={<InfoMaxUnidades />}>
              <Input id="maxUnidades" type="number" inputMode="numeric" min={1} max={MAX_UNIDADES} value={f.maxUnidades} onChange={(e) => poner("maxUnidades", e.target.value)} aria-invalid={Boolean(mostrar("maxUnidades"))} aria-describedby={descripcionDe("maxUnidades", false, mostrar("maxUnidades"))} className="tabular w-28" />
            </Campo>

            <fieldset className="grid gap-1.5">
              <legend className="mb-1.5 flex items-center gap-1 text-sm font-medium">
                Métodos de pago que acepta <InfoMetodosPago />
              </legend>
              <div className="grid gap-2 sm:grid-cols-2">
                {METODOS_PAGO.map((m) => (
                  <label key={m.valor} htmlFor={`pago-${m.valor}`} className="flex min-h-12 cursor-pointer items-start gap-3 rounded-lg border bg-card p-3">
                    <Checkbox id={`pago-${m.valor}`} checked={f.metodosPago.includes(m.valor)} onCheckedChange={(c) => alternarMetodo(m.valor, c === true)} className="mt-0.5" />
                    <span className="min-w-0">
                      <span className="block text-sm font-medium">{m.label}</span>
                      <span className="block text-xs text-muted-foreground">{m.ayuda}</span>
                    </span>
                  </label>
                ))}
              </div>
              {mostrar("metodosPago") && (
                <p role="alert" className="text-xs font-medium text-status-danger-ink">
                  {mostrar("metodosPago")}
                </p>
              )}
            </fieldset>
          </div>
        </SectionCard>

        <SectionCard titulo="Para que Victoria conteste mejor" descripcion="Opcional. Puedes completarlo después en la ficha.">
          <div className="space-y-5 p-4 sm:p-5">
            <Campo id="preguntasFrecuentes" label="Preguntas frecuentes" opcional info={<InfoPreguntasFrecuentes />} contador={{ actual: f.preguntasFrecuentes.length, maximo: LIMITE.preguntasFrecuentes }}>
              <Textarea id="preguntasFrecuentes" rows={4} value={f.preguntasFrecuentes} maxLength={LIMITE.preguntasFrecuentes} onChange={(e) => poner("preguntasFrecuentes", e.target.value)} />
            </Campo>
            <Campo id="temasNoResponder" label="Temas que Victoria NO debe responder" opcional info={<InfoTemasNoResponder />} contador={{ actual: f.temasNoResponder.length, maximo: LIMITE.temasNoResponder }}>
              <Textarea id="temasNoResponder" rows={3} value={f.temasNoResponder} maxLength={LIMITE.temasNoResponder} onChange={(e) => poner("temasNoResponder", e.target.value)} />
            </Campo>
          </div>
        </SectionCard>
      </fieldset>

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

      {intento && Object.keys(r.errores).length > 0 && (
        <p role="alert" className="text-sm font-medium text-status-danger-ink">
          Revisa los campos marcados antes de crear el producto.
        </p>
      )}

      <div className="flex flex-wrap items-center justify-end gap-2">
        <Button type="submit" disabled={guardando}>
          {guardando ? (
            <>
              <Loader2 className="animate-spin" /> Creando…
            </>
          ) : (
            "Crear como borrador"
          )}
        </Button>
      </div>
    </form>
  );
}
