"use client";

import { Bell, CirclePause, DollarSign, Loader2, Megaphone, RefreshCw, ShoppingBag, TrendingUp } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { EmptyState } from "@/components/app/empty-state";
import { FilterChips, type Chip } from "@/components/app/filter-chips";
import { InfoButton } from "@/components/app/info-button";
import { ListSkeleton } from "@/components/app/list-skeleton";
import { SectionCard } from "@/components/app/section-card";
import { StatCard } from "@/components/app/stat-card";
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
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useApi } from "@/hooks/use-api";
import { apiFetch, ApiError } from "@/lib/api";
import { formatMoney } from "@/lib/format";
import type { AnuncioMeta, TableroAnuncios } from "@/types/meta";

const DIAS: Chip[] = [
  { value: "1", label: "Hoy" },
  { value: "7", label: "7 días" },
  { value: "14", label: "14 días" },
  { value: "30", label: "30 días" },
];

function estadoInfo(estado: string | null): { label: string; variant: "success" | "warning" | "danger" | "neutral" } {
  if (estado === "ACTIVE") return { label: "Activo", variant: "success" };
  if (estado === "DISAPPROVED" || estado === "WITH_ISSUES") return { label: "Con problemas", variant: "danger" };
  if (estado === "PENDING_REVIEW" || estado === "IN_PROCESS") return { label: "En revisión", variant: "warning" };
  return { label: "Pausado", variant: "neutral" };
}

function vinculo(a: AnuncioMeta) {
  if (a.ofertaId !== null) return <Link href={`/ofertas/${a.ofertaId}`} className="text-primary underline-offset-2 hover:underline">{a.ofertaNombre}</Link>;
  if (a.productoSku) return <Link href={`/catalogo/producto/${encodeURIComponent(a.productoSku)}`} className="text-primary underline-offset-2 hover:underline">{a.productoNombre}</Link>;
  return <span className="text-status-warning-ink">Sin vincular</span>;
}

