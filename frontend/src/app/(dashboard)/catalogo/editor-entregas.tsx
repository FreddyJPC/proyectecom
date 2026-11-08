"use client";

import { ArrowDown, ArrowUp, Plus, Trash2 } from "lucide-react";
import { useId } from "react";

import { InfoAviso, InfoButton, InfoEjemplo } from "@/components/app/info-button";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { normalizarMonto } from "@/lib/format";
import type { OpcionEntrega, OpcionEntregaInput } from "@/types/producto-bot";

/** Máximo de opciones por producto (espejo de `MAXIMO_OPCIONES_POR_PRODUCTO` en el backend). */
export const MAXIMO_OPCIONES = 12;

type Alcance = "cantones" | "provincias" | "resto";

/** Una opción tal como se edita: todo texto, para poder escribir con libertad. */
export type EntregaBorrador = {
  /** Identidad estable en la lista (no es el id de la base). */
  clave: string;
  nombre: string;
  tipo: "envio" | "retiro";
  costoCliente: string;
  costoNegocio: string;
  alcance: Alcance;
  /** Cantones o provincias separados por coma. */
  lugares: string;
  direccionRetiro: string;
  tiempoEntrega: string;
  activo: boolean;
};

let contador = 0;
const nuevaClave = () => `opcion-${++contador}`;

export function borradorVacio(tipo: "envio" | "retiro" = "envio"): EntregaBorrador {
  return {
    clave: nuevaClave(),
    nombre: "",
    tipo,
    costoCliente: "",
    costoNegocio: "",
    alcance: "resto",
    lugares: "",
    direccionRetiro: "",
    tiempoEntrega: "",
    activo: true,
  };
}

export function desdeOpciones(opciones: OpcionEntrega[]): EntregaBorrador[] {
  return opciones.map((o) => ({
    clave: nuevaClave(),
    nombre: o.nombre,
    tipo: o.tipo,
    costoCliente: o.costoCliente,
    costoNegocio: o.costoNegocio ?? "",
    alcance: o.restoDelPais ? "resto" : o.cantones.length > 0 ? "cantones" : o.provincias.length > 0 ? "provincias" : "resto",
    lugares: (o.restoDelPais ? [] : o.cantones.length > 0 ? o.cantones : o.provincias).join(", "),
    direccionRetiro: o.direccionRetiro ?? "",
    tiempoEntrega: o.tiempoEntrega ?? "",
    activo: o.activo,
  }));
}

function lista(texto: string): string[] {
  return texto
    .split(",")
    .map((x) => x.trim())
    .filter(Boolean);
}

/** Convierte lo escrito en lo que espera el backend, con los mismos requisitos. `errores[i]` es el
 * mensaje de la opción i (vacío si está bien). */
export function aOpciones(borradores: EntregaBorrador[]): { opciones: OpcionEntregaInput[]; errores: string[] } {
  const errores: string[] = [];
  const opciones: OpcionEntregaInput[] = borradores.map((b, i) => {
    const numero = i + 1;
    let error = "";
    const nombre = b.nombre.trim();
    if (!nombre) error = `Opción ${numero}: falta el nombre (por ejemplo «Envío dentro de Cuenca»).`;

    const costo = b.costoCliente.trim() === "" ? "0.00" : normalizarMonto(b.costoCliente, true);
    if (!error && costo === null) error = `Opción ${numero}: «lo que paga el cliente» debe ser un monto, por ejemplo 2.50 (0 si es gratis).`;

    const negocio = b.costoNegocio.trim() === "" ? null : normalizarMonto(b.costoNegocio, true);
    if (!error && b.costoNegocio.trim() !== "" && negocio === null) error = `Opción ${numero}: «lo que te cuesta» debe ser un monto, por ejemplo 1.50.`;

    const lugares = lista(b.lugares);
    if (!error && b.tipo === "envio" && b.alcance !== "resto" && lugares.length === 0) {
      error = `Opción ${numero}: escribe a qué ${b.alcance === "cantones" ? "cantones" : "provincias"} aplica, o elige «el resto del país».`;
    }
    if (!error && b.tipo === "retiro" && !b.direccionRetiro.trim()) error = `Opción ${numero}: un retiro necesita la dirección donde se retira.`;
    errores.push(error);

    const esRetiro = b.tipo === "retiro";
    return {
      nombre,
      tipo: b.tipo,
      costoCliente: costo ?? "0.00",
      costoNegocio: negocio,
      cantones: !esRetiro && b.alcance === "cantones" ? lugares : [],
      provincias: !esRetiro && b.alcance === "provincias" ? lugares : [],
      restoDelPais: !esRetiro && b.alcance === "resto",
      direccionRetiro: esRetiro ? b.direccionRetiro.trim() : null,
      tiempoEntrega: b.tiempoEntrega.trim() || null,
      activo: b.activo,
    };
  });
  return { opciones, errores };
}

