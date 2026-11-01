import { useSyncExternalStore } from "react";

const sinSuscripcion = () => () => {};

/** `false` al generar el HTML (en el servidor o al compilar) y `true` apenas la
 * página está viva en el navegador. Sirve para lo que depende de "ahora" (hora,
 * fecha, ids por tiempo): Next prerenderiza las pantallas al compilar, así que
 * un `new Date()` en el render queda congelado con la hora del build (y en UTC).
 * Con `suppressHydrationWarning` React además se niega a corregirlo. Mostrar el
 * valor solo cuando esto es `true` evita ambas cosas. */
export function useMontado(): boolean {
  return useSyncExternalStore(
    sinSuscripcion,
    () => true,
    () => false,
  );
}
