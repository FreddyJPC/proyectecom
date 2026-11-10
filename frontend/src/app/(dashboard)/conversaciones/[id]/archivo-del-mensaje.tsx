"use client";

import { FileText, ImageIcon, Loader2, Mic } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { apiBlob } from "@/lib/api";

const ETIQUETA = { imagen: "Ver la foto", audio: "Escuchar el audio", documento: "Abrir el PDF" } as const;
const ICONO = { imagen: ImageIcon, audio: Mic, documento: FileText } as const;

/** La foto, el audio o el PDF que mandó el cliente. El servidor lo trae de Meta solo cuando se pide (Meta lo guarda ~30 días);
 * por eso hay un botón y no se carga todo al abrir la conversación. */
export function ArchivoDelMensaje({ conversacionId, mensajeId, tipo }: { conversacionId: string; mensajeId: number; tipo: string }) {
  const clave = (tipo === "audio" || tipo === "documento" ? tipo : "imagen") as keyof typeof ETIQUETA;
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
        window.open(nueva, "_blank", "noopener");
      } else {
        setUrl(nueva);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo abrir el archivo.");
    } finally {
      setCargando(false);
    }
  }

  if (url && clave === "imagen") {
    // eslint-disable-next-line @next/next/no-img-element -- es un blob local de la sesión, next/image no aplica
    return <img src={url} alt="Foto enviada por el cliente" className="mt-2 max-h-72 w-full rounded-lg border object-contain" />;
  }
  if (url && clave === "audio") {
    return <audio controls src={url} className="mt-2 w-full" aria-label="Audio enviado por el cliente" />;
  }
  return (
    <div className="mt-2 not-italic">
      <Button type="button" variant="outline" size="sm" className="h-10 gap-2" onClick={abrir} disabled={cargando}>
        {cargando ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Icono className="size-4" aria-hidden />}
        {ETIQUETA[clave]}
      </Button>
      {error && (
        <p role="alert" className="mt-1 text-xs text-status-danger-ink">
          {error}
        </p>
      )}
    </div>
  );
}
