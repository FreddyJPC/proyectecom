"use client";

import { Link2, Loader2, Plus, Trash2, TriangleAlert } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { InfoButton } from "@/components/app/info-button";
import { SectionCard } from "@/components/app/section-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { useApi } from "@/hooks/use-api";
import { apiFetch, ApiError } from "@/lib/api";
import { aCentavos, deCentavos, formatMoney, normalizarMonto, normalizarPorcentaje } from "@/lib/format";
import type { Oferta } from "@/types/precios";
import type { ProductoBotResumen } from "@/types/producto-bot";

type Item = { productoSku: string; cantidad: string; variante: string };

const ZONA = "America/Guayaquil";

/** ISO del servidor -> valor de un <input type="datetime-local"> en hora de Ecuador. */
function aLocal(iso: string | null): string {
  if (!iso) return "";
  const partes = new Intl.DateTimeFormat("en-CA", {
    timeZone: ZONA, year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23",
  }).formatToParts(new Date(iso));
  const p = (t: string) => partes.find((x) => x.type === t)?.value ?? "00";
  return `${p("year")}-${p("month")}-${p("day")}T${p("hour")}:${p("minute")}`;
}

/** Valor del <input> (hora de Ecuador, sin horario de verano) -> ISO con zona. */
function aIso(local: string): string | null {
  return local ? `${local}:00-05:00` : null;
}

function leerRegla(tipo: string, texto: string): string | null {
  return tipo === "porcentaje" ? normalizarPorcentaje(texto) : normalizarMonto(texto);
}

