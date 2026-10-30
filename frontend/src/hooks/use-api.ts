"use client";

import { useEffect, useState } from "react";

import { ApiError, apiFetch } from "@/lib/api";

type Resultado<T> = { clave: string; data: T | null; error: string | null };

/** Consulta GET al backend con estados de carga y error, y reintento.
 *
 * - Mientras llega una respuesta nueva (p. ej. al cambiar de página o de
 *   filtro) se conserva el dato anterior: la pantalla no parpadea ni salta.
 * - Pasar `null` como ruta pausa la consulta.
 * - `recargar()` vuelve a pedir lo mismo (botón "Reintentar").
 * - `intervalo` (ms) refresca solo cada cierto tiempo, también sin parpadeo.
 *
 * El "cargando" se deriva (¿ya llegó la respuesta de ESTA consulta?) en vez
 * de guardarse en un estado: así no hay setState síncrono dentro del efecto. */
export function useApi<T>(path: string | null, opciones?: { intervalo?: number }) {
  const [version, setVersion] = useState(0);
  const [resultado, setResultado] = useState<Resultado<T> | null>(null);
  const clave = `${path}#${version}`;

  useEffect(() => {
    if (path === null) return;
    let cancelado = false;

    apiFetch<T>(path)
      .then((data) => {
        if (!cancelado) setResultado({ clave, data, error: null });
      })
      .catch((err: unknown) => {
        if (cancelado) return;
        setResultado({
          clave,
          data: null,
          error: err instanceof ApiError ? err.message : "No se pudo conectar con el servidor.",
        });
      });

    return () => {
      cancelado = true;
    };
  }, [path, clave]);

  const intervalo = opciones?.intervalo;
  useEffect(() => {
    if (path === null || !intervalo) return;
    const id = setInterval(() => setVersion((v) => v + 1), intervalo);
    return () => clearInterval(id);
  }, [path, intervalo]);

  const actual = resultado?.clave === clave;
  return {
    data: resultado?.data ?? null,
    error: actual ? resultado.error : null,
    /** Aún no hay nada que mostrar (primera carga). */
    cargando: path !== null && !actual && resultado?.data == null,
    /** Hay una consulta en curso, aunque ya se vean datos anteriores. */
    actualizando: path !== null && !actual,
    recargar: () => setVersion((v) => v + 1),
  };
}
