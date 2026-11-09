"use client";

import { BellOff, ExternalLink, MessageCircle, Pencil, TriangleAlert } from "lucide-react";
import Link from "next/link";
import { useState, type ReactNode } from "react";

import { AvatarInitials } from "@/components/app/avatar-initials";
import { EmptyState } from "@/components/app/empty-state";
import { InfoButton } from "@/components/app/info-button";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { useApi } from "@/hooks/use-api";
import { lineaDeCanal, nombreCanal, nombreDeCliente } from "@/lib/canales";
import { estadoConversacionInfo } from "@/lib/estados";
import { formatFecha, formatFechaHora, formatMoney, tiempoRelativo } from "@/lib/format";
import { esFutura, etapaLead, nombreOrigen, ORIGEN_TEMPERATURA, temperaturaImpuesta, temperaturaInfo, TIPOS_CONTACTO } from "@/lib/leads";
import type { LeadDetalle } from "@/types/leads";

import { CambiarTemperaturaDialog, NoContactarDialog } from "./acciones-lead";
import { TemperaturaBadge } from "./temperatura-badge";

function Seccion({ titulo, info, children }: { titulo: string; info?: ReactNode; children: ReactNode }) {
  return (
    <section className="space-y-3 border-t px-4 py-4 first:border-t-0">
      <div className="flex items-center gap-1">
        <h3 className="text-sm font-semibold">{titulo}</h3>
        {info}
      </div>
      {children}
    </section>
  );
}

function Dato({ etiqueta, children, ancho }: { etiqueta: string; children?: ReactNode; ancho?: boolean }) {
  if (children === undefined || children === null || children === "") return null;
  return (
    <div className={`min-w-0 space-y-0.5${ancho ? " col-span-2" : ""}`}>
      <dt className="text-xs text-muted-foreground">{etiqueta}</dt>
      <dd className="break-words text-sm">{children}</dd>
    </div>
  );
}

/** El detalle de un lead en un panel lateral: qué quiere, su temperatura y por qué, cómo ha cambiado, quién es el cliente
 * (visión 360) y las acciones del dueño. */
