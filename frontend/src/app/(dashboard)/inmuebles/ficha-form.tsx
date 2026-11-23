"use client";

import { ExternalLink, Loader2, MapPin, Save } from "lucide-react";
import { useState, type FormEvent, type ReactNode } from "react";

import { InfoButton } from "@/components/app/info-button";
import { SectionCard } from "@/components/app/section-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { coordenadasDe, enlaceMapa } from "@/lib/inmuebles";
import { NOMBRE_TIPO_INMUEBLE, type InmuebleDetalle } from "@/types/inmueble";

/** Los campos de texto del formulario (todo se edita como texto y se manda tal cual: el dinero y las medidas nunca son float). */
const CAMPOS = [
  "codigo", "titulo", "tipo", "operacion", "precio", "ciudad", "sector", "direccion", "referenciaLlegada", "latitud", "longitud",
  "terrenoM2", "construccionM2", "frenteM", "fondoM", "pisos", "habitaciones", "banos", "parqueaderos", "uso", "descripcion",
  "caracteristicas", "servicios", "documentacion", "preguntasFrecuentes", "temasNoResponder", "horariosVisita", "encargadoVisitas",
  "notasInternas",
] as const;
type CampoTexto = (typeof CAMPOS)[number];
type Valores = Record<CampoTexto, string> & { mostrarPrecio: boolean; precioNegociable: "si" | "no" | "dueno" };

const ENTEROS: CampoTexto[] = ["pisos", "habitaciones", "parqueaderos"];
const DECIMALES: CampoTexto[] = ["precio", "latitud", "longitud", "terrenoM2", "construccionM2", "frenteM", "fondoM", "banos"];

function inicial(inmueble?: InmuebleDetalle): Valores {
  const v = {} as Valores;
  for (const c of CAMPOS) {
    const actual = inmueble?.[c as keyof InmuebleDetalle];
    v[c] = actual == null ? "" : String(actual);
  }
  if (!inmueble) {
    v.tipo = "casa";
    v.operacion = "venta";
  }
  v.mostrarPrecio = inmueble?.mostrarPrecio ?? false;
  v.precioNegociable = inmueble?.precioNegociable === true ? "si" : inmueble?.precioNegociable === false ? "no" : "dueno";
  return v;
}

/** Lo que se manda a la API: vacío = null; números como texto (la API los valida). Solo lo que cambió, al editar. */
export function cuerpoDe(valores: Valores, original?: InmuebleDetalle): Record<string, unknown> {
  const cuerpo: Record<string, unknown> = {};
  for (const c of CAMPOS) {
    let valor: unknown = valores[c].trim() === "" ? null : valores[c].trim();
    if (valor !== null && ENTEROS.includes(c)) valor = Number(valor);
    if (valor !== null && DECIMALES.includes(c)) valor = String(valor).replace(",", ".");
    if (c === "uso" && valor === "sin_definir") valor = null;
    const anterior = original?.[c as keyof InmuebleDetalle];
    if (!original || String(anterior ?? "") !== String(valor ?? "")) cuerpo[c] = valor;
  }
  const negociable = valores.precioNegociable === "si" ? true : valores.precioNegociable === "no" ? false : null;
  if (!original || original.mostrarPrecio !== valores.mostrarPrecio) cuerpo.mostrarPrecio = valores.mostrarPrecio;
  if (!original || original.precioNegociable !== negociable) cuerpo.precioNegociable = negociable;
  return cuerpo;
}

function Campo({ id, label, children, ayuda, info }: { id: string; label: string; children: ReactNode; ayuda?: string; info?: ReactNode }) {
  return (
    <div className="grid gap-1.5">
      <div className="flex items-center gap-1">
        <Label htmlFor={id}>{label}</Label>
        {info}
      </div>
      {children}
      {ayuda && <p className="text-xs text-muted-foreground">{ayuda}</p>}
    </div>
  );
}

