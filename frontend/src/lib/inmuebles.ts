/** Ayudantes del módulo «Inmuebles». Las fechas de la agenda se muestran SIEMPRE en hora de Ecuador (America/Guayaquil),
 * no en la del navegador: la visita es en Ecuador aunque el panel se abra desde otro lado. */

const ZONA = "America/Guayaquil";

/** "sábado 28 nov" */
export function fechaEcuador(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Intl.DateTimeFormat("es-EC", { timeZone: ZONA, weekday: "long", day: "numeric", month: "short" })
    .format(new Date(iso))
    .replace(".", "")
    .replace(",", "");
}

/** "10:00" */
export function horaEcuador(iso: string | null | undefined): string {
  if (!iso) return "";
  return new Intl.DateTimeFormat("es-EC", { timeZone: ZONA, hour: "2-digit", minute: "2-digit", hour12: false }).format(new Date(iso));
}

/** "2026-11-28": el día de Ecuador de un instante (para agrupar la agenda por día). */
export function diaEcuador(iso: string | Date): string {
  const partes = new Intl.DateTimeFormat("en-CA", { timeZone: ZONA, year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(
    typeof iso === "string" ? new Date(iso) : iso,
  );
  const v = (t: string) => partes.find((p) => p.type === t)?.value ?? "";
  return `${v("year")}-${v("month")}-${v("day")}`;
}

/** Hoy en Ecuador, como "AAAA-MM-DD". */
export function hoyEcuador(): string {
  return diaEcuador(new Date());
}

/** "AAAA-MM-DD" + n días. */
export function sumarDias(dia: string, dias: number): string {
  const [a, m, d] = dia.split("-").map(Number);
  const fecha = new Date(Date.UTC(a, m - 1, d + dias));
  return fecha.toISOString().slice(0, 10);
}

/** Título de un día de la agenda: «Hoy», «Mañana» o «lunes 1 dic». */
export function tituloDia(dia: string): string {
  const hoy = hoyEcuador();
  if (dia === hoy) return "Hoy";
  if (dia === sumarDias(hoy, 1)) return "Mañana";
  if (dia === sumarDias(hoy, -1)) return "Ayer";
  return fechaEcuador(`${dia}T12:00:00-05:00`);
}

/** Lo que escribe el dueño en el formulario (día y hora de Ecuador) -> instante con zona, que es lo que pide la API. */
export function instanteEcuador(dia: string, hora: string): string {
  return `${dia}T${hora}:00-05:00`;
}

/** Para precargar el formulario: el día y la hora de Ecuador de un instante. */
export function partesEcuador(iso: string | null | undefined): { dia: string; hora: string } {
  if (!iso) return { dia: "", hora: "" };
  return { dia: diaEcuador(iso), hora: horaEcuador(iso) };
}

/** Saca las coordenadas de un enlace de Google Maps o de un texto «-2.17, -79.92». Los enlaces cortos (maps.app.goo.gl) no
 * traen las coordenadas: en ese caso hay que abrirlos y copiar el enlace largo (o las coordenadas). */
export function coordenadasDe(texto: string): { latitud: string; longitud: string } | null {
  const limpio = texto.trim();
  const patrones = [
    /@(-?\d{1,2}\.\d+),(-?\d{1,3}\.\d+)/, // .../@-2.17,-79.92,17z
    /[?&](?:q|query|ll|destination)=(-?\d{1,2}\.\d+)(?:,|%2C)\s*(-?\d{1,3}\.\d+)/i, // ?q=-2.17,-79.92
    /!3d(-?\d{1,2}\.\d+)!4d(-?\d{1,3}\.\d+)/, // ...!3d-2.17!4d-79.92
    /^(-?\d{1,2}\.\d+)\s*,\s*(-?\d{1,3}\.\d+)$/, // -2.17, -79.92
  ];
  for (const patron of patrones) {
    const m = patron.exec(limpio);
    if (m) {
      const lat = Number(m[1]);
      const lng = Number(m[2]);
      if (Math.abs(lat) <= 90 && Math.abs(lng) <= 180) return { latitud: m[1], longitud: m[2] };
    }
  }
  return null;
}

export function enlaceMapa(latitud: string | null, longitud: string | null): string | null {
  return latitud && longitud ? `https://maps.google.com/?q=${latitud},${longitud}` : null;
}
