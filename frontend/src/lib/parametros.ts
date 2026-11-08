import type { Parametro, ValorParametro } from "@/types/parametros";

/** Lo que la persona tiene escrito en el control de un parámetro: un texto
 * (número, texto libre u opción elegida) o un sí/no (interruptor). */
export type Borrador = string | boolean;

export type RevisionBorrador = {
  /** Valor ya convertido y listo para enviar, o null si no es válido. */
  valor: ValorParametro | null;
  error: string | null;
};

/** El borrador con el que arranca el control: el valor que rige hoy. */
export function borradorInicial(p: Parametro): Borrador {
  return p.tipo === "booleano" ? p.valor === true : String(p.valor);
}

/** Valida lo escrito con las mismas reglas que el backend (que es quien manda):
 * aquí solo se adelanta el mensaje para no esperar a que el servidor lo rechace. */
export function revisarBorrador(p: Parametro, b: Borrador): RevisionBorrador {
  if (p.tipo === "booleano") return { valor: b === true, error: null };

  const texto = String(b).trim();
  if (p.tipo === "entero") {
    const unidad = p.unidad ? ` ${p.unidad}` : "";
    const mensaje = `Escribe un número entero entre ${p.minimo} y ${p.maximo}${unidad}.`;
    if (!/^\d{1,6}$/.test(texto)) return { valor: null, error: mensaje };
    const numero = Number(texto);
    if ((p.minimo != null && numero < p.minimo) || (p.maximo != null && numero > p.maximo)) return { valor: null, error: mensaje };
    return { valor: numero, error: null };
  }
  if (p.tipo === "opcion") {
    return texto ? { valor: texto, error: null } : { valor: null, error: "Elige una de las opciones." };
  }
  if (!texto) return { valor: null, error: "No puede quedar vacío." };
  if (p.largoMaximo != null && texto.length > p.largoMaximo) {
    return { valor: null, error: `Es demasiado largo: máximo ${p.largoMaximo} caracteres.` };
  }
  return { valor: texto, error: null };
}

/** ¿Lo escrito es distinto de lo que rige hoy? Solo entonces tiene sentido guardar. */
export function haCambiado(p: Parametro, revision: RevisionBorrador): boolean {
  return revision.valor !== null && revision.valor !== p.valor;
}

/** Valor legible: «40 mensajes», «Encendido», «Sonnet 5 (el actual)», o el texto entre comillas. */
export function formatearValor(p: Parametro, valor: ValorParametro | null | undefined): string {
  if (valor === null || valor === undefined) return "—";
  if (p.tipo === "booleano") return valor === true ? "Encendido" : "Apagado";
  if (p.tipo === "entero") return p.unidad ? `${valor} ${p.unidad}` : String(valor);
  if (p.tipo === "opcion") return p.opciones.find((o) => o.valor === valor)?.etiqueta ?? String(valor);
  const texto = String(valor);
  return `«${texto.length > 70 ? `${texto.slice(0, 70)}…` : texto}»`;
}

/** Lo mismo pero partiendo del texto tal como lo guarda la base (historial de cambios). */
export function formatearTextoGuardado(p: Parametro | undefined, texto: string | null): string {
  if (texto === null) return "valor original";
  if (!p) return texto;
  if (p.tipo === "booleano") return formatearValor(p, texto === "true");
  if (p.tipo === "entero") return formatearValor(p, Number(texto));
  return formatearValor(p, texto);
}
