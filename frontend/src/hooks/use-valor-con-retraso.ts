"use client";

import { useEffect, useState } from "react";

/** Devuelve `valor` pero solo después de que deje de cambiar `ms` milisegundos.
 * Sirve para no consultar al servidor en cada tecla mientras alguien escribe
 * (p. ej. el precio en la calculadora). */
export function useValorConRetraso<T>(valor: T, ms: number): T {
  const [retrasado, setRetrasado] = useState(valor);

  useEffect(() => {
    const t = setTimeout(() => setRetrasado(valor), ms);
    return () => clearTimeout(t);
  }, [valor, ms]);

  return retrasado;
}
