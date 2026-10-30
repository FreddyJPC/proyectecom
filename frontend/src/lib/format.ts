/** Formateadores de presentación compartidos. Solo dan formato visual: los
 * montos siguen viajando y calculándose como string (nunca float). */

/** "2154.80" -> "$2,154.80". Entrada inválida -> "—". No convierte a número:
 * trabaja sobre el texto para no introducir errores de redondeo. Acepta un
 * número solo porque Rocketfy a veces manda `0` en vez de "0.00". */
export function formatMoney(valor: string | number | null | undefined): string {
  if (valor == null || valor === "") return "—";
  const limpio = String(valor).trim();
  if (!/^-?\d+(\.\d+)?$/.test(limpio)) return "—";

  const negativo = limpio.startsWith("-");
  const [entero, decimales = ""] = limpio.replace("-", "").split(".");
  const conMiles = entero.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  const dec = (decimales + "00").slice(0, 2);
  return `${negativo ? "-" : ""}$${conMiles}.${dec}`;
}

/** "593987654321" -> "+593 98 765 4321". Si no tiene la forma de un celular
 * ecuatoriano, devuelve el número tal cual para no ocultar información. */
export function formatPhone(telefono: string | null | undefined): string {
  if (!telefono) return "—";
  const digitos = telefono.replace(/\D/g, "");
  if (/^5939\d{8}$/.test(digitos)) {
    return `+593 ${digitos.slice(3, 5)} ${digitos.slice(5, 8)} ${digitos.slice(8)}`;
  }
  return telefono;
}

export function iniciales(nombre: string | null | undefined): string {
  if (!nombre) return "?";
  const partes = nombre.trim().split(/\s+/).filter(Boolean);
  if (partes.length === 0) return "?";
  if (partes.length === 1) return partes[0].charAt(0).toUpperCase();
  return (partes[0].charAt(0) + partes[1].charAt(0)).toUpperCase();
}

export function tiempoRelativo(iso: string | null | undefined): string {
  if (!iso) return "—";
  const diffMs = Date.now() - new Date(iso).getTime();
  const minutos = Math.round(diffMs / 60000);
  if (minutos < 1) return "ahora";
  if (minutos < 60) return `hace ${minutos} min`;
  const horas = Math.round(minutos / 60);
  if (horas < 24) return `hace ${horas} h`;
  const dias = Math.round(horas / 24);
  if (dias < 30) return `hace ${dias} d`;
  return formatFecha(iso);
}

/** "30 oct" (o "30 oct 2025" si no es del año en curso). */
export function formatFecha(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  const esteAnio = d.getFullYear() === new Date().getFullYear();
  return new Intl.DateTimeFormat("es-EC", {
    day: "numeric",
    month: "short",
    ...(esteAnio ? {} : { year: "numeric" }),
  })
    .format(d)
    .replace(".", "");
}

/** "30 oct, 14:05" */
export function formatFechaHora(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  const hora = new Intl.DateTimeFormat("es-EC", { hour: "2-digit", minute: "2-digit", hour12: false }).format(d);
  return `${formatFecha(iso)}, ${hora}`;
}

/** "14:05" */
export function formatHora(iso: string | null | undefined): string {
  if (!iso) return "";
  return new Intl.DateTimeFormat("es-EC", { hour: "2-digit", minute: "2-digit", hour12: false }).format(new Date(iso));
}

/** Etiqueta de día para separar mensajes: "Hoy", "Ayer" o "30 oct". */
export function etiquetaDia(iso: string): string {
  const d = new Date(iso);
  const hoy = new Date();
  const mismoDia = (a: Date, b: Date) =>
    a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
  if (mismoDia(d, hoy)) return "Hoy";
  const ayer = new Date(hoy);
  ayer.setDate(hoy.getDate() - 1);
  if (mismoDia(d, ayer)) return "Ayer";
  return formatFecha(iso);
}

/** "en 17 h" / "en 25 min" para cuenta regresiva de la ventana de WhatsApp. */
export function tiempoRestante(iso: string | null | undefined): string {
  if (!iso) return "";
  const minutos = Math.round((new Date(iso).getTime() - Date.now()) / 60000);
  if (minutos <= 0) return "cerrada";
  if (minutos < 60) return `${minutos} min`;
  const horas = Math.floor(minutos / 60);
  const resto = minutos % 60;
  return resto === 0 || horas >= 10 ? `${horas} h` : `${horas} h ${resto} min`;
}
