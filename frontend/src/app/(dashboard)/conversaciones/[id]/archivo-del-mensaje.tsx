"use client";

import { Film, FileText, ImageIcon, Loader2, Mic } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { apiBlob } from "@/lib/api";

const ETIQUETA = { imagen: "Ver la foto", audio: "Escuchar el audio", video: "Ver el video", documento: "Abrir el archivo" } as const;
const ICONO = { imagen: ImageIcon, audio: Mic, video: Film, documento: FileText } as const;
type Clave = keyof typeof ETIQUETA;

/** El archivo de un mensaje: lo que mandó el cliente (foto, audio, video, PDF) o lo que el dueño mandó desde su teléfono o
 * computadora. El servidor lo trae de Meta solo cuando se pide (Meta lo guarda ~30 días); por eso hay un botón y no se carga todo
 * al abrir la conversación. Un PDF se abre en otra pestaña; otro documento (Word, Excel…) se descarga con su nombre. */
export function ArchivoDelMensaje({
  conversacionId,
  mensajeId,
  tipo,
  deCliente = true,
  nombreArchivo,
}: {
  conversacionId: string;
  mensajeId: number;
  tipo: string;
  deCliente?: boolean;
  nombreArchivo?: string | null;
}) {
  const clave: Clave = tipo === "audio" || tipo === "documento" || tipo === "video" ? tipo : "imagen";
  const Icono = ICONO[clave];
  const [url, setUrl] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const urlRef = useRef<string | null>(null);

  useEffect(() => {
    return () => {
      if (urlRef.current) URL.revokeObjectURL(urlRef.current);
    };
  }, []);

  async function abrir() {
    setCargando(true);
    setError(null);
    try {
      const blob = await apiBlob(`/conversaciones/${conversacionId}/mensajes/${mensajeId}/archivo`);
      const nueva = URL.createObjectURL(blob);
      urlRef.current = nueva;
      if (clave === "documento") {
        if (blob.type === "application/pdf") {
          window.open(nueva, "_blank", "noopener");
        } else {
          const enlace = document.createElement("a");
          enlace.href = nueva;
          enlace.download = nombreArchivo || "archivo";
          enlace.click();
        }
      } else {
        setUrl(nueva);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo abrir el archivo.");
    } finally {
      setCargando(false);
    }
  }

  const quien = deCliente ? "por el cliente" : "al cliente";
  if (url && clave === "imagen") {
    // eslint-disable-next-line @next/next/no-img-element -- es un blob local de la sesión, next/image no aplica
    return <img src={url} alt={`Foto enviada ${quien}`} className="mt-2 max-h-72 w-full rounded-lg border object-contain" />;
  }
  if (url && clave === "audio") {
    return <audio controls src={url} className="mt-2 w-full" aria-label={`Audio enviado ${quien}`} />;
  }
  if (url && clave === "video") {
    return <video controls playsInline src={url} className="mt-2 max-h-72 w-full rounded-lg bg-black" aria-label={`Video enviado ${quien}`} />;
  }
  return (
    <div className="mt-2 not-italic">
      <Button type="button" variant="outline" size="sm" className="h-10 max-w-full gap-2" onClick={abrir} disabled={cargando}>
        {cargando ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Icono className="size-4" aria-hidden />}
        <span className="truncate">{clave === "documento" && nombreArchivo ? nombreArchivo : ETIQUETA[clave]}</span>
      </Button>
      {error && (
        <p role="alert" className="mt-1 text-xs text-status-danger-ink">
          {error}
        </p>
      )}
    </div>
  );
}