export function FormularioOferta({ oferta, onGuardada }: { oferta?: Oferta; onGuardada?: () => void }) {
  const router = useRouter();
  const productos = useApi<ProductoBotResumen[]>("/productos-bot");
  const elegibles = (productos.data ?? []).filter((p) => p.estado !== "archivado");

  const [nombre, setNombre] = useState(oferta?.nombre ?? "");
  const [items, setItems] = useState<Item[]>(
    oferta?.items.map((i) => ({ productoSku: i.productoSku, cantidad: String(i.cantidad), variante: i.variante ?? "" })) ?? [{ productoSku: "", cantidad: "1", variante: "" }],
  );
  const [precio, setPrecio] = useState(oferta?.precio ?? "");
  const [envioIncluido, setEnvioIncluido] = useState(oferta?.envioIncluido ?? true);
  const [desde, setDesde] = useState(aLocal(oferta?.desde ?? null));
  const [hasta, setHasta] = useState(aLocal(oferta?.hasta ?? null));
  const [cupo, setCupo] = useState(oferta?.cupo != null ? String(oferta.cupo) : "");
  const [maximo, setMaximo] = useState(String(oferta?.maximoPorCliente ?? 1));
  const [visibilidad, setVisibilidad] = useState<string>(oferta?.visibilidad ?? "anuncio");
  const [regTipo, setRegTipo] = useState<string>(oferta?.regateoTipo ?? "ninguno");
  const [regValor, setRegValor] = useState(oferta?.regateoValor ?? "");
  const [trTipo, setTrTipo] = useState<string>(oferta?.transferenciaTipo ?? "ninguno");
  const [trValor, setTrValor] = useState(oferta?.transferenciaValor ?? "");
  const [descripcion, setDescripcion] = useState(oferta?.descripcion ?? "");
  const [textoAnuncio, setTextoAnuncio] = useState(oferta?.textoAnuncio ?? "");
  const [estado, setEstado] = useState<string>(oferta?.estado ?? "activa");
  const [bajoMargenAutorizado, setBajoMargenAutorizado] = useState(oferta?.bajoMargenAutorizado ?? false);
  const [intento, setIntento] = useState(false);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<{ mensaje: string; motivos: string[] } | null>(null);
  const [bajoMargen, setBajoMargen] = useState<string[] | null>(null);

  const precioNormal = normalizarMonto(precio);
  const listaCentavos = items.reduce((total, it) => {
    const p = elegibles.find((x) => x.sku === it.productoSku);
    const c = Number(it.cantidad);
    return total + (p && Number.isInteger(c) && c > 0 ? (aCentavos(p.precio) ?? 0) * c : 0);
  }, 0);
  const precioCentavos = aCentavos(precioNormal);
  const ahorro = precioCentavos !== null && listaCentavos > 0 ? listaCentavos - precioCentavos : null;

  const errores = {
    nombre: nombre.trim() === "" ? "Ponle un nombre a la oferta." : undefined,
    items: items.some((i) => !i.productoSku || !/^\d+$/.test(i.cantidad) || Number(i.cantidad) < 1) ? "Elige cada producto y su cantidad." : undefined,
    precio: precioNormal === null ? "Escribe el precio total." : ahorro !== null && ahorro < 0 ? "Es más caro que comprar los productos por separado." : undefined,
    fechas: desde && hasta && hasta <= desde ? "La fecha de fin debe ser posterior a la de inicio." : undefined,
    cupo: cupo.trim() !== "" && !/^\d+$/.test(cupo.trim()) ? "Escribe un número entero." : undefined,
    maximo: !/^\d+$/.test(maximo.trim()) || Number(maximo) < 1 ? "Debe ser 1 o más." : undefined,
    regateo: regTipo !== "ninguno" && leerRegla(regTipo, regValor) === null ? "Escribe un valor válido." : undefined,
    transferencia: trTipo !== "ninguno" && leerRegla(trTipo, trValor) === null ? "Escribe un valor válido." : undefined,
  };
  const hayErrores = Object.values(errores).some(Boolean);
  const err = (clave: keyof typeof errores) => (intento ? errores[clave] : undefined);

  async function guardar(autorizarBajoMargen = bajoMargenAutorizado) {
    setIntento(true);
    setError(null);
    if (hayErrores) return;
    setGuardando(true);
    const cuerpo = {
      nombre: nombre.trim(),
      items: items.map((i) => ({ productoSku: i.productoSku, cantidad: Number(i.cantidad), variante: i.variante.trim() || null })),
      precio: precioNormal,
      envioIncluido,
      desde: aIso(desde),
      hasta: aIso(hasta),
      cupo: cupo.trim() === "" ? null : Number(cupo),
      maximoPorCliente: Number(maximo),
      visibilidad,
      regateoTipo: regTipo === "ninguno" ? null : regTipo,
      regateoValor: regTipo === "ninguno" ? null : leerRegla(regTipo, regValor),
      transferenciaTipo: trTipo === "ninguno" ? null : trTipo,
      transferenciaValor: trTipo === "ninguno" ? null : leerRegla(trTipo, trValor),
      descripcion: descripcion.trim() || null,
      textoAnuncio: textoAnuncio.trim() || null,
      bajoMargenAutorizado: autorizarBajoMargen,
      ...(oferta ? { estado } : {}),
    };
    try {
      const guardada = await apiFetch<Oferta>(oferta ? `/precios/ofertas/${oferta.id}` : "/precios/ofertas", {
        method: oferta ? "PUT" : "POST",
        body: JSON.stringify(cuerpo),
      });
      toast.success(oferta ? "Oferta guardada." : "Oferta creada. Ahora vincúlala a su anuncio.");
      setBajoMargen(null);
      if (oferta) onGuardada?.();
      else router.push(`/ofertas/${guardada.id}`);
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) setBajoMargen(e.bloqueos);
      else setError(e instanceof ApiError ? { mensaje: e.message, motivos: e.bloqueos } : { mensaje: "No se pudo conectar con el servidor.", motivos: [] });
    } finally {
      setGuardando(false);
    }
  }

  const off = guardando;

  return (
    <div className="flex flex-col gap-5 pb-28 md:pb-6">
      <SectionCard titulo="Qué incluye" descripcion="Productos, precio y envío.">
        <div className="space-y-4 p-4 sm:p-5">
          <div className="grid gap-1.5">
            <Label htmlFor="of-nombre">Nombre</Label>
            <Input id="of-nombre" value={nombre} onChange={(e) => setNombre(e.target.value)} maxLength={120} placeholder="Linterna + cargador" aria-invalid={Boolean(err("nombre"))} disabled={off} />
            {err("nombre") && <p className="text-xs text-status-danger-ink">{err("nombre")}</p>}
          </div>

          <fieldset className="space-y-3">
            <legend className="mb-1 text-sm font-medium">Productos</legend>
            {items.map((it, i) => (
              <div key={i} className="grid grid-cols-[minmax(0,1fr)_4.5rem_auto] items-end gap-2 sm:grid-cols-[minmax(0,1fr)_5rem_minmax(0,10rem)_auto]">
                <div className="grid min-w-0 gap-1.5">
                  <Label htmlFor={`of-p-${i}`}>Producto</Label>
                  <Select value={it.productoSku} onValueChange={(v) => setItems(items.map((x, j) => (j === i ? { ...x, productoSku: v } : x)))} disabled={off}>
                    <SelectTrigger id={`of-p-${i}`} className="w-full">
                      <SelectValue placeholder="Elige un producto" />
                    </SelectTrigger>
                    <SelectContent>
                      {elegibles.map((p) => (
                        <SelectItem key={p.sku} value={p.sku}>
                          {p.nombre} · {formatMoney(p.precio)}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid gap-1.5">
                  <Label htmlFor={`of-c-${i}`}>Cant.</Label>
                  <Input id={`of-c-${i}`} inputMode="numeric" value={it.cantidad} onChange={(e) => setItems(items.map((x, j) => (j === i ? { ...x, cantidad: e.target.value } : x)))} className="tabular" disabled={off} />
                </div>
                <div className="col-span-3 grid gap-1.5 sm:col-span-1 sm:row-start-1 sm:col-start-3">
                  <Label htmlFor={`of-v-${i}`}>
                    Variante <span className="font-normal text-muted-foreground">(opcional)</span>
                  </Label>
                  <Input id={`of-v-${i}`} value={it.variante} onChange={(e) => setItems(items.map((x, j) => (j === i ? { ...x, variante: e.target.value } : x)))} placeholder="Ej.: negro" disabled={off} />
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="size-10 sm:col-start-4 sm:row-start-1"
                  aria-label="Quitar este producto"
                  disabled={off || items.length === 1}
                  onClick={() => setItems(items.filter((_, j) => j !== i))}
                >
                  <Trash2 />
                </Button>
              </div>
            ))}
            {err("items") && <p className="text-xs text-status-danger-ink">{err("items")}</p>}
            <Button type="button" variant="outline" size="sm" disabled={off || items.length >= 6} onClick={() => setItems([...items, { productoSku: "", cantidad: "1", variante: "" }])}>
              <Plus /> Agregar producto
            </Button>
          </fieldset>

          <div className="grid gap-3 border-t pt-4 sm:grid-cols-2 sm:items-end">
            <div className="grid gap-1.5">
              <Label htmlFor="of-precio">Precio total de la oferta ($)</Label>
              <Input id="of-precio" inputMode="decimal" value={precio} onChange={(e) => setPrecio(e.target.value)} aria-invalid={Boolean(err("precio"))} aria-describedby="of-precio-ayuda" className="tabular" disabled={off} />
            </div>
            <p id="of-precio-ayuda" className="text-sm text-muted-foreground" aria-live="polite">
              {err("precio") ? (
                <span className="text-status-danger-ink">{err("precio")}</span>
              ) : listaCentavos > 0 ? (
                <>
                  Por separado: <span className="tabular">{formatMoney(deCentavos(listaCentavos))}</span>
                  {ahorro !== null && ahorro > 0 && (
                    <>
                      {" "}· el cliente ahorra <strong className="tabular text-foreground">{formatMoney(deCentavos(ahorro))}</strong>
                    </>
                  )}
                </>
              ) : null}
            </p>
          </div>

          <div className="flex items-center justify-between gap-3 border-t pt-4">
            <Label htmlFor="of-envio">Envío incluido en el precio</Label>
            <Switch id="of-envio" checked={envioIncluido} onCheckedChange={setEnvioIncluido} disabled={off} />
          </div>
        </div>
      </SectionCard>

      <SectionCard
        titulo="Cuándo y para quién"
        descripcion="Fechas, cupo y quién la puede pedir."
        info={
          <InfoButton titulo="Fechas, cupo y visibilidad">
            <p>Fuera de las fechas o sin cupo, Victoria explica que la oferta terminó y ofrece el precio normal (o te pasa la conversación, según Parámetros).</p>
            <p>Las horas son de Ecuador. Deja las fechas vacías si la oferta no vence.</p>
            <p><strong>Solo su anuncio:</strong> la recibe quien llega por un anuncio vinculado a esta oferta. <strong>Cualquier cliente:</strong> Victoria la puede ofrecer a todos.</p>
          </InfoButton>
        }
      >
        <div className="grid gap-4 p-4 sm:grid-cols-2 sm:p-5">
          <div className="grid gap-1.5">
            <Label htmlFor="of-desde">Desde</Label>
            <Input id="of-desde" type="datetime-local" value={desde} onChange={(e) => setDesde(e.target.value)} disabled={off} />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="of-hasta">Hasta</Label>
            <Input id="of-hasta" type="datetime-local" value={hasta} onChange={(e) => setHasta(e.target.value)} aria-invalid={Boolean(err("fechas"))} disabled={off} />
            {err("fechas") && <p className="text-xs text-status-danger-ink">{err("fechas")}</p>}
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="of-cupo">
              Cupo de ventas <span className="font-normal text-muted-foreground">(vacío = sin límite)</span>
            </Label>
            <Input id="of-cupo" inputMode="numeric" value={cupo} onChange={(e) => setCupo(e.target.value)} aria-invalid={Boolean(err("cupo"))} className="tabular" disabled={off} />
            {err("cupo") && <p className="text-xs text-status-danger-ink">{err("cupo")}</p>}
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="of-max">Veces por cliente</Label>
            <Input id="of-max" inputMode="numeric" value={maximo} onChange={(e) => setMaximo(e.target.value)} aria-invalid={Boolean(err("maximo"))} className="tabular" disabled={off} />
            {err("maximo") && <p className="text-xs text-status-danger-ink">{err("maximo")}</p>}
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="of-vis">Quién la puede pedir</Label>
            <Select value={visibilidad} onValueChange={setVisibilidad} disabled={off}>
              <SelectTrigger id="of-vis" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="anuncio">Solo quien llega por su anuncio</SelectItem>
                <SelectItem value="publica">Cualquier cliente</SelectItem>
              </SelectContent>
            </Select>
          </div>
          {oferta && (
            <div className="grid gap-1.5">
              <Label htmlFor="of-estado">Estado</Label>
              <Select value={estado} onValueChange={setEstado} disabled={off}>
                <SelectTrigger id="of-estado" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="activa">Activa</SelectItem>
                  <SelectItem value="pausada">Pausada</SelectItem>
                  <SelectItem value="archivada">Archivada</SelectItem>
                </SelectContent>
              </Select>
            </div>
          )}
        </div>
      </SectionCard>

      <SectionCard
        titulo="Rebajas dentro de la oferta"
        descripcion="Por defecto, un combo no se regatea."
        info={
          <InfoButton titulo="Rebajas en una oferta">
            <p>El combo ya es el descuento: por defecto Victoria no lo regatea. Si quieres, permite un regateo pequeño.</p>
            <p>También puedes darle un precio especial por transferencia. El regateo y la transferencia no se suman: el cliente paga el menor.</p>
          </InfoButton>
        }
      >
        <div className="grid gap-4 p-4 sm:grid-cols-2 sm:p-5">
          <div className="grid content-start gap-1.5">
            <Label htmlFor="of-reg">Regateo</Label>
            <Select value={regTipo} onValueChange={setRegTipo} disabled={off}>
              <SelectTrigger id="of-reg" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="ninguno">No se regatea</SelectItem>
                <SelectItem value="porcentaje">Hasta un porcentaje</SelectItem>
                <SelectItem value="monto">Hasta un monto</SelectItem>
              </SelectContent>
            </Select>
            {regTipo !== "ninguno" && (
              <Input aria-label={regTipo === "porcentaje" ? "Hasta qué porcentaje" : "Hasta qué monto"} inputMode="decimal" value={regValor} onChange={(e) => setRegValor(e.target.value)} aria-invalid={Boolean(err("regateo"))} className="tabular" disabled={off} />
            )}
            {err("regateo") && <p className="text-xs text-status-danger-ink">{err("regateo")}</p>}
          </div>
          <div className="grid content-start gap-1.5">
            <Label htmlFor="of-tr">Pagando por transferencia</Label>
            <Select value={trTipo} onValueChange={setTrTipo} disabled={off}>
              <SelectTrigger id="of-tr" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="ninguno">Mismo precio</SelectItem>
                <SelectItem value="precio">Precio fijo</SelectItem>
                <SelectItem value="porcentaje">Porcentaje menos</SelectItem>
                <SelectItem value="monto">Dólares menos</SelectItem>
              </SelectContent>
            </Select>
            {trTipo !== "ninguno" && (
              <Input aria-label="Valor del precio por transferencia" inputMode="decimal" value={trValor} onChange={(e) => setTrValor(e.target.value)} aria-invalid={Boolean(err("transferencia"))} className="tabular" disabled={off} />
            )}
            {err("transferencia") && <p className="text-xs text-status-danger-ink">{err("transferencia")}</p>}
          </div>
        </div>
      </SectionCard>

      <SectionCard
        titulo="Lo que sabe Victoria"
        descripcion="Condiciones y el texto del anuncio."
        info={
          <InfoButton titulo="Lo que sabe Victoria">
            <p><strong>Condiciones:</strong> lo que incluye y cualquier detalle que Victoria deba saber (colores disponibles, regalo, etc.).</p>
            <p><strong>Texto del anuncio:</strong> copia lo que dice tu anuncio. Victoria lo lee para no contradecirlo.</p>
          </InfoButton>
        }
      >
        <div className="grid gap-4 p-4 sm:p-5">
          <div className="grid gap-1.5">
            <Label htmlFor="of-desc">Condiciones</Label>
            <Textarea id="of-desc" value={descripcion} onChange={(e) => setDescripcion(e.target.value)} maxLength={1000} rows={3} disabled={off} />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="of-texto">Texto del anuncio</Label>
            <Textarea id="of-texto" value={textoAnuncio} onChange={(e) => setTextoAnuncio(e.target.value)} maxLength={1000} rows={3} disabled={off} />
          </div>
        </div>
      </SectionCard>

      {oferta && <AnunciosDeLaOferta oferta={oferta} onCambio={() => onGuardada?.()} />}

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
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="bg-card text-foreground"
            disabled={guardando}
            onClick={() => {
              setBajoMargenAutorizado(true);
              void guardar(true);
            }}
          >
            Vender bajo mi margen, a propósito
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

      <div className="flex flex-wrap justify-end gap-2">
        <Button type="button" variant="outline" disabled={guardando} onClick={() => router.push("/ofertas")}>
          Volver
        </Button>
        <Button type="button" disabled={guardando} onClick={() => void guardar()}>
          {guardando ? (
            <>
              <Loader2 className="animate-spin" /> Guardando…
            </>
          ) : oferta ? (
            "Guardar oferta"
          ) : (
            "Crear oferta"
          )}
        </Button>
      </div>
    </div>
  );
}

/** Los anuncios que promocionan esta oferta: quien llegue por ellos la recibe. */
function AnunciosDeLaOferta({ oferta, onCambio }: { oferta: Oferta; onCambio: () => void }) {
  const [id, setId] = useState("");
  const [guardando, setGuardando] = useState(false);
  const [aviso, setAviso] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function vincular(reasignar = false) {
    const limpio = id.trim();
    if (!/^[\w.-]{1,64}$/.test(limpio)) {
      setError("Escribe el ID del anuncio (lo ves en el Administrador de anuncios de Meta).");
      return;
    }
    setGuardando(true);
    setError(null);
    try {
      await apiFetch(`/precios/ofertas/${oferta.id}/anuncios/${encodeURIComponent(limpio)}`, { method: "PUT", body: JSON.stringify({ reasignar }) });
      toast.success("Anuncio vinculado a la oferta.");
      setId("");
      setAviso(null);
      onCambio();
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) setAviso(e.message);
      else setError(e instanceof ApiError ? e.message : "No se pudo conectar con el servidor.");
    } finally {
      setGuardando(false);
    }
  }

  return (
    <SectionCard
      titulo="Anuncios de esta oferta"
      descripcion="Quien llegue por ellos recibe esta oferta."
      info={
        <InfoButton titulo="Vincular anuncios">
          <p>Escribe el ID del anuncio (columna «ID del anuncio» en el Administrador de anuncios de Meta). Puedes hacerlo antes de publicarlo.</p>
          <p>Un anuncio vende una sola cosa: un producto o una oferta. Si ya estaba vinculado a otra, te pedimos confirmar el cambio.</p>
        </InfoButton>
      }
    >
      <div className="space-y-3 p-4 sm:p-5">
        {oferta.anuncios.length === 0 ? (
          <p className="text-sm text-muted-foreground">Ningún anuncio vinculado todavía.</p>
        ) : (
          <ul className="flex flex-wrap gap-2">
            {oferta.anuncios.map((a) => (
              <li key={a} className="tabular rounded-full bg-muted px-3 py-1 text-sm">
                {a}
              </li>
            ))}
          </ul>
        )}
        <div className="flex flex-wrap items-end gap-2">
          <div className="grid min-w-0 flex-1 gap-1.5 sm:max-w-xs">
            <Label htmlFor="of-anuncio">ID del anuncio</Label>
            <Input id="of-anuncio" inputMode="numeric" value={id} onChange={(e) => setId(e.target.value)} placeholder="120210000123456" className="tabular" disabled={guardando} />
          </div>
          <Button type="button" variant="outline" disabled={guardando || id.trim() === ""} onClick={() => void vincular()}>
            <Link2 /> Vincular
          </Button>
        </div>
        {aviso && (
          <div role="alert" className="space-y-2 rounded-lg bg-status-warning-soft p-3 text-sm text-status-warning-ink">
            <p>{aviso}</p>
            <Button type="button" size="sm" variant="outline" className="bg-card text-foreground" disabled={guardando} onClick={() => void vincular(true)}>
              Sí, que venda esta oferta
            </Button>
          </div>
        )}
        {error && (
          <p role="alert" className="text-sm text-status-danger-ink">
            {error}
          </p>
        )}
      </div>
    </SectionCard>
  );
}