/** La ficha de una propiedad. Sirve para crearla (`inmueble` vacío) y para editarla. */
export function FichaForm({
  inmueble,
  guardando,
  error,
  onGuardar,
  textoGuardar,
}: {
  inmueble?: InmuebleDetalle;
  guardando: boolean;
  error: string | null;
  onGuardar: (cuerpo: Record<string, unknown>) => void;
  textoGuardar: string;
}) {
  const [v, setV] = useState<Valores>(() => inicial(inmueble));
  const [enlace, setEnlace] = useState("");
  const [avisoEnlace, setAvisoEnlace] = useState<string | null>(null);
  const cambiar = (campo: CampoTexto) => (e: { target: { value: string } }) => setV((prev) => ({ ...prev, [campo]: e.target.value }));
  const mapa = enlaceMapa(v.latitud || null, v.longitud || null);
  const cuerpo = cuerpoDe(v, inmueble);
  const hayCambios = Object.keys(cuerpo).length > 0;

  function usarEnlace() {
    const c = coordenadasDe(enlace);
    if (!c) {
      setAvisoEnlace(
        enlace.includes("goo.gl")
          ? "Ese es un enlace corto: ábrelo, y copia el enlace largo de la barra del navegador (o las coordenadas)."
          : "No encontré coordenadas en ese texto. Pega el enlace de Google Maps o las coordenadas (p. ej. -2.1709, -79.9223).",
      );
      return;
    }
    setV((prev) => ({ ...prev, latitud: c.latitud, longitud: c.longitud }));
    setAvisoEnlace(null);
    setEnlace("");
  }

  function enviar(e: FormEvent) {
    e.preventDefault();
    onGuardar(cuerpo);
  }

  const texto = (campo: CampoTexto, label: string, props: { placeholder?: string; ayuda?: string; info?: ReactNode; inputMode?: "decimal" | "numeric" } = {}) => (
    <Campo id={`f-${campo}`} label={label} ayuda={props.ayuda} info={props.info}>
      <Input id={`f-${campo}`} value={v[campo]} onChange={cambiar(campo)} placeholder={props.placeholder} inputMode={props.inputMode} disabled={guardando} />
    </Campo>
  );
  const area = (campo: CampoTexto, label: string, props: { placeholder?: string; ayuda?: string; filas?: number } = {}) => (
    <Campo id={`f-${campo}`} label={label} ayuda={props.ayuda}>
      <Textarea id={`f-${campo}`} value={v[campo]} onChange={cambiar(campo)} placeholder={props.placeholder} rows={props.filas ?? 3} disabled={guardando} />
    </Campo>
  );

  return (
    <form onSubmit={enviar} className="flex flex-col gap-5">
      <SectionCard titulo="Datos generales" descripcion="Qué es y cómo se llama.">
        <div className="grid gap-4 p-4 sm:grid-cols-2 sm:p-5">
          {texto("codigo", "Código", { placeholder: "CASA-GYE-01", ayuda: "Corto y sin espacios. El asistente lo usa para saber de cuál se habla." })}
          {texto("titulo", "Título", { placeholder: "Casa de dos pisos en el norte de Guayaquil" })}
          <Campo id="f-tipo" label="Tipo">
            <Select value={v.tipo} onValueChange={(x) => setV((p) => ({ ...p, tipo: x }))} disabled={guardando}>
              <SelectTrigger id="f-tipo" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {Object.entries(NOMBRE_TIPO_INMUEBLE).map(([valor, nombre]) => (
                  <SelectItem key={valor} value={valor}>
                    {nombre}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Campo>
          <Campo id="f-operacion" label="Operación">
            <Select value={v.operacion} onValueChange={(x) => setV((p) => ({ ...p, operacion: x }))} disabled={guardando}>
              <SelectTrigger id="f-operacion" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="venta">Venta</SelectItem>
                <SelectItem value="alquiler">Alquiler</SelectItem>
              </SelectContent>
            </Select>
          </Campo>
        </div>
      </SectionCard>

      {inmueble && (
        <>
          <SectionCard
            titulo="Ubicación"
            descripcion="Para mandar el pin de WhatsApp y explicar cómo llegar."
            info={
              <InfoButton titulo="Ubicación">
                <p>Con la ubicación en el mapa, el asistente le manda al cliente el pin de WhatsApp (se abre en su app de mapas con un toque).</p>
                <p>
                  Lo más fácil: abre la propiedad en Google Maps, copia el enlace de la barra del navegador y pégalo en «Pegar enlace de
                  Google Maps». Los enlaces cortos (maps.app.goo.gl) no traen las coordenadas: ábrelos primero.
                </p>
              </InfoButton>
            }
          >
            <div className="grid gap-4 p-4 sm:grid-cols-2 sm:p-5">
              {texto("ciudad", "Ciudad", { placeholder: "Guayaquil" })}
              {texto("sector", "Sector", { placeholder: "Norte, cerca de…" })}
              <div className="sm:col-span-2">{texto("direccion", "Dirección", { placeholder: "Av. … y calle …" })}</div>
              <div className="sm:col-span-2">{area("referenciaLlegada", "Cómo llegar", { placeholder: "Frente al parque…, casa esquinera color…", filas: 2 })}</div>
              <div className="grid gap-1.5 sm:col-span-2">
                <Label htmlFor="f-enlace">Pegar enlace de Google Maps</Label>
                <div className="flex gap-2">
                  <Input id="f-enlace" value={enlace} onChange={(e) => setEnlace(e.target.value)} placeholder="https://www.google.com/maps/…" disabled={guardando} />
                  <Button type="button" variant="outline" onClick={usarEnlace} disabled={guardando || !enlace.trim()}>
                    <MapPin /> Usar
                  </Button>
                </div>
                {avisoEnlace && (
                  <p role="alert" className="text-xs font-medium text-status-warning-ink">
                    {avisoEnlace}
                  </p>
                )}
              </div>
              {texto("latitud", "Latitud", { placeholder: "-2.170998", inputMode: "decimal" })}
              {texto("longitud", "Longitud", { placeholder: "-79.922359", inputMode: "decimal" })}
              {mapa && (
                <a href={mapa} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1 text-sm text-primary underline-offset-2 hover:underline sm:col-span-2">
                  <ExternalLink className="size-3.5" aria-hidden /> Ver en Google Maps
                </a>
              )}
            </div>
          </SectionCard>

          <SectionCard titulo="Medidas y distribución" descripcion="Lo que más preguntan los interesados.">
            <div className="grid grid-cols-2 gap-4 p-4 sm:grid-cols-4 sm:p-5">
              {texto("terrenoM2", "Terreno (m²)", { inputMode: "decimal" })}
              {texto("construccionM2", "Construcción (m²)", { inputMode: "decimal" })}
              {texto("frenteM", "Frente (m)", { inputMode: "decimal" })}
              {texto("fondoM", "Fondo (m)", { inputMode: "decimal" })}
              {texto("pisos", "Pisos", { inputMode: "numeric" })}
              {texto("habitaciones", "Habitaciones", { inputMode: "numeric" })}
              {texto("banos", "Baños", { inputMode: "decimal", ayuda: "2,5 = dos y medio" })}
              {texto("parqueaderos", "Parqueaderos", { inputMode: "numeric" })}
              <div className="col-span-2">
                <Campo id="f-uso" label="Uso o zona">
                  <Select value={v.uso || "sin_definir"} onValueChange={(x) => setV((p) => ({ ...p, uso: x === "sin_definir" ? "" : x }))} disabled={guardando}>
                    <SelectTrigger id="f-uso" className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="sin_definir">Sin definir</SelectItem>
                      <SelectItem value="residencial">Residencial</SelectItem>
                      <SelectItem value="comercial">Comercial</SelectItem>
                      <SelectItem value="mixto">Mixto (residencial y comercial)</SelectItem>
                    </SelectContent>
                  </Select>
                </Campo>
              </div>
            </div>
          </SectionCard>

          <SectionCard
            titulo="Precio"
            descripcion="Si el asistente lo dice y si es conversable."
            info={
              <InfoButton titulo="Precio">
                <ul>
                  <li>
                    <strong>Decir el precio apagado:</strong> el asistente no lo dice; si preguntan, responde que te lo indica el
                    propietario y te pasa la conversación.
                  </li>
                  <li>
                    <strong>Encendido:</strong> lo dice tal cual. Nunca da rebajas ni acepta ofertas: si el cliente quiere ofertar, te
                    pasa la conversación.
                  </li>
                </ul>
              </InfoButton>
            }
          >
            <div className="grid gap-4 p-4 sm:grid-cols-2 sm:p-5">
              {texto("precio", "Precio (USD)", { inputMode: "decimal", placeholder: "85000" })}
              <div className="flex items-center justify-between gap-3 self-end rounded-lg border p-3">
                <Label htmlFor="f-mostrar-precio">Que el asistente diga el precio</Label>
                <Switch id="f-mostrar-precio" checked={v.mostrarPrecio} onCheckedChange={(x) => setV((p) => ({ ...p, mostrarPrecio: x }))} disabled={guardando} />
              </div>
              <Campo id="f-negociable" label="¿Es conversable?">
                <Select value={v.precioNegociable} onValueChange={(x) => setV((p) => ({ ...p, precioNegociable: x as Valores["precioNegociable"] }))} disabled={guardando}>
                  <SelectTrigger id="f-negociable" className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="dueno">No decir nada (lo hablo yo)</SelectItem>
                    <SelectItem value="si">Sí, es conversable</SelectItem>
                    <SelectItem value="no">No, es el precio final</SelectItem>
                  </SelectContent>
                </Select>
              </Campo>
            </div>
          </SectionCard>

          <SectionCard titulo="Visitas" descripcion="Cuándo se puede visitar y quién la enseña.">
            <div className="grid gap-4 p-4 sm:grid-cols-2 sm:p-5">
              {area("horariosVisita", "Horarios de visita", { placeholder: "Lunes a sábado de 9:00 a 17:00", filas: 2, ayuda: "El asistente los ofrece como opciones; nunca confirma." })}
              {texto("encargadoVisitas", "Quién la enseña", { placeholder: "Nombre", ayuda: "Interno: no se le dice al cliente." })}
            </div>
          </SectionCard>

          <SectionCard
            titulo="Lo que el asistente puede contar"
            descripcion="Todo lo que no esté aquí, no lo inventa."
            info={
              <InfoButton titulo="Lo que el asistente puede contar">
                <p>
                  El asistente responde SOLO con lo que escribas aquí y en las secciones de arriba. Si le preguntan algo que no está, te
                  pasa la conversación. Las preguntas frecuentes las responde tal cual: escríbelas como «¿Pregunta? Respuesta».
                </p>
              </InfoButton>
            }
          >
            <div className="grid gap-4 p-4 sm:p-5">
              {area("descripcion", "Descripción", { filas: 4 })}
              {area("caracteristicas", "Características", { placeholder: "Patio, terraza, cisterna, cocina equipada…" })}
              {area("servicios", "Servicios", { placeholder: "Agua potable, luz, alcantarillado, internet…", filas: 2 })}
              {area("documentacion", "Papeles", { placeholder: "Escrituras al día, impuestos pagados…", filas: 2 })}
              {area("preguntasFrecuentes", "Preguntas frecuentes", { placeholder: "¿Aceptan crédito hipotecario? Sí, …", filas: 5 })}
              {area("temasNoResponder", "Temas de los que no habla", { placeholder: "Financiamiento, linderos…", filas: 2, ayuda: "Si preguntan por esto, te pasa la conversación." })}
              {area("notasInternas", "Notas internas", { filas: 2, ayuda: "Solo para ti: el asistente no las ve." })}
            </div>
          </SectionCard>
        </>
      )}

      {error && (
        <p role="alert" className="rounded-lg bg-status-danger-soft p-3 text-sm font-medium text-status-danger-ink">
          {error}
        </p>
      )}
      <div className="sticky bottom-24 z-10 flex justify-end md:bottom-4">
        <Button type="submit" size="lg" disabled={guardando || (!!inmueble && !hayCambios)} className="shadow-card">
          {guardando ? <Loader2 className="animate-spin" /> : <Save />} {textoGuardar}
        </Button>
      </div>
    </form>
  );
}
