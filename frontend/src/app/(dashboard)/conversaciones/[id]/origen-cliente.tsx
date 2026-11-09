"use client";

import { ExternalLink, Megaphone } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { InfoAviso, InfoButton } from "@/components/app/info-button";
import { StatusBadge } from "@/components/status-badge";
import { formatFechaHora } from "@/lib/format";
import type { ConversacionDetalle } from "@/types/conversacion";

function Dato({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-0.5">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="text-sm">{children}</dd>
    </div>
  );
}

/** De dónde viene este cliente: directo o por un anuncio (con lo que Meta mandó de él, su producto vinculado y la ventana
 * gratuita). Va en el panel de datos de la conversación. */
export function OrigenCliente({ conversacion }: { conversacion: ConversacionDetalle }) {
  const { anuncio, ventanaGratuita: gratuita, llegadasPorAnuncio: llegadas } = conversacion;
  const [imagenFalla, setImagenFalla] = useState(false);
  const imagen = anuncio?.miniaturaUrl ?? anuncio?.imagenUrl ?? null;

  return (
    <section aria-labelledby="t-origen" className="space-y-3 border-t pt-5">
      <div className="flex items-center gap-1">
        <h2 id="t-origen" className="flex items-center gap-2 text-sm font-semibold">
          <Megaphone className="size-4 text-muted-foreground" aria-hidden /> Origen
        </h2>
        <InfoButton titulo="De dónde viene este cliente">
          <p>
            Cuando alguien escribe <strong>tocando un anuncio</strong> (Click-to-WhatsApp), Meta manda los datos del anuncio y aquí se guardan todos: título, texto, enlace, imagen y el ID.
          </p>
          <ul>
            <li>
              <strong>Si el cliente vuelve por otro anuncio,</strong> el anuncio vigente pasa a ser el último y los anteriores quedan en el historial de llegadas.
            </li>
            <li>
              <strong>Producto vinculado:</strong> Victoria lo usa para saber de qué hablar sin preguntar. Si el anuncio no está vinculado, ella pregunta qué producto quiere el cliente. Se vincula en <Link href="/anuncios">Anuncios</Link>.
            </li>
            <li>
              <strong>Ventana gratuita:</strong> si le respondes dentro de las 24 horas, Meta no cobra los mensajes (plantillas incluidas) durante hasta 7 días desde tu respuesta.
            </li>
          </ul>
          <InfoAviso>
            <p>
              La ventana gratuita es un beneficio de <strong>costo</strong>: solo puedes escribir texto libre dentro de las 24 horas desde el último mensaje del cliente (la barra de arriba del chat). «Hasta 7 días» es el máximo que indica Meta.
            </p>
          </InfoAviso>
        </InfoButton>
      </div>

      {!anuncio ? (
        <p className="flex items-center gap-2 text-sm">
          <StatusBadge label="Directo" variant="neutral" />
          <span className="text-muted-foreground">Escribió sin tocar un anuncio.</span>
        </p>
      ) : (
        <>
          <p className="flex flex-wrap items-center gap-2 text-sm">
            <StatusBadge label="Por anuncio" variant="info" />
            {anuncio.llegadas > 1 && <span className="text-muted-foreground">Llegó {anuncio.llegadas} veces por anuncio</span>}
          </p>

          <div className="flex items-start gap-3">
            {imagen && !imagenFalla && (
              // eslint-disable-next-line @next/next/no-img-element -- la imagen viene de la CDN de Meta
              <img src={imagen} alt="" width={56} height={56} referrerPolicy="no-referrer" onError={() => setImagenFalla(true)} className="size-14 shrink-0 rounded-lg border bg-muted object-cover" />
            )}
            <div className="min-w-0 space-y-1">
              <p className="text-sm font-medium break-words">{anuncio.titulo ?? "Anuncio sin título"}</p>
              {anuncio.texto && <p className="line-clamp-3 text-xs text-muted-foreground break-words">{anuncio.texto}</p>}
            </div>
          </div>

          <dl className="space-y-3">
            <Dato label="Producto del anuncio">
              {anuncio.producto ? (
                <Link href={`/catalogo/producto/${encodeURIComponent(anuncio.producto.sku)}`} className="text-primary underline-offset-2 hover:underline">
                  {anuncio.producto.nombre}
                </Link>
              ) : (
                <span className="text-muted-foreground">
                  Sin vincular.{" "}
                  <Link href="/anuncios" className="text-primary underline-offset-2 hover:underline">
                    Vincular en Anuncios
                  </Link>
                </span>
              )}
            </Dato>
            {anuncio.idAnuncio && (
              <Dato label="ID del anuncio">
                <span className="tabular break-all">{anuncio.idAnuncio}</span>
              </Dato>
            )}
            {gratuita && gratuita.estado !== "sin_anuncio" && (
              <Dato label="Ventana gratuita de Meta">
                {gratuita.estado === "abierta" && (
                  <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
                    <StatusBadge label="Abierta" variant="success" />
                    <span className="text-muted-foreground">hasta {formatFechaHora(gratuita.expiraEn)}</span>
                  </span>
                )}
                {gratuita.estado === "pendiente" && (
                  <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
                    <StatusBadge label="Por abrir" variant="warning" />
                    <span className="text-muted-foreground">se abre si respondes antes de {formatFechaHora(gratuita.responderAntesDe)}</span>
                  </span>
                )}
                {gratuita.estado === "cerrada" && <StatusBadge label="Cerrada" variant="neutral" />}
              </Dato>
            )}
          </dl>

          {anuncio.urlAnuncio && (
            <a
              href={anuncio.urlAnuncio}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex min-h-10 items-center gap-1.5 rounded-md text-sm text-primary underline-offset-2 outline-none hover:underline focus-visible:ring-2 focus-visible:ring-ring"
            >
              Ver el anuncio <ExternalLink className="size-3.5" aria-hidden />
              <span className="sr-only">(se abre en otra pestaña)</span>
            </a>
          )}

          {llegadas && llegadas.length > 1 && (
            <details className="text-sm">
              <summary className="min-h-10 cursor-pointer py-2 font-medium">Historial de llegadas ({llegadas.length})</summary>
              <ol className="space-y-2 border-l pl-3">
                {llegadas.map((l, i) => (
                  <li key={`${l.creadoEn}-${i}`} className="space-y-0.5">
                    <p className="break-words">{l.titulo ?? `Anuncio ${l.idAnuncio ?? "sin ID"}`}</p>
                    <p className="text-xs text-muted-foreground">{formatFechaHora(l.creadoEn)}</p>
                  </li>
                ))}
              </ol>
            </details>
          )}
        </>
      )}
    </section>
  );
}