export function LeadDetalleSheet({ leadId, onCerrar, onCambio }: { leadId: number | null; onCerrar: () => void; onCambio: () => void }) {
  const detalle = useApi<LeadDetalle>(leadId !== null ? `/leads/${leadId}` : null);
  // Mientras llega el detalle de OTRO lead no se muestra el anterior: sería engañoso.
  const datos = detalle.data && detalle.data.lead.id === leadId ? detalle.data : null;

  const [cambiando, setCambiando] = useState(false);
  const [noContactarAbierto, setNoContactarAbierto] = useState(false);
  // Qué se va a hacer, fijado al abrir el cuadro: si dependiera del contacto, el texto cambiaría mientras el cuadro se cierra.
  const [activarNoContactar, setActivarNoContactar] = useState(true);

  const lead = datos?.lead;
  const contacto = datos?.contacto;
  const nombre = lead ? nombreDeCliente({ nombre: lead.nombre, telefono: lead.telefono, idExterno: lead.idExterno }) : "Lead";
  const impuesta = lead ? temperaturaImpuesta(lead.etapa) : null;
  const fijadaVigente = esFutura(lead?.temperaturaFijadaHasta);

  function alGuardar() {
    detalle.recargar();
    onCambio();
  }

  return (
    <Sheet open={leadId !== null} onOpenChange={(abierto) => !abierto && onCerrar()}>
      <SheetContent className="w-full gap-0 p-0 data-[side=right]:w-full data-[side=right]:sm:max-w-lg">
        <SheetHeader className="shrink-0 border-b p-4 pr-12">
          <div className="flex items-center gap-3">
            <AvatarInitials nombre={lead?.nombre ?? lead?.telefono} semilla={lead?.idExterno ?? String(leadId)} className="size-11" />
            <div className="min-w-0">
              <SheetTitle className="truncate">{nombre}</SheetTitle>
              <SheetDescription className="tabular truncate">
                {lead ? lineaDeCanal({ canal: lead.canal, telefono: lead.telefono, idExterno: lead.idExterno }) : "Cargando…"}
              </SheetDescription>
            </div>
          </div>
        </SheetHeader>

        {/* tabIndex=0: si el contenido no cabe, quien navega con teclado puede enfocar la zona y desplazarla. */}
        <div tabIndex={0} className="min-h-0 flex-1 overflow-y-auto outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring/60">
          {detalle.cargando || (leadId !== null && !datos && !detalle.error) ? (
            <div className="space-y-4 p-4">
              <Skeleton className="h-24 w-full" />
              <Skeleton className="h-32 w-full" />
              <Skeleton className="h-40 w-full" />
            </div>
          ) : detalle.error && !datos ? (
            <EmptyState
              icon={TriangleAlert}
              tone="danger"
              title="No se pudo cargar el lead"
              description={detalle.error}
              action={
                <Button variant="outline" onClick={detalle.recargar}>
                  Reintentar
                </Button>
              }
            />
          ) : lead && datos ? (
            <>
              <Seccion
                titulo="Temperatura"
                info={
                  <InfoButton titulo="Cómo se decide la temperatura">
                    <p>La temperatura dice <strong>qué tan probable es que el cliente compre</strong>. Es distinta de la etapa, que dice dónde va el pedido.</p>
                    <ul>
                      <li><strong>Tú</strong> mandas sobre todo: lo que fijas a mano no lo cambian ni Victoria ni el enfriamiento automático durante unos días.</li>
                      <li><strong>Las ventas</strong> mandan sobre Victoria: una venta cerrada es «ganado» y una cancelada es «perdido».</li>
                      <li><strong>Victoria</strong> la ajusta al leer la conversación (por ejemplo, «caliente» si pide datos de envío).</li>
                      <li><strong>El tiempo</strong> solo enfría: si el cliente deja de responder pasa a tibio, frío y, al final, perdido.</li>
                    </ul>
                  </InfoButton>
                }
              >
                <div className="flex flex-wrap items-center gap-2">
                  <TemperaturaBadge temperatura={lead.temperatura} />
                  <span className="text-sm text-muted-foreground">{etapaLead(lead.etapa)}</span>
                </div>
                <p className="text-sm text-muted-foreground">{temperaturaInfo(lead.temperatura).explicacion}</p>
                <dl className="grid grid-cols-2 gap-x-4 gap-y-3">
                  <Dato etiqueta="La puso">{ORIGEN_TEMPERATURA[lead.temperaturaOrigen] ?? lead.temperaturaOrigen}</Dato>
                  <Dato etiqueta="Desde">{tiempoRelativo(lead.temperaturaEn)}</Dato>
                  {lead.motivoPerdidaEtiqueta && <Dato etiqueta="Motivo de pérdida">{lead.motivoPerdidaEtiqueta}</Dato>}
                  {fijadaVigente && <Dato etiqueta="Fijada hasta">{formatFecha(lead.temperaturaFijadaHasta)}</Dato>}
                  <Dato etiqueta="Motivo" ancho>
                    {lead.temperaturaMotivo}
                  </Dato>
                </dl>
                {impuesta ? (
                  <p className="text-xs text-muted-foreground">
                    {impuesta === "ganado" ? "Este lead tiene una venta cerrada: es «ganado»." : "La venta de este lead se canceló: es «perdido»."}
                  </p>
                ) : (
                  <Button type="button" variant="outline" size="sm" onClick={() => setCambiando(true)}>
                    <Pencil /> Cambiar temperatura
                  </Button>
                )}
              </Seccion>

              <Seccion titulo="Qué quiere">
                <dl className="grid grid-cols-2 gap-x-4 gap-y-3">
                  <Dato etiqueta="Producto" ancho>
                    {lead.productoNombre
                      ? `${lead.cantidad && lead.cantidad > 1 ? `${lead.cantidad} × ` : ""}${lead.productoNombre}${lead.productoVariante ? ` (${lead.productoVariante})` : ""}`
                      : "Aún no se sabe"}
                  </Dato>
                  <Dato etiqueta="Total">{lead.total ? formatMoney(lead.total) : null}</Dato>
                  <Dato etiqueta="Etapa">{etapaLead(lead.etapa)}</Dato>
                  <Dato etiqueta="Llegó por">{lead.origen === "anuncio" ? (lead.tituloAnuncio ? `Anuncio: ${lead.tituloAnuncio}` : "Anuncio") : nombreOrigen(lead.origen)}</Dato>
                  <Dato etiqueta="Creado">{formatFechaHora(lead.creadoEn)}</Dato>
                  <Dato etiqueta="Último mensaje suyo">{lead.ultimoClienteEn ? tiempoRelativo(lead.ultimoClienteEn) : "Nunca escribió"}</Dato>
                  {lead.cerradoEn && <Dato etiqueta="Cerrado">{formatFechaHora(lead.cerradoEn)}</Dato>}
                </dl>
                {lead.ultimoMensaje && (
                  <p className="line-clamp-3 rounded-lg bg-muted/60 p-3 text-sm text-foreground/80">
                    <span className="text-muted-foreground">{lead.ultimoMensaje.rol === "cliente" ? "Cliente: " : lead.ultimoMensaje.rol === "bot" ? "Victoria: " : "Tú: "}</span>
                    {lead.ultimoMensaje.contenido}
                  </p>
                )}
                <Button asChild variant="outline" size="sm">
                  <Link href={`/conversaciones/${lead.conversacionId}`}>
                    <MessageCircle /> Abrir la conversación
                  </Link>
                </Button>
              </Seccion>

              <Seccion titulo="Cómo ha cambiado">
                {datos.historial.length === 0 ? (
                  <p className="text-sm text-muted-foreground">Todavía no hay cambios registrados.</p>
                ) : (
                  <ol className="relative ml-1 space-y-4 border-l pl-4">
                    {datos.historial.map((h) => (
                      <li key={h.id} className="relative space-y-1">
                        <span className="absolute top-1.5 -left-5 size-2 rounded-full bg-primary" aria-hidden />
                        <div className="flex flex-wrap items-center gap-1.5 text-sm">
                          {h.de ? (
                            <>
                              <TemperaturaBadge temperatura={h.de} className="h-5 px-2 text-[0.7rem]" />
                              <span aria-label="pasó a" className="text-muted-foreground">→</span>
                            </>
                          ) : (
                            <span className="text-muted-foreground">Nació como</span>
                          )}
                          <TemperaturaBadge temperatura={h.a} className="h-5 px-2 text-[0.7rem]" />
                        </div>
                        {h.motivo && <p className="text-sm">{h.motivo}</p>}
                        <p className="text-xs text-muted-foreground">
                          {ORIGEN_TEMPERATURA[h.origen] ?? h.origen} · {formatFechaHora(h.creadoEn)}
                        </p>
                      </li>
                    ))}
                  </ol>
                )}
              </Seccion>

              {contacto && (
                <Seccion
                  titulo="El cliente"
                  info={
                    <InfoButton titulo="La ficha del cliente">
                      <p>
                        Todo lo que sabemos de la <strong>persona</strong>, no solo de este lead: por qué canales escribe, cuánto ha comprado, cómo llegó la primera vez y sus otros leads.
                      </p>
                      <ul>
                        <li><strong>Prospecto:</strong> aún no ha comprado.</li>
                        <li><strong>Cliente:</strong> una compra.</li>
                        <li><strong>Recurrente:</strong> dos compras o más.</li>
                      </ul>
                    </InfoButton>
                  }
                >
                  <div className="flex flex-wrap items-center gap-2">
                    {contacto.tipo && <StatusBadge label={TIPOS_CONTACTO[contacto.tipo].label} variant={TIPOS_CONTACTO[contacto.tipo].variant} />}
                    {contacto.noContactar && <StatusBadge label="No contactar" variant="danger" />}
                  </div>
                  <dl className="grid grid-cols-2 gap-x-4 gap-y-3">
                    <Dato etiqueta="Compras">{contacto.compras.cantidad}</Dato>
                    <Dato etiqueta="Ha gastado">{formatMoney(contacto.compras.totalGastado)}</Dato>
                    <Dato etiqueta="Ganancia">{contacto.compras.cantidad > 0 && contacto.compras.comprasSinCosto === 0 ? formatMoney(contacto.compras.ganancia) : null}</Dato>
                    <Dato etiqueta="Última compra">{contacto.compras.ultimaCompra ? formatFecha(contacto.compras.ultimaCompra) : null}</Dato>
                    <Dato etiqueta="Cliente desde">{formatFecha(contacto.creadoEn)}</Dato>
                    <Dato etiqueta="Llegadas por anuncio">{contacto.anuncios.llegadas > 0 ? contacto.anuncios.llegadas : null}</Dato>
                    <Dato etiqueta="Primer anuncio" ancho>
                      {contacto.anuncios.primerAnuncio ? (contacto.anuncios.primerAnuncio.titulo ?? contacto.anuncios.primerAnuncio.id_anuncio) : null}
                    </Dato>
                  </dl>

                  {contacto.conversaciones.length > 0 && (
                    <div className="space-y-1.5">
                      <p className="text-xs text-muted-foreground">Conversaciones</p>
                      <ul className="space-y-1">
                        {contacto.conversaciones.map((c) => (
                          <li key={c.id}>
                            <Link
                              href={`/conversaciones/${c.id}`}
                              className="flex min-h-10 items-center justify-between gap-2 rounded-md px-2 text-sm outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring"
                            >
                              <span className="min-w-0 truncate">{nombreCanal(c.canal)}</span>
                              <span className="flex shrink-0 items-center gap-2 text-xs text-muted-foreground">
                                {estadoConversacionInfo(c.estado).label}
                                <ExternalLink className="size-3.5" aria-hidden />
                              </span>
                            </Link>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {contacto.leads.length > 1 && (
                    <div className="space-y-1.5">
                      <p className="text-xs text-muted-foreground">Todos sus leads</p>
                      <ul className="divide-y rounded-lg border">
                        {contacto.leads.map((l) => (
                          <li key={l.id} className="flex items-center justify-between gap-2 px-3 py-2 text-sm">
                            <span className="min-w-0 truncate">
                              {l.productoNombre ?? "Sin producto"}
                              {l.id === lead.id && <span className="text-muted-foreground"> · este</span>}
                            </span>
                            <TemperaturaBadge temperatura={l.temperatura} className="h-5 shrink-0 px-2 text-[0.7rem]" />
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </Seccion>
              )}

              {contacto && (
                <Seccion
                  titulo="Protección"
                  info={
                    <InfoButton titulo="No contactar">
                      <p>
                        Marca a la <strong>persona</strong>, no a un lead ni a un canal. Si está activo, el sistema no le escribe por iniciativa propia (seguimientos, recordatorios) en ningún canal, y sus leads abiertos pasan a «perdido».
                      </p>
                      <p>Si él escribe primero, Victoria lo sigue atendiendo con normalidad.</p>
                      <p>Victoria lo marca sola cuando el cliente pide que no le escriban; también puedes marcarlo tú.</p>
                    </InfoButton>
                  }
                >
                  <div className="flex items-center justify-between gap-3">
                    <Label htmlFor="no-contactar" className="flex min-w-0 items-center gap-2 text-sm">
                      <BellOff className="size-4 shrink-0 text-muted-foreground" aria-hidden />
                      No contactar a este cliente
                    </Label>
                    <Switch id="no-contactar" checked={contacto.noContactar} onCheckedChange={(valor) => {
                        setActivarNoContactar(valor);
                        setNoContactarAbierto(true);
                      }} />
                  </div>
                  {contacto.noContactar && (
                    <p className="text-sm text-muted-foreground">
                      {contacto.noContactarMotivo ?? "Sin motivo anotado"}
                      {contacto.noContactarPor ? ` · lo marcó ${contacto.noContactarPor === "ia" ? "Victoria" : "el dueño"}` : ""}
                      {contacto.noContactarEn ? `, ${formatFecha(contacto.noContactarEn)}` : ""}
                    </p>
                  )}
                </Seccion>
              )}
            </>
          ) : null}
        </div>

        {lead && (
          <CambiarTemperaturaDialog lead={lead} abierto={cambiando} onAbiertoChange={setCambiando} onGuardado={alGuardar} />
        )}
        {contacto && (
          <NoContactarDialog
            contactoId={contacto.id}
            nombre={nombre}
            activar={activarNoContactar}
            abierto={noContactarAbierto}
            onAbiertoChange={setNoContactarAbierto}
            onGuardado={alGuardar}
          />
        )}
      </SheetContent>
    </Sheet>
  );
}