const ALCANCES: { valor: Alcance; label: string }[] = [
  { valor: "cantones", label: "Solo estos cantones" },
  { valor: "provincias", label: "Solo estas provincias" },
  { valor: "resto", label: "El resto del país" },
];

function Opcion({
  b,
  indice,
  total,
  error,
  deshabilitado,
  onCambio,
  onQuitar,
  onMover,
}: {
  b: EntregaBorrador;
  indice: number;
  total: number;
  error: string;
  deshabilitado: boolean;
  onCambio: (cambios: Partial<EntregaBorrador>) => void;
  onQuitar: () => void;
  onMover: (direccion: -1 | 1) => void;
}) {
  const id = useId();
  const numero = indice + 1;
  const retiro = b.tipo === "retiro";

  return (
    <li className="space-y-3 rounded-xl border bg-card p-3 sm:p-4">
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm font-semibold">Opción {numero}</p>
        <div className="flex items-center gap-1">
          <Button type="button" variant="ghost" size="icon" disabled={deshabilitado || indice === 0} onClick={() => onMover(-1)} aria-label={`Subir la opción ${numero}`}>
            <ArrowUp />
          </Button>
          <Button type="button" variant="ghost" size="icon" disabled={deshabilitado || indice === total - 1} onClick={() => onMover(1)} aria-label={`Bajar la opción ${numero}`}>
            <ArrowDown />
          </Button>
          <Button type="button" variant="ghost" size="icon" disabled={deshabilitado} onClick={onQuitar} aria-label={`Quitar la opción ${numero}`}>
            <Trash2 />
          </Button>
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <div className="grid gap-1.5 sm:col-span-2">
          <Label htmlFor={`${id}-nombre`}>Nombre</Label>
          <Input
            id={`${id}-nombre`}
            value={b.nombre}
            maxLength={200}
            disabled={deshabilitado}
            placeholder={retiro ? "Retiro en mi local" : "Envío dentro de Cuenca"}
            onChange={(e) => onCambio({ nombre: e.target.value })}
          />
        </div>

        <div className="grid gap-1.5">
          <Label htmlFor={`${id}-tipo`}>Tipo</Label>
          <Select value={b.tipo} onValueChange={(v) => onCambio({ tipo: v as "envio" | "retiro" })} disabled={deshabilitado}>
            <SelectTrigger id={`${id}-tipo`} className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="envio">Envío a domicilio</SelectItem>
              <SelectItem value="retiro">El cliente retira</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="grid gap-1.5">
          <Label htmlFor={`${id}-costo`}>Lo que paga el cliente ($)</Label>
          <Input
            id={`${id}-costo`}
            inputMode="decimal"
            value={b.costoCliente}
            disabled={deshabilitado}
            placeholder="0.00"
            onChange={(e) => onCambio({ costoCliente: e.target.value })}
            className="tabular"
          />
        </div>

        {retiro ? (
          <div className="grid gap-1.5 sm:col-span-2">
            <Label htmlFor={`${id}-direccion`}>Dirección donde se retira</Label>
            <Input
              id={`${id}-direccion`}
              value={b.direccionRetiro}
              maxLength={300}
              disabled={deshabilitado}
              placeholder="Calle Larga 1-23 y Hermano Miguel, Cuenca"
              onChange={(e) => onCambio({ direccionRetiro: e.target.value })}
            />
          </div>
        ) : (
          <>
            <div className="grid gap-1.5">
              <Label htmlFor={`${id}-alcance`}>A quién se le ofrece</Label>
              <Select value={b.alcance} onValueChange={(v) => onCambio({ alcance: v as Alcance })} disabled={deshabilitado}>
                <SelectTrigger id={`${id}-alcance`} className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ALCANCES.map((a) => (
                    <SelectItem key={a.valor} value={a.valor}>
                      {a.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {b.alcance !== "resto" && (
              <div className="grid gap-1.5">
                <Label htmlFor={`${id}-lugares`}>{b.alcance === "cantones" ? "Cantones" : "Provincias"}</Label>
                <Input
                  id={`${id}-lugares`}
                  value={b.lugares}
                  disabled={deshabilitado}
                  placeholder={b.alcance === "cantones" ? "Cuenca, Azogues" : "Azuay, Cañar"}
                  onChange={(e) => onCambio({ lugares: e.target.value })}
                  aria-describedby={`${id}-lugares-ayuda`}
                />
                <p id={`${id}-lugares-ayuda`} className="text-xs text-muted-foreground">
                  Separados por coma.
                </p>
              </div>
            )}
          </>
        )}

        <div className="grid gap-1.5">
          <Label htmlFor={`${id}-negocio`}>
            Lo que te cuesta a ti ($) <span className="font-normal text-muted-foreground">(opcional)</span>
          </Label>
          <Input
            id={`${id}-negocio`}
            inputMode="decimal"
            value={b.costoNegocio}
            disabled={deshabilitado}
            placeholder="Para calcular tu ganancia real"
            onChange={(e) => onCambio({ costoNegocio: e.target.value })}
            className="tabular"
          />
        </div>

        <div className="grid gap-1.5">
          <Label htmlFor={`${id}-tiempo`}>
            Tiempo de entrega <span className="font-normal text-muted-foreground">(opcional)</span>
          </Label>
          <Input
            id={`${id}-tiempo`}
            value={b.tiempoEntrega}
            maxLength={200}
            disabled={deshabilitado}
            placeholder="Mismo día"
            onChange={(e) => onCambio({ tiempoEntrega: e.target.value })}
          />
        </div>
      </div>

      <div className="flex items-center gap-3">
        <Switch id={`${id}-activo`} checked={b.activo} disabled={deshabilitado} onCheckedChange={(c) => onCambio({ activo: c })} />
        <Label htmlFor={`${id}-activo`} className="text-sm font-normal">
          {b.activo ? "Activa: Victoria la ofrece" : "Pausada: Victoria no la ofrece"}
        </Label>
      </div>

      {error && (
        <p role="alert" className="text-xs font-medium text-status-danger-ink">
          {error}
        </p>
      )}
    </li>
  );
}

/** El envío de UN producto: o va incluido en el precio, o se cobra aparte con las opciones que definas
 * (envío a domicilio con su costo y a quién aplica, o retiro). Lo controlas producto por producto. */
export function EditorEntregas({
  envioIncluido,
  onEnvioIncluido,
  entregas,
  onEntregas,
  errores,
  costoFlete,
  onCostoFlete,
  errorFlete,
  deshabilitado = false,
}: {
  envioIncluido: boolean;
  onEnvioIncluido: (incluido: boolean) => void;
  entregas: EntregaBorrador[];
  onEntregas: (entregas: EntregaBorrador[]) => void;
  errores: string[];
  costoFlete: string;
  onCostoFlete: (valor: string) => void;
  errorFlete?: string;
  deshabilitado?: boolean;
}) {
  const id = useId();

  function mover(indice: number, direccion: -1 | 1) {
    const copia = [...entregas];
    const destino = indice + direccion;
    [copia[indice], copia[destino]] = [copia[destino], copia[indice]];
    onEntregas(copia);
  }

  return (
    <div className="space-y-4">
      <div className="flex items-start gap-3 rounded-lg border bg-card p-3">
        <Switch id={`${id}-incluido`} checked={envioIncluido} disabled={deshabilitado} onCheckedChange={onEnvioIncluido} className="mt-0.5" aria-describedby={`${id}-incluido-ayuda`} />
        <div className="min-w-0 flex-1">
          <Label htmlFor={`${id}-incluido`} className="text-sm font-medium">
            El envío ya está incluido en el precio
          </Label>
          <p id={`${id}-incluido-ayuda`} className="text-xs text-muted-foreground">
            {envioIncluido ? "El cliente paga solo el precio del producto." : "El cliente paga el precio más el envío que elija."}
          </p>
        </div>
        <InfoButton titulo="Envío incluido o cobrado aparte">
          <p>
            <strong>Incluido en el precio:</strong> el cliente paga solo el precio del producto y el envío sale de tu ganancia. Es lo normal en Rocketfy.
          </p>
          <p>
            <strong>Cobrado aparte:</strong> el cliente paga el precio más el envío que elija. Tú defines las opciones (envío a domicilio o retiro, con su costo y a quién se le ofrece) y Victoria le ofrece solo las que le aplican según su cantón y provincia.
          </p>
          <p>Cada producto tiene su propio envío: lo que configures aquí no cambia los demás productos.</p>
        </InfoButton>
      </div>

      {envioIncluido ? (
        <div className="grid max-w-sm gap-1.5">
          <div className="flex items-center gap-1">
            <Label htmlFor={`${id}-flete`}>
              Costo del flete ($) <span className="font-normal text-muted-foreground">(opcional)</span>
            </Label>
            <InfoButton titulo="Costo del flete de este producto">
              <p>
                Lo que te cuesta a ti enviar <strong>este</strong> producto. Un producto pesado cuesta más de enviar que uno liviano.
              </p>
              <p>
                Si lo anotas, el precio mínimo y tu margen usan este número en vez del envío estimado general de «Ajustes de precios». Si lo dejas vacío, se usa el estimado general.
              </p>
            </InfoButton>
          </div>
          <Input
            id={`${id}-flete`}
            inputMode="decimal"
            value={costoFlete}
            disabled={deshabilitado}
            placeholder="Vacío = usar el envío estimado general"
            onChange={(e) => onCostoFlete(e.target.value)}
            aria-invalid={Boolean(errorFlete)}
            className="tabular"
          />
          {errorFlete && (
            <p role="alert" className="text-xs font-medium text-status-danger-ink">
              {errorFlete}
            </p>
          )}
        </div>
      ) : (
        <div className="space-y-3">
          <div className="flex items-center gap-1">
            <h3 className="text-sm font-medium">Opciones de entrega</h3>
            <InfoButton titulo="Opciones de entrega">
              <p>Cada opción es una forma de entregar este producto: un envío a domicilio o un retiro, con lo que paga el cliente.</p>
              <ul>
                <li>
                  <strong>A quién se le ofrece:</strong> unos cantones, unas provincias o el resto del país. Se comparan con lo que diga el cliente sin importar mayúsculas ni tildes.
                </li>
                <li>
                  <strong>Lo que te cuesta a ti:</strong> es opcional y sirve para calcular tu ganancia real.
                </li>
                <li>
                  <strong>Activa o pausada:</strong> una opción pausada se conserva pero Victoria no la ofrece.
                </li>
                <li>
                  <strong>El orden:</strong> puedes subir o bajar cada opción con las flechas.
                </li>
              </ul>
              <p>
                Victoria le ofrece al cliente solo las opciones que le aplican según su cantón y provincia. Un envío «al resto del país» se ofrece solo si ninguna otra cubre su destino.
              </p>
              <InfoEjemplo>
                <p>«Envío dentro de Cuenca» $2 · «Retiro en mi local» $0 · «Envío al resto del país» $5</p>
              </InfoEjemplo>
              <InfoAviso>
                <p>Hace falta al menos una opción para poder publicar el producto. Puedes tener hasta {MAXIMO_OPCIONES}.</p>
              </InfoAviso>
            </InfoButton>
          </div>
          {entregas.length === 0 ? (
            <p className="rounded-lg bg-status-warning-soft p-3 text-sm text-status-warning-ink">
              Todavía no hay opciones de entrega. Agrega al menos una para poder publicar el producto.
            </p>
          ) : (
            <ul className="space-y-3">
              {entregas.map((b, i) => (
                <Opcion
                  key={b.clave}
                  b={b}
                  indice={i}
                  total={entregas.length}
                  error={errores[i] ?? ""}
                  deshabilitado={deshabilitado}
                  onCambio={(cambios) => onEntregas(entregas.map((x) => (x.clave === b.clave ? { ...x, ...cambios } : x)))}
                  onQuitar={() => onEntregas(entregas.filter((x) => x.clave !== b.clave))}
                  onMover={(d) => mover(i, d)}
                />
              ))}
            </ul>
          )}
          <div className="flex flex-wrap gap-2">
            <Button type="button" variant="outline" size="sm" disabled={deshabilitado || entregas.length >= MAXIMO_OPCIONES} onClick={() => onEntregas([...entregas, borradorVacio("envio")])}>
              <Plus /> Agregar envío
            </Button>
            <Button type="button" variant="outline" size="sm" disabled={deshabilitado || entregas.length >= MAXIMO_OPCIONES} onClick={() => onEntregas([...entregas, borradorVacio("retiro")])}>
              <Plus /> Agregar retiro
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