/** Gasto y resultado de cada anuncio según Meta + lo que pasó en tu negocio (ADR-017). Solo si «Leer mis anuncios de Meta» está encendido. */
export function RendimientoMeta() {
  const [dias, setDias] = useState("7");
  const tablero = useApi<TableroAnuncios>(`/meta/anuncios?dias=${dias}`);
  const [leyendo, setLeyendo] = useState(false);
  const t = tablero.data;

  async function leerAhora() {
    setLeyendo(true);
    try {
      await apiFetch("/meta/anuncios/leer", { method: "POST" });
      toast.success("Anuncios leídos de Meta.");
      tablero.recargar();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo conectar con el servidor.");
    } finally {
      setLeyendo(false);
    }
  }

  const info = (
    <InfoButton titulo="Gasto y rendimiento">
      <p>El sistema lee cada hora tus anuncios de Meta y cuánto gastó cada uno, y lo cruza con tus ventas:</p>
      <ul>
        <li><strong>Costo por venta:</strong> gasto ÷ ventas del anuncio.</li>
        <li><strong>Ganancia neta:</strong> lo que dejaron las ventas (precio − costo − envío) menos el gasto en el anuncio.</li>
        <li><strong>Retorno:</strong> cuántos dólares vendiste por cada dólar de anuncio.</li>
        <li><strong>Entregadas / devueltas:</strong> según Rocketfy.</li>
      </ul>
      <p>Las alertas avisan por Telegram. El sistema solo pausa un anuncio si encendiste la pausa automática, y solo por hechos (producto agotado u oferta terminada). Nunca reactiva un anuncio.</p>
      <p>Meta ajusta sus cifras durante unas horas: el gasto de hoy puede cambiar.</p>
    </InfoButton>
  );

  if (tablero.cargando) {
    return (
      <SectionCard titulo="Gasto y rendimiento" descripcion="Según Meta y tus ventas." info={info}>
        <ListSkeleton filas={3} />
      </SectionCard>
    );
  }
  if (tablero.error || !t) {
    return (
      <SectionCard titulo="Gasto y rendimiento" descripcion="Según Meta y tus ventas." info={info}>
        <EmptyState
          icon={Megaphone}
          tone="danger"
          title="No se pudo cargar el gasto de tus anuncios"
          description={tablero.error ?? undefined}
          action={
            <Button variant="outline" onClick={tablero.recargar}>
              Reintentar
            </Button>
          }
        />
      </SectionCard>
    );
  }
  if (!t.lecturaActiva && t.anuncios.length === 0) {
    return (
      <SectionCard titulo="Gasto y rendimiento" descripcion="Según Meta y tus ventas." info={info}>
        <EmptyState
          icon={DollarSign}
          title="Todavía no se lee el gasto de tus anuncios"
          description="Enciende «Leer mis anuncios de Meta» en Parámetros y guarda tu cuenta publicitaria en Conexión con Meta."
          action={
            <Button asChild variant="outline">
              <Link href="/parametros/meta">Conexión con Meta</Link>
            </Button>
          }
        />
      </SectionCard>
    );
  }

  return (
    <SectionCard
      titulo="Gasto y rendimiento"
      descripcion={t.ultimaLectura ? `Leído de Meta ${new Date(t.ultimaLectura).toLocaleString("es-EC", { dateStyle: "short", timeStyle: "short" })}.` : "Según Meta y tus ventas."}
      info={info}
    >
      <div className="space-y-4 p-4 sm:p-5">
        <FilterChips
          chips={DIAS}
          value={dias}
          onChange={setDias}
          label="Periodo del gasto"
          trailing={
            t.lecturaActiva ? (
              <Button type="button" variant="outline" size="sm" disabled={leyendo} onClick={() => void leerAhora()}>
                {leyendo ? <Loader2 className="animate-spin" /> : <RefreshCw />} Leer ahora
              </Button>
            ) : null
          }
        />
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <StatCard label="Gasto" value={formatMoney(t.totales.gasto)} icon={DollarSign} tono="info" />
          <StatCard label="Ventas por anuncios" value={t.totales.ventas} hint={formatMoney(t.totales.ingreso)} icon={ShoppingBag} tono="primary" />
          <StatCard label="Costo por venta" value={t.totales.costoPorVenta ? formatMoney(t.totales.costoPorVenta) : "—"} icon={TrendingUp} tono="neutral" />
          <StatCard
            label="Ganancia neta"
            value={t.totales.gananciaNeta ? formatMoney(t.totales.gananciaNeta) : "—"}
            hint={t.totales.gananciaNeta ? "Ventas menos costos y anuncios" : "Falta el costo de alguna venta"}
            icon={TrendingUp}
            tono={t.totales.gananciaNeta && t.totales.gananciaNeta.startsWith("-") ? "danger" : "success"}
          />
        </div>

        {t.anuncios.length === 0 ? (
          <p className="text-sm text-muted-foreground">No hay anuncios en tu cuenta publicitaria todavía.</p>
        ) : (
          <>
            <ul className="divide-y rounded-lg ring-1 ring-border md:hidden">
              {t.anuncios.map((a) => (
                <li key={a.idAnuncio} className="space-y-2 p-3">
                  <div className="flex items-start justify-between gap-2">
                    <p className="min-w-0 text-sm font-medium break-words">{a.nombre ?? a.idAnuncio}</p>
                    <StatusBadge {...estadoInfo(a.estadoEfectivo)} />
                  </div>
                  <p className="text-xs text-muted-foreground">Vende: {vinculo(a)}</p>
                  <dl className="grid grid-cols-3 gap-2 text-xs">
                    <div>
                      <dt className="text-muted-foreground">Gasto</dt>
                      <dd className="tabular font-medium">{formatMoney(a.gasto)}</dd>
                    </div>
                    <div>
                      <dt className="text-muted-foreground">Ventas</dt>
                      <dd className="tabular font-medium">{a.ventas}</dd>
                    </div>
                    <div>
                      <dt className="text-muted-foreground">Neta</dt>
                      <dd className="tabular font-medium">{a.gananciaNeta ? formatMoney(a.gananciaNeta) : "—"}</dd>
                    </div>
                  </dl>
                  {a.estadoEfectivo === "ACTIVE" && <BotonPausar anuncio={a} onPausado={tablero.recargar} />}
                </li>
              ))}
            </ul>
            <div className="hidden overflow-x-auto rounded-lg ring-1 ring-border md:block">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Anuncio</TableHead>
                    <TableHead>Vende</TableHead>
                    <TableHead className="text-right">Gasto</TableHead>
                    <TableHead className="text-right">Conv.</TableHead>
                    <TableHead className="text-right">Ventas</TableHead>
                    <TableHead className="text-right">Costo/venta</TableHead>
                    <TableHead className="text-right">Ganancia neta</TableHead>
                    <TableHead className="text-right">Retorno</TableHead>
                    <TableHead>
                      <span className="sr-only">Acciones</span>
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {t.anuncios.map((a) => (
                    <TableRow key={a.idAnuncio}>
                      <TableCell className="max-w-56">
                        <p className="truncate font-medium">{a.nombre ?? a.idAnuncio}</p>
                        <StatusBadge {...estadoInfo(a.estadoEfectivo)} className="mt-1" />
                      </TableCell>
                      <TableCell className="max-w-44 truncate">{vinculo(a)}</TableCell>
                      <TableCell className="tabular text-right">{formatMoney(a.gasto)}</TableCell>
                      <TableCell className="tabular text-right">{a.conversacionesMeta}</TableCell>
                      <TableCell className="tabular text-right">
                        {a.ventas}
                        {a.devueltas > 0 && <span className="block text-xs text-muted-foreground">{a.devueltas} devuelta{a.devueltas === 1 ? "" : "s"}</span>}
                      </TableCell>
                      <TableCell className="tabular text-right">{a.costoPorVenta ? formatMoney(a.costoPorVenta) : "—"}</TableCell>
                      <TableCell className="tabular text-right">{a.gananciaNeta ? formatMoney(a.gananciaNeta) : "—"}</TableCell>
                      <TableCell className="tabular text-right">{a.roas ? `${a.roas}×` : "—"}</TableCell>
                      <TableCell>{a.estadoEfectivo === "ACTIVE" && <BotonPausar anuncio={a} onPausado={tablero.recargar} />}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </>
        )}

        {t.alertas.length > 0 && (
          <div className="space-y-2 border-t pt-4">
            <h3 className="flex items-center gap-2 text-sm font-medium">
              <Bell className="size-4" aria-hidden /> Alertas recientes
            </h3>
            <ul className="space-y-1.5 text-sm">
              {t.alertas.slice(0, 8).map((al) => (
                <li key={al.id} className="rounded-lg bg-status-warning-soft px-3 py-2 text-status-warning-ink">
                  {al.mensaje}
                </li>
              ))}
            </ul>
          </div>
        )}
        {t.acciones.length > 0 && (
          <div className="space-y-2 border-t pt-4">
            <h3 className="flex items-center gap-2 text-sm font-medium">
              <CirclePause className="size-4" aria-hidden /> Pausas hechas por el sistema o por ti
            </h3>
            <ul className="space-y-1 text-sm text-muted-foreground">
              {t.acciones.slice(0, 8).map((ac) => (
                <li key={ac.id}>
                  {new Date(ac.creadaEn).toLocaleString("es-EC", { dateStyle: "short", timeStyle: "short" })} · anuncio {ac.idAnuncio} ·{" "}
                  {ac.resultado === "hecho" ? "pausado" : ac.resultado === "dudoso" ? "no se sabe si se pausó: revísalo en Meta" : "Meta no lo pausó"} ({ac.motivo})
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </SectionCard>
  );
}

function BotonPausar({ anuncio, onPausado }: { anuncio: AnuncioMeta; onPausado: () => void }) {
  const [pausando, setPausando] = useState(false);

  async function pausar() {
    setPausando(true);
    try {
      const r = await apiFetch<{ mensaje: string }>(`/meta/anuncios/${encodeURIComponent(anuncio.idAnuncio)}/pausar`, { method: "POST" });
      toast.success(r.mensaje);
      onPausado();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo conectar con el servidor.");
    } finally {
      setPausando(false);
    }
  }

  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>
        <Button type="button" variant="outline" size="sm" disabled={pausando}>
          {pausando ? <Loader2 className="animate-spin" /> : <CirclePause />} Pausar
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>¿Pausar este anuncio en Meta?</AlertDialogTitle>
          <AlertDialogDescription>
            «{anuncio.nombre ?? anuncio.idAnuncio}» dejará de gastar. Para reactivarlo, hazlo tú en el Administrador de anuncios de Meta.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancelar</AlertDialogCancel>
          <AlertDialogAction onClick={() => void pausar()}>Sí, pausar</AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
