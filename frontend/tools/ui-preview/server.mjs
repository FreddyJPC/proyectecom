// Servidor de prueba local: simula Supabase Auth y el backend Flask con datos
// realistas, SOLO para ver y capturar la UI. No toca nada real.
// Ver README.md de esta carpeta.
import fs from "node:fs";
import http from "node:http";

const PORT = Number(process.env.PORT || 5050);
const now = Date.now();
const ago = (min) => new Date(now - min * 60000).toISOString();

const USER = { id: "00000000-0000-0000-0000-000000000001", aud: "authenticated", role: "authenticated", email: "freddy@azoshop.ec", app_metadata: {}, user_metadata: {}, created_at: ago(99999) };
const SESSION = () => ({ access_token: "mock-token", token_type: "bearer", expires_in: 3600, expires_at: Math.floor(Date.now() / 1000) + 3600, refresh_token: "mock-refresh", user: USER });

// ---------- Pedidos ----------
const clientes = [
  ["María Fernanda Loor", "593987654321", "Guayaquil", "Guayas", "Av. 9 de Octubre 1234 y Boyacá", "34.90"],
  ["Carlos Andrade", "593998877665", "Quito", "Pichincha", "Calle Los Pinos N45-12 y Av. Eloy Alfaro", "24.99"],
  ["Lucía Mendoza", "593961234567", "Cuenca", "Azuay", "Av. Remigio Crespo 3-45", "49.50"],
  ["José Armijos", "593976543210", "Manta", "Manabí", "Barrio Tarqui, calle 12 y av. 4", "19.90"],
  ["Daniela Vera", "593984455667", "Ambato", "Tungurahua", "Av. Cevallos 12-34", "34.90"],
  ["Pedro Villacís", "593991122334", "Loja", "Loja", "Calle Bolívar 10-22", "29.00"],
  ["Andrea Salazar", "593958899001", "Machala", "El Oro", "Av. Las Palmeras y calle 5ta", "24.99"],
  ["Santiago Caicedo", "593967788990", "Riobamba", "Chimborazo", "Primera Constituyente 25-10", "59.90"],
  ["Gabriela Núñez", "593972233445", "Portoviejo", "Manabí", "Av. Universitaria s/n", "34.90"],
  ["Esteban Ruiz", "593983344556", "Quito", "Pichincha", "Av. de los Shyris N36-12", "39.99"],
  ["Paola Cedeño", "593954455667", "Guayaquil", "Guayas", "Cdla. Kennedy Norte Mz 5 V 3", "24.99"],
  ["Ricardo Palacios", "593965566778", "Esmeraldas", "Esmeraldas", "Av. Libertad y calle Olmedo", "44.00"],
  ["Verónica Tapia", "593976677889", "Ibarra", "Imbabura", "Av. Mariano Acosta 8-45", "34.90"],
  ["Mateo Guerrero", "593987788990", "Quevedo", "Los Ríos", "Calle 7 de Octubre y 12va", "19.90"],
];
const estadosPedido = [
  ["confirmado", 5], ["confirmado", 6], ["creado", null], ["confirmado", 7], ["confirmado", 8], ["rechazado", 3],
  ["confirmado", 5], ["error", null], ["confirmado", 6], ["pendiente_creacion", null], ["confirmado", 8], ["incompleto", null],
  ["confirmado", 2], ["confirmado", 7],
];
const lineasPor = [
  [{ sku: "AUD-BT-001", nombre: "Audífonos Bluetooth Pro", cantidad: 1 }],
  [{ sku: "RLJ-SM-014", nombre: "Reloj Inteligente Serie 7", cantidad: 1 }],
  [{ sku: "LMP-LED-220", nombre: "Lámpara LED Recargable", cantidad: 2 }],
  [{ sku: "CRG-RAP-33", nombre: "Cargador Rápido 33W", cantidad: 1 }],
];
const pedidos = clientes.map((c, i) => ({
  idLocal: 1040 - i,
  idRocketfy: estadosPedido[i][1] || ["creado", "confirmado", "rechazado"].includes(estadosPedido[i][0]) ? 884000 + i * 7 : null,
  estadoLocal: estadosPedido[i][0],
  statusIdRocketfy: estadosPedido[i][1],
  nombreCliente: c[0], telefono: c[1], canton: c[2], provincia: c[3], total: c[5],
  creadoEn: ago(35 + i * 190), actualizadoEn: ago(10 + i * 150),
  _direccion: c[4],
}));
const pedidoDetalle = (id) => {
  const p = pedidos.find((x) => String(x.idLocal) === String(id)) || pedidos[0];
  return {
    ...p, mensajeError: p.estadoLocal === "error" ? "Rocketfy respondió 422: la ciudad de destino no tiene cobertura para contra entrega." : null,
    direccion: p._direccion, direccion2: "Referencia: frente al parque central", codigoPostal: null, noContraEntrega: false,
    observacionesTransportista: "Llamar antes de llegar. Entregar solo al cliente.",
    lineas: lineasPor[p.idLocal % lineasPor.length],
    confirmadoEn: p.estadoLocal === "confirmado" ? ago(30 + (1040 - p.idLocal) * 150) : null,
  };
};

// ---------- Conversaciones ----------
const convs = [
  ["593987654321", "María Fernanda Loor", "anuncio", "escalada", "Audífonos Bluetooth Pro", true, "cliente", "Mejor prefiero hablar con una persona, ¿pueden llamarme?", 4],
  ["593998877665", "Carlos Andrade", "anuncio", "esperando_pago", "Reloj Inteligente Serie 7", false, "bot", "Perfecto Carlos, te comparto los datos para la transferencia.", 26],
  ["593961234567", "Lucía Mendoza", "directo", "activa", "Lámpara LED Recargable", false, "bot", "¿Me confirmas tu dirección completa y el cantón?", 41],
  ["593976543210", null, "anuncio", "activa", null, false, "cliente", "Hola, vi el anuncio, ¿cuánto cuesta?", 55],
  ["593984455667", "Daniela Vera", "web_formulario", "escalada", "Cargador Rápido 33W", true, "cliente", "Mi pedido llegó con el cable roto", 120],
  ["593991122334", "Pedro Villacís", "directo", "cerrada", "Reloj Inteligente Serie 7", false, "bot", "¡Gracias por tu compra, Pedro! Tu pedido va en camino.", 60 * 20],
  ["593958899001", "Andrea Salazar", "anuncio", "fria", "Audífonos Bluetooth Pro", false, "bot", "Quedo atenta por si deseas continuar con tu pedido.", 60 * 52],
  ["593967788990", "Santiago Caicedo", "anuncio", "activa", "Lámpara LED Recargable", false, "cliente", "Sí, la quiero en color blanco", 8],
  ["593972233445", "Gabriela Núñez", "directo", "esperando_pago", "Audífonos Bluetooth Pro", false, "cliente", "Ya hice la transferencia, te envío el comprobante", 15],
  ["593955667788", "Marcelo Ortiz", "anuncio", "en_gestion", "Zapatos de cuero", true, "bot", "Listo, le avisé al dueño: te escribe enseguida para coordinar 🙋", 12],
  ["17841400000000002", "Valeria Quishpe", "anuncio", "activa", "Lámpara LED Recargable", false, "cliente", "¿Hacen envíos a Loja? Vi su anuncio en Instagram", 6, "instagram"],
  ["7391850264412009", null, "directo", "escalada", "Cargador Rápido 33W", true, "cliente", "¿Pueden llamarme? Mi número es 0991112233", 33, "messenger"],
  ["593969001122", "Carla Romero", "directo", "manual", "Lámpara LED Recargable", false, "humano", "Hola Carla, soy Freddy, yo te ayudo con tu pedido.", 4],
];
const conversaciones = convs.map((c, i) => ({
  id: 301 - i, canal: c[9] || "whatsapp", idExterno: c[0], telefono: c[9] ? null : c[0], nombre: c[9] ? (c[1] || "usuario_" + c[0].slice(-4)) : c[1],
  nombreCliente: c[1], origen: c[2], estado: c[3], productoInteres: c[4], sinRevisar: c[5],
  ultimoMensaje: { rol: c[6], contenido: c[7], creadoEn: ago(c[8]) }, creadaEn: ago(c[8] + 300), actualizadaEn: ago(c[8]),
}));
const mensajesDe = (c) => {
  const base = [
    ["cliente", "Hola, vi su anuncio de los " + (c.productoInteres || "audífonos") + ". ¿Todavía tienen disponibles?"],
    ["bot", "¡Hola! Soy Victoria, de AzoShop 😊 Sí, tenemos stock. El precio es $34.90 con envío gratis y pagas al recibir."],
    ["cliente", "¿Y hacen envíos a mi ciudad?"],
    ["bot", "¡Claro! Enviamos a todo el Ecuador. ¿Me indicas tu nombre, dirección y cantón para registrar tu pedido?"],
    ["cliente", c.nombreCliente ? `Soy ${c.nombreCliente}, vivo en el centro` : "Prefiero pensarlo un poco"],
    [c.estado === "escalada" ? "bot" : "bot", c.estado === "escalada" ? "Entiendo. Voy a pasar tu caso a una persona del equipo para que te ayude mejor." : "Perfecto, ¿qué dirección registro para la entrega?"],
    [c.ultimoMensaje.rol, c.ultimoMensaje.contenido],
  ];
  const lista = base.map((m, i) => ({ id: c.id * 100 + i, rol: m[0], contenido: m[1], tipo: "texto", creadoEn: ago(180 - i * 22) }));
  // Archivos del cliente (fotos y audios) para ver cómo se muestran: solo en las dos primeras conversaciones.
  if (c.id >= 300) {
    lista.splice(4, 0,
      { id: c.id * 100 + 50, rol: "cliente", contenido: "[imagen]", tipo: "imagen", creadoEn: ago(120), tieneArchivo: true, analisis: "Comprobante de pago: Transferencia (monto: $34.90; fecha: 2026-11-09; banco: Pichincha; referencia: 884412)" },
      { id: c.id * 100 + 51, rol: "cliente", contenido: "[audio]", tipo: "audio", creadoEn: ago(118), tieneArchivo: true, analisis: "quiero dos más pero de color blanco, ¿me los pueden enviar juntos?" },
    );
  }
  return lista;
};
// Anuncios (Click-to-WhatsApp): lo que Meta manda de cada uno y a qué producto está vinculado (null = sin vincular).
const anunciosMeta = {
  "120210000123": { titulo: "Audífonos Bluetooth Pro · 30 h de batería", texto: "Cancelación de ruido, estuche de carga y envío a todo el Ecuador. Escríbenos y pregunta por tu color.", urlAnuncio: "https://www.facebook.com/ads/library/?id=120210000123", tipoOrigen: "ad", tipoMedia: "image", imagenUrl: `http://127.0.0.1:${PORT}/storage/v1/object/public/productos/anuncio-1.svg`, miniaturaUrl: null },
  "120210000456": { titulo: "Lámpara LED recargable", texto: "Luz cálida, 3 intensidades y hasta 20 horas de uso.", urlAnuncio: "https://www.facebook.com/ads/library/?id=120210000456", tipoOrigen: "ad", tipoMedia: "video", imagenUrl: null, miniaturaUrl: `http://127.0.0.1:${PORT}/storage/v1/object/public/productos/anuncio-2.svg` },
  "120210000789": { titulo: "Zapatos de cuero hechos a mano · 2x1", texto: null, urlAnuncio: null, tipoOrigen: "ad", tipoMedia: "image", imagenUrl: null, miniaturaUrl: null },
};
const vinculosAnuncio = { "120210000123": { sku: "AUD-BT-001", nombre: "Video principal" }, "120210000456": { sku: "LMP-LED-220", nombre: null } };
const nombreProductoBot = (sku) => (productosBot.find((f) => f.sku === sku) || {}).nombre || sku;
const anuncioDeConv = (c) => {
  if (c.origen !== "anuncio") return { id: null, llegadas: [] };
  const id = c.telefono === "593976543210" ? "120210000789" : c.telefono === "593998877665" ? "120210000456" : "120210000123";
  const extra = c.telefono === "593987654321" ? [{ idAnuncio: "120210000456", titulo: anunciosMeta["120210000456"].titulo, creadoEn: ago(60 * 24 * 12) }] : [];
  return { id, llegadas: [{ idAnuncio: id, titulo: anunciosMeta[id].titulo, creadoEn: c.creadaEn }, ...extra] };
};
const convDetalle = (id) => {
  const c = conversaciones.find((x) => String(x.id) === String(id)) || conversaciones[0];
  const cerrada = ["fria", "cerrada"].includes(c.estado);
  const ad = anuncioDeConv(c);
  const meta = ad.id ? anunciosMeta[ad.id] : null;
  const vinculo = ad.id ? vinculosAnuncio[ad.id] : null;
  const gratuita = !ad.id ? { estado: "sin_anuncio", expiraEn: null, responderAntesDe: null }
    : c.estado === "fria" ? { estado: "cerrada", expiraEn: null, responderAntesDe: null }
    : c.telefono === "593976543210" ? { estado: "pendiente", expiraEn: null, responderAntesDe: new Date(now + 20 * 3600000).toISOString() }
    : { estado: "abierta", expiraEn: new Date(now + 5 * 86400000).toISOString(), responderAntesDe: null };
  return {
    conversacion: {
      id: c.id, contactoId: c.id, canal: c.canal, idExterno: c.idExterno, telefono: c.telefono, nombre: c.nombre,
      origen: c.origen, estado: c.estado, idAnuncio: ad.id,
      notasInternas: c.estado === "escalada" ? "Cliente pidió llamada. Escribirle primero por aquí." : "",
      ventanaAbierta: !cerrada, ventanaExpiraEn: cerrada ? null : new Date(now + 17 * 3600000).toISOString(), creadaEn: c.creadaEn, actualizadaEn: c.actualizadaEn,
      ventanaGratuita: gratuita,
      anuncio: meta ? { idAnuncio: ad.id, ...meta, producto: vinculo ? { sku: vinculo.sku, nombre: nombreProductoBot(vinculo.sku) } : null, llegadas: ad.llegadas.length } : null,
      llegadasPorAnuncio: ad.llegadas,
    },
    lead: c.nombreCliente ? {
      nombreCliente: c.nombreCliente, direccion: "Av. 9 de Octubre 1234 y Boyacá", canton: "Guayaquil", provincia: "Guayas",
      productoSku: "AUD-BT-001", productoNombre: c.productoInteres, productoVariante: "Negro", total: "34.90", metodoPago: c.estado === "esperando_pago" ? "transferencia" : "contraentrega",
      estadoPago: null, estado: c.estado === "cerrada" ? "despachado" : "en_proceso", idPedidoLocal: c.estado === "cerrada" ? 1035 : null, idPedidoRocketfy: c.estado === "cerrada" ? 884035 : null,
    } : null,
    mensajes: mensajesDe(c),
  };
};

// ---------- Anuncios ----------
const dosDecimales = (n) => Number(n).toFixed(2);
const estadoAnuncios = [
  { id: "120210000789", llegadas: 5, conversaciones: 5, ventas: 0, ingresos: 0, ganancia: 0, sinCosto: 0, ultima: ago(60 * 3), primera: ago(60 * 24 * 2) },
  { id: "120210000123", llegadas: 14, conversaciones: 12, ventas: 3, ingresos: 104.7, ganancia: 38.4, sinCosto: 0, ultima: ago(25), primera: ago(60 * 24 * 20) },
  { id: "120210000456", llegadas: 6, conversaciones: 5, ventas: 1, ingresos: 29.9, ganancia: 12.8, sinCosto: 1, ultima: ago(60 * 30), primera: ago(60 * 24 * 9) },
  { id: "120210000999", llegadas: 0, conversaciones: 0, ventas: 0, ingresos: 0, ganancia: 0, sinCosto: 0, ultima: null, primera: null, soloVinculo: true },
];
const nombresVinculo = { "120210000999": "Anuncio de prueba (zapatos)" };
vinculosAnuncio["120210000999"] = { sku: "PROP-0001", nombre: "Anuncio de prueba (zapatos)" };
const anuncioFila = (e) => {
  const meta = anunciosMeta[e.id] || {};
  const v = vinculosAnuncio[e.id];
  return {
    idAnuncio: e.id, productoSku: v ? v.sku : null, productoNombre: v ? nombreProductoBot(v.sku) : null, nombreVinculo: v ? v.nombre : null,
    titulo: meta.titulo || null, texto: meta.texto || null, urlAnuncio: meta.urlAnuncio || null, tipoOrigen: meta.tipoOrigen || null, tipoMedia: meta.tipoMedia || null,
    imagenUrl: meta.imagenUrl || null, miniaturaUrl: meta.miniaturaUrl || null, primeraLlegada: e.primera, ultimaLlegada: e.ultima,
    llegadas: e.llegadas, conversaciones: e.conversaciones, ventas: e.ventas, ingresos: dosDecimales(e.ingresos), ganancia: dosDecimales(e.ganancia), ventasSinCosto: e.sinCosto,
  };
};
const listaAnuncios = () => estadoAnuncios.map(anuncioFila).sort((a, b) => Number(a.productoSku !== null) - Number(b.productoSku !== null));
const resumenAnuncios = () => ({
  anuncio: { conversaciones: 17, ventas: 4, ingresos: "134.60", ganancia: "51.20" },
  directo: { conversaciones: 9, ventas: 2, ingresos: "69.80", ganancia: "24.00" },
  llegadas: 25, anunciosActivos: 3, anunciosSinVincular: estadoAnuncios.filter((e) => !e.soloVinculo && !vinculosAnuncio[e.id]).length,
});
const manejarAnuncios = (req, res, p, send) => {
  if (p === "/anuncios" && req.method === "GET") return send(listaAnuncios());
  if (p === "/anuncios/resumen" && req.method === "GET") return send(resumenAnuncios());
  const m = p.match(/^\/anuncios\/([^/]+)\/producto$/);
  if (m) {
    const id = decodeURIComponent(m[1]);
    if (req.method === "DELETE") {
      if (!vinculosAnuncio[id]) return send({ error: `El anuncio ${id} no está vinculado a ningún producto.` }, 404);
      delete vinculosAnuncio[id];
      return send({ ok: true });
    }
    if (req.method === "PUT") {
      let cuerpo = "";
      req.on("data", (d) => (cuerpo += d));
      return req.on("end", () => {
        const dato = JSON.parse(cuerpo || "{}");
        const producto = productosBot.find((f) => f.sku === dato.sku);
        if (!producto) return send({ error: `No existe el producto ${dato.sku}.` }, 404);
        const actual = vinculosAnuncio[id];
        if (actual && actual.sku !== dato.sku && !dato.reasignar) return send({ error: `El anuncio ${id} ya está vinculado a ${nombreProductoBot(actual.sku)}.`, vinculadoA: { sku: actual.sku, nombre: nombreProductoBot(actual.sku) } }, 409);
        vinculosAnuncio[id] = { sku: dato.sku, nombre: dato.nombre || (actual && actual.nombre) || null };
        if (!estadoAnuncios.find((e) => e.id === id)) estadoAnuncios.push({ id, llegadas: 0, conversaciones: 0, ventas: 0, ingresos: 0, ganancia: 0, sinCosto: 0, ultima: null, primera: null, soloVinculo: true });
        return send({ idAnuncio: id, productoSku: dato.sku, productoNombre: producto.nombre });
      });
    }
  }
  return send({ error: "mock: ruta de anuncios no implementada " + p }, 404);
};

// ---------- Leads (CRM) ----------
const ETIQUETA_TEMP = { caliente: "Caliente", tibio: "Tibio", frio: "Frío", perdido: "Perdido", ganado: "Ganado" };
const ETIQUETA_PERDIDA = { precio: "El precio", sin_respuesta: "No respondió", compro_en_otro_lado: "Compró en otro lado", sin_cobertura: "No llegamos a su ciudad", sin_stock: "Sin stock", no_le_interesa: "No le interesa", otro: "Otro motivo" };
const TEMP_ABIERTAS = ["caliente", "tibio", "frio"];
// [nombre, teléfono|null, canal, idExterno, producto, variante, cantidad, total, etapa, temperatura, quién, motivo, motivoPérdida, origen, idAnuncio, minutos desde la última actividad, noContactar, [rol, último mensaje]]
const AUD = "Audífonos Bluetooth Pro", LAM = "Lámpara LED recargable", ZAP = "Zapatos de cuero hechos a mano";
const leadsBase = [
  ["María Fernanda Loor", "593987654321", "whatsapp", null, AUD, "Negro", 1, "34.90", "esperando_pago", "caliente", "ia", "Pidió cómo pagar por transferencia", null, "anuncio", "120210000123", 12, false, ["cliente", "¿A qué cuenta hago la transferencia?"]],
  ["Carlos Andrade", "593998877665", "whatsapp", null, LAM, null, 2, "49.98", "recopilando_datos", "caliente", "ia", "Dio su dirección y pidió el total", null, "anuncio", "120210000456", 45, false, ["cliente", "Quito, calle Los Pinos. ¿Cuánto sería con el envío?"]],
  ["Lucía Mendoza", "593961234567", "whatsapp", null, AUD, "Blanco", 1, "34.90", "recopilando_datos", "tibio", "ia", "Preguntó por colores pero no dijo si compra", null, "directo", null, 180, false, ["bot", "Tenemos negro y blanco. ¿Cuál prefieres?"]],
  ["José Armijos", "593976543210", "whatsapp", null, ZAP, "41", 1, "59.90", "recopilando_datos", "tibio", "regla", "El cliente no escribe hace 2 días", null, "anuncio", "120210000789", 60 * 50, false, ["bot", "¿Te reservo el par en la talla 41?"]],
  ["Daniela Vera", "593984455667", "whatsapp", null, AUD, null, 1, "34.90", "recopilando_datos", "frio", "regla", "El cliente no escribe hace 5 días", null, "directo", null, 60 * 24 * 5, false, ["bot", "Quedo atenta por si te animas 😊"]],
  ["Pedro Villacís", "593991122334", "whatsapp", null, LAM, null, 1, "24.99", "recopilando_datos", "frio", "dueno", "Me dijo que cobra a fin de mes", null, "directo", null, 60 * 24 * 6, false, ["cliente", "Te aviso cuando cobre"]],
  ["Andrea Salazar", "593958899001", "whatsapp", null, AUD, null, 1, "34.90", "recopilando_datos", "perdido", "ia", "Dijo que lo encontró más barato en otra tienda", "compro_en_otro_lado", "anuncio", "120210000123", 60 * 24 * 3, false, ["cliente", "Ya lo compré en otro lado, gracias"]],
  ["Santiago Caicedo", "593967788990", "whatsapp", null, ZAP, "42", 1, "59.90", "recopilando_datos", "perdido", "regla", "El cliente no escribe hace 14 días", "sin_respuesta", "directo", null, 60 * 24 * 15, false, ["bot", "¿Sigues interesado en los zapatos?"]],
  ["Gabriela Núñez", "593972233445", "whatsapp", null, AUD, "Negro", 1, "34.90", "despachado", "ganado", "regla", "Venta cerrada", null, "anuncio", "120210000123", 60 * 24 * 2, false, ["bot", "¡Listo! Tu pedido va en camino 🚚"]],
  ["Esteban Ruiz", "593983344556", "whatsapp", null, LAM, null, 1, "39.99", "por_gestionar", "ganado", "regla", "Venta cerrada", null, "directo", null, 60 * 8, false, ["bot", "Un asesor coordinará la entrega contigo."]],
  ["Paola Cedeño", "593954455667", "whatsapp", null, AUD, null, 1, "34.90", "recopilando_datos", "perdido", "ia", "El cliente pidió que no lo contacten", "no_le_interesa", "directo", null, 60 * 24 * 9, true, ["cliente", "Por favor no me escriban más"]],
  ["Ricardo Palacios", "593965566778", "whatsapp", null, LAM, null, 1, "24.99", "recopilando_datos", "tibio", "ia", "Comparando con otro modelo", null, "directo", null, 60 * 26, false, ["cliente", "Déjame pensarlo y te cuento"]],
  ["Verónica Tapia", null, "instagram", "17841400123456789", AUD, "Blanco", 1, "34.90", "recopilando_datos", "tibio", "ia", "Preguntó por el envío a Ibarra", null, "anuncio", "120210000123", 60 * 5, false, ["cliente", "¿Llegan a Ibarra?"]],
  ["Mateo Guerrero", null, "messenger", "7123456789012345", ZAP, "40", 1, "59.90", "recopilando_datos", "caliente", "ia", "Pidió reservar su talla", null, "directo", null, 25, false, ["cliente", "Resérvame la 40 por favor"]],
  ["Juan Pérez", "593987001122", "whatsapp", null, LAM, null, 1, "24.99", "recopilando_datos", "perdido", "ia", "Vive en una zona sin cobertura de envío", "sin_cobertura", "directo", null, 60 * 24 * 4, false, ["bot", "Lo siento, aún no llegamos a tu zona."]],
];
const extraNombres = ["Sofía Burbano", "Diego Zambrano", "Camila Ortiz", "Andrés Moreira", "Valentina Paredes", "Luis Cevallos", "Karla Intriago", "Fabián Naranjo", "Mónica Ponce", "Bryan Lara", "Nataly Quishpe"];
const extraTemps = ["tibio", "caliente", "frio", "tibio", "perdido", "ganado", "tibio", "frio", "caliente", "tibio", "perdido"];
extraNombres.forEach((n, i) => {
  const t = extraTemps[i];
  const etapa = t === "ganado" ? "despachado" : "recopilando_datos";
  leadsBase.push([n, `59399000${String(1000 + i)}`, "whatsapp", null, [AUD, LAM, ZAP][i % 3], null, 1, ["34.90", "24.99", "59.90"][i % 3], etapa, t, t === "ganado" ? "regla" : i % 2 ? "ia" : "regla", t === "ganado" ? "Venta cerrada" : "Conversación revisada", t === "perdido" ? "precio" : null, i % 2 ? "anuncio" : "directo", i % 2 ? "120210000456" : null, 60 * (6 + i * 9), false, ["cliente", "Gracias, lo reviso"]]);
});
const leadsMock = leadsBase.map((r, i) => {
  const [nombre, telefono, canal, idExterno, producto, variante, cantidad, total, etapa, temperatura, quien, motivo, perdida, origen, idAnuncio, minutos, noContactar, ultimo] = r;
  const cerrado = ["perdido", "ganado"].includes(temperatura);
  return {
    id: 301 + i, contactoId: 501 + i, conversacionId: 201 + i, canal, idExterno: idExterno || telefono, telefono, nombre,
    productoSku: null, productoNombre: producto, productoVariante: variante, cantidad, total, etapa,
    temperatura, temperaturaEtiqueta: ETIQUETA_TEMP[temperatura], temperaturaMotivo: motivo, temperaturaOrigen: quien, temperaturaEn: ago(minutos),
    temperaturaFijadaHasta: quien === "dueno" ? new Date(now + 5 * 86400000).toISOString() : null,
    motivoPerdida: perdida, motivoPerdidaEtiqueta: perdida ? ETIQUETA_PERDIDA[perdida] : null,
    origen, idAnuncio, tituloAnuncio: idAnuncio ? anunciosMeta[idAnuncio].titulo : null,
    creadoEn: ago(minutos + 60 * 24 * 3), actualizadoEn: ago(minutos), cerradoEn: cerrado ? ago(minutos) : null,
    noContactar, noContactarMotivo: noContactar ? "El cliente pidió que no lo contacten" : null,
    estadoConversacion: etapa === "esperando_pago" ? "esperando_pago" : "activa",
    ultimoMensaje: { rol: ultimo[0], contenido: ultimo[1], creadoEn: ago(minutos) }, ultimoClienteEn: ago(minutos + 30),
  };
});
// Seguimiento automático: lo que el sistema le escribió a cada cliente (lead -> seguimientos, el más reciente primero).
const seguimientosLeads = {};
const textoEmpujon = "Hola 👋 ¿Sigue interesado(a)? Cuénteme y lo terminamos en un momento 😊";
const textoPlantilla = "Hola 👋 Soy Victoria, de AzoShop. ¿Sigue interesado(a)? Si necesita ayuda, escríbame y con gusto le atiendo.";
leadsMock.forEach((l) => {
  seguimientosLeads[l.id] = [];
  l.ultimoSeguimiento = null;
});
const ponerSeguimiento = (nombre, items) => {
  const l = leadsMock.find((x) => x.nombre === nombre);
  if (!l) return;
  items.forEach((it, i) => seguimientosLeads[l.id].push({ id: l.id * 10 + i, tipo: it.tipo, estado: it.estado || "enviado", contenido: it.tipo === "plantilla" ? textoPlantilla : textoEmpujon, plantilla: it.tipo === "plantilla" ? "retomar_conversacion" : null, error: it.error || null, creadoEn: ago(it.min), enviadoEn: it.estado === "fallido" ? null : ago(it.min) }));
  const ultimo = seguimientosLeads[l.id].find((x) => x.estado === "enviado");
  l.ultimoSeguimiento = ultimo ? { tipo: ultimo.tipo, enviadoEn: ultimo.enviadoEn } : null;
};
ponerSeguimiento("Daniela Vera", [{ tipo: "plantilla", min: 60 * 24 * 3 }, { tipo: "empujon", min: 60 * 24 * 4 }]);
ponerSeguimiento("José Armijos", [{ tipo: "empujon", min: 60 * 24 * 1 }]);
ponerSeguimiento("Pedro Villacís", [{ tipo: "plantilla", min: 60 * 20, estado: "fallido", error: "Template name does not exist in the translation" }, { tipo: "empujon", min: 60 * 24 * 5 }]);
const historialLeads = {}; // leadId -> cambios (más reciente primero)
leadsMock.forEach((l) => {
  const cambios = [];
  if (l.temperatura !== "tibio") cambios.push({ id: l.id * 10 + 2, de: "tibio", a: l.temperatura, origen: l.temperaturaOrigen, motivo: l.temperaturaMotivo, usuario: l.temperaturaOrigen === "dueno" ? "freddy@azoshop.ec" : null, creadoEn: l.temperaturaEn });
  cambios.push({ id: l.id * 10 + 1, de: null, a: "tibio", origen: "regla", motivo: "Nuevo lead", usuario: null, creadoEn: l.creadoEn });
  historialLeads[l.id] = cambios;
});
const fichaContacto = (l) => {
  const mia = leadsMock.filter((x) => x.contactoId === l.contactoId);
  const recurrente = l.nombre === "Gabriela Núñez";
  const compras = l.temperatura === "ganado" ? (recurrente ? 2 : 1) : 0;
  const total = compras ? (recurrente ? "69.80" : l.total) : "0.00";
  const noContactar = l.noContactar;
  return {
    id: l.contactoId, nombre: l.nombre, telefono: l.telefono, tipo: compras === 0 ? "prospecto" : compras === 1 ? "cliente" : "recurrente",
    noContactar, noContactarMotivo: noContactar ? l.noContactarMotivo : null, noContactarEn: noContactar ? ago(60 * 24 * 9) : null, noContactarPor: noContactar ? "ia" : null,
    creadoEn: l.creadoEn,
    conversaciones: [{ id: l.conversacionId, canal: l.canal, idExterno: l.idExterno, estado: l.estadoConversacion, creadaEn: l.creadoEn }],
    leads: recurrente
      ? [{ id: l.id, conversacionId: l.conversacionId, productoNombre: l.productoNombre, temperatura: l.temperatura, etapa: l.etapa, total: l.total, origen: l.origen, creadoEn: l.creadoEn, cerradoEn: l.cerradoEn },
         { id: 9001, conversacionId: l.conversacionId, productoNombre: LAM, temperatura: "ganado", etapa: "despachado", total: "34.90", origen: "directo", creadoEn: ago(60 * 24 * 40), cerradoEn: ago(60 * 24 * 38) }]
      : mia.map((x) => ({ id: x.id, conversacionId: x.conversacionId, productoNombre: x.productoNombre, temperatura: x.temperatura, etapa: x.etapa, total: x.total, origen: x.origen, creadoEn: x.creadoEn, cerradoEn: x.cerradoEn })),
    compras: { cantidad: compras, totalGastado: total, ganancia: compras ? "27.40" : "0.00", comprasSinCosto: 0, ultimaCompra: compras ? l.cerradoEn : null },
    anuncios: { llegadas: l.origen === "anuncio" ? 1 : 0, primera: l.origen === "anuncio" ? l.creadoEn : null, ultima: l.origen === "anuncio" ? l.creadoEn : null, primerAnuncio: l.idAnuncio ? { idAnuncio: l.idAnuncio, titulo: l.tituloAnuncio } : null },
  };
};
const detalleLead = (l) => ({ lead: l, historial: historialLeads[l.id], contacto: fichaContacto(l), seguimientos: seguimientosLeads[l.id] || [] });
const resumenLeads = (dias) => {
  const abiertos = leadsMock.filter((l) => TEMP_ABIERTAS.includes(l.temperatura));
  const ganados = leadsMock.filter((l) => l.temperatura === "ganado"), perdidos = leadsMock.filter((l) => l.temperatura === "perdido");
  const suma = (arr) => arr.reduce((a, l) => a + Number(l.total || 0), 0).toFixed(2);
  const motivos = {};
  perdidos.forEach((l) => { const k = l.motivoPerdida || "otro"; motivos[k] = (motivos[k] || 0) + 1; });
  const cerrados = ganados.length + perdidos.length;
  return {
    calientes: abiertos.filter((l) => l.temperatura === "caliente").length, tibios: abiertos.filter((l) => l.temperatura === "tibio").length, frios: abiertos.filter((l) => l.temperatura === "frio").length,
    valorEnJuego: suma(abiertos), nuevos: leadsMock.length, ganados: ganados.length, perdidos: perdidos.length, ingresosGanados: suma(ganados),
    tasaDeCierre: cerrados ? ((ganados.length * 100) / cerrados).toFixed(1) : null,
    noContactar: new Set(leadsMock.filter((l) => l.noContactar).map((l) => l.contactoId)).size,
    motivosDePerdida: Object.entries(motivos).sort((a, b) => b[1] - a[1]).map(([motivo, leads]) => ({ motivo, etiqueta: ETIQUETA_PERDIDA[motivo], leads })),
  };
};
const ORDEN_TEMP = ["caliente", "tibio", "frio", "perdido", "ganado"];
const manejarLeads = (req, res, p, q, send) => {
  if (p === "/leads" && req.method === "GET") {
    let items = leadsMock.slice();
    if (q.get("temperatura")) { const t = q.get("temperatura").split(","); items = items.filter((l) => t.includes(l.temperatura)); }
    if (q.get("etapa")) items = items.filter((l) => l.etapa === q.get("etapa"));
    if (q.get("origen")) items = items.filter((l) => l.origen === q.get("origen"));
    if (q.get("canal")) items = items.filter((l) => l.canal === q.get("canal"));
    if (q.get("noContactar")) items = items.filter((l) => String(l.noContactar) === q.get("noContactar"));
    if (q.get("sinRespuestaDias")) items = items.filter((l) => (now - new Date(l.ultimoClienteEn).getTime()) / 86400000 >= Number(q.get("sinRespuestaDias")));
    if (q.get("q")) items = items.filter((l) => ((l.nombre || "") + (l.telefono || "") + l.idExterno + (l.productoNombre || "")).toLowerCase().includes(q.get("q").toLowerCase()));
    const orden = q.get("orden") || "actividad";
    items.sort((a, b) =>
      orden === "valor" ? Number(b.total || 0) - Number(a.total || 0)
      : orden === "temperatura" ? ORDEN_TEMP.indexOf(a.temperatura) - ORDEN_TEMP.indexOf(b.temperatura)
      : orden === "antiguedad" ? new Date(a.creadoEn) - new Date(b.creadoEn)
      : new Date(b.actualizadoEn) - new Date(a.actualizadoEn));
    return send(paginar(items, q));
  }
  if (p === "/leads/resumen" && req.method === "GET") return send(resumenLeads(q.get("dias")));
  let m = p.match(/^\/leads\/(\d+)$/);
  if (m) {
    const l = leadsMock.find((x) => x.id === Number(m[1]));
    if (!l) return send({ error: `No existe el lead ${m[1]}.` }, 404);
    if (req.method === "GET") return send(detalleLead(l));
    if (req.method === "PATCH") {
      let cuerpo = "";
      req.on("data", (d) => (cuerpo += d));
      return req.on("end", () => {
        const dato = JSON.parse(cuerpo || "{}");
        if (!ORDEN_TEMP.includes(dato.temperatura)) return send({ error: "Datos inválidos." }, 422);
        if (["despachado", "por_gestionar"].includes(l.etapa) && dato.temperatura !== "ganado") return send({ error: "Este lead ya tiene una venta cerrada: es «ganado»." }, 409);
        const de = l.temperatura;
        l.temperatura = dato.temperatura; l.temperaturaEtiqueta = ETIQUETA_TEMP[dato.temperatura]; l.temperaturaOrigen = "dueno";
        l.temperaturaMotivo = dato.motivo || null; l.temperaturaEn = new Date().toISOString(); l.actualizadoEn = l.temperaturaEn;
        l.motivoPerdida = dato.temperatura === "perdido" ? dato.motivoPerdida || "otro" : null; l.motivoPerdidaEtiqueta = l.motivoPerdida ? ETIQUETA_PERDIDA[l.motivoPerdida] : null;
        l.temperaturaFijadaHasta = TEMP_ABIERTAS.includes(dato.temperatura) ? new Date(Date.now() + 7 * 86400000).toISOString() : null;
        historialLeads[l.id].unshift({ id: Date.now(), de, a: dato.temperatura, origen: "dueno", motivo: dato.motivo || null, usuario: USER.email, creadoEn: l.temperaturaEn });
        return send(detalleLead(l));
      });
    }
  }
  m = p.match(/^\/contactos\/(\d+)\/no-contactar$/);
  if (m && req.method === "PUT") {
    let cuerpo = "";
    req.on("data", (d) => (cuerpo += d));
    return req.on("end", () => {
      const dato = JSON.parse(cuerpo || "{}");
      leadsMock.filter((l) => l.contactoId === Number(m[1])).forEach((l) => {
        l.noContactar = !!dato.noContactar; l.noContactarMotivo = dato.noContactar ? dato.motivo || null : null;
        if (dato.noContactar && TEMP_ABIERTAS.includes(l.temperatura)) { l.temperatura = "perdido"; l.temperaturaEtiqueta = "Perdido"; l.motivoPerdida = "no_le_interesa"; l.motivoPerdidaEtiqueta = ETIQUETA_PERDIDA.no_le_interesa; l.temperaturaMotivo = "Marcado como «no contactar»"; }
      });
      return send({ ok: true });
    });
  }
  return send({ error: "mock: ruta de leads no implementada " + p }, 404);
};

// ---------- Incidencias ----------
const eventos = [
  [7, "Novedad", "Cliente no contesta llamadas. Se reprograma la entrega.", 1036, 884014], [6, "En ruta", null, 1038, 884028], [8, "Entregado", "Entregado a cliente. Cobro realizado.", 1039, 884035],
  [7, "Novedad", "Dirección incorrecta, se solicita referencia adicional.", 1034, 884042], [5, "Enviado", null, 1040, 884000], [9, "Devuelto en tránsito", "Cliente rechazó el paquete en puerta.", 1030, 884049],
  [12, "Aplazado", "Cliente pidió entrega para el sábado.", 1033, 884056], [6, "En ruta", null, 1037, 884063], [8, "Entregado", null, 1031, 884070], [4, "Preparado", null, 1032, 884077],
].map((e, i) => ({ id: 900 - i, idRocketfy: e[4], idLocal: e[3], statusId: e[0], statusName: e[1], details: e[2], trackingCode: i % 3 === 0 ? "GT-88214" + i : null, trackingUrl: null, shippingCompany: "Servientrega", eventDate: ago(20 + i * 95), recibidoEn: ago(18 + i * 95) }));
const alertas = [
  ["AUD-BT-001", "stock_bajo", { stock: 4, umbral: 10 }, 35], ["RLJ-SM-014", "cambio_precio", { precioAnterior: "29.90", precioActual: "34.90" }, 240],
  ["LMP-LED-220", "stock_bajo", { stock: 2, umbral: 8 }, 600], ["CRG-RAP-33", "cambio_precio", { precioAnterior: "14.00", precioActual: "12.50" }, 1500],
  // Fase F: los genera la sincronización de productos publicados
  ["SPK-MIN-20", "producto_agotado", { stock: 0 }, 90], ["CRG-RAP-33", "margen_en_riesgo", { costoAnterior: "5.50", costoActual: "7.00", precio: "12.50", margenPct: "4.0", margenMinimoPct: "25.00" }, 180],
].sort((a, b) => a[3] - b[3]).map((a, i) => ({ id: 50 - i, sku: a[0], tipo: a[1], detalle: a[2], creadoEn: ago(a[3]) }));

// ---------- Catálogo ----------
const catalogo = [
  ["AUD-BT-001", "Audífonos Bluetooth Pro", "34.90", 4], ["RLJ-SM-014", "Reloj Inteligente Serie 7", "34.90", 62], ["LMP-LED-220", "Lámpara LED Recargable", "24.99", 2],
  ["CRG-RAP-33", "Cargador Rápido 33W", "12.50", 140], ["CAM-SEG-360", "Cámara de Seguridad 360°", "39.99", 28], ["PWB-10K", "Power Bank 10.000 mAh", "19.90", 85],
  ["SPK-MIN-20", "Parlante Bluetooth Mini", "22.00", 0], ["TCL-MEC-RGB", "Teclado Mecánico RGB", "44.00", 17], ["MSE-ERG-10", "Mouse Ergonómico Inalámbrico", "18.90", 53],
  ["SOP-LAP-02", "Soporte Plegable para Laptop", "15.50", 71], ["FND-SIL-15", "Funda de Silicona para Celular", "6.90", 310], ["GAF-LUZ-AZ", "Gafas Anti Luz Azul", "9.90", 96],
].map((p) => ({ sku: p[0], name: p[1], price: p[2], stock: p[3] }));
const monitoreados = [
  ["AUD-BT-001", 10, true, 4, "34.90", 6], ["RLJ-SM-014", 15, true, 62, "34.90", 6], ["LMP-LED-220", 8, true, 2, "24.99", 6], ["SPK-MIN-20", 10, false, 0, "22.00", 600],
].map((m) => ({ sku: m[0], umbralStockMinimo: m[1], activo: m[2], ultimoStock: m[3], ultimoPrecio: m[4], ultimoSnapshotEn: ago(m[5]) }));

const provincias = ["Azuay", "Guayas", "Loja", "Manabí", "Pichincha", "Tungurahua"];
const cantones = { Azuay: ["Cuenca", "Gualaceo"], Guayas: ["Guayaquil", "Daule", "Durán"], Loja: ["Loja", "Catamayo"], Manabí: ["Manta", "Portoviejo"], Pichincha: ["Quito", "Cayambe"], Tungurahua: ["Ambato", "Baños"] };

const metricas = {
  pedidosHoy: 9, montoTotalPedidosHoy: "287.40", confirmadosHoy: 7, ingresoConfirmado: "2154.80", ingresoHoy: "238.40", ingresoTotal: "6830.15",
  ingresoEnTransito: "1112.30", ingresoRetenidoPorNovedad: "104.80", costoProductosEnTransito: "640.20",
  avisoImportante: "Estos valores son un agregado de pedidos y montos por estado. No equivalen al saldo real de tu billetera de Rocketfy.",
};


// ---------- Mis productos (gestión de productos de ventas, Fase B) ----------
// Mantiene estado en memoria para poder probar crear, editar y publicar. Las
// reglas de verificación son un espejo reducido de backend/.../verificacion.py.
const PISO_MIN = 1000; // $10.00 en centavos (recaudo mínimo de Rocketfy)
const cents = (m) => { const r = /^(\d+)(?:\.(\d{1,2}))?$/.exec(String(m ?? "").trim()); return r ? Number(r[1]) * 100 + Number((r[2] || "").padEnd(2, "0") || 0) : null; };
const dinero = (c) => `${Math.floor(c / 100)}.${String(c % 100).padStart(2, "0")}`;
const fichaBase = (sku, nombre, estado, precio, costo, sugerido, stock, extra = {}) => ({
  sku, nombre, estado, precio, costoRocketfy: costo, precioSugeridoRocketfy: sugerido, stockUltimo: stock, stockActualizadoEn: ago(12),
  pesoKg: "0.350", imagenUrl: null, rocketfyProductId: 4800 + sku.length, descripcion: "", variantes: null, tiempoEntrega: "", metodosPago: ["contraentrega"],
  preguntasFrecuentes: null, temasNoResponder: null, maxUnidadesPorPedido: 1, notasInternas: null, precioCompetencia: null, publicadoEn: null, publicadoPor: null,
  creadoEn: ago(9000), actualizadoEn: ago(60), historial: [],
  // ADR-012: de dónde viene el producto, cómo se envía y sus fotos. Un producto de Rocketfy trae el envío en el precio.
  id: ++siguienteIdProducto, proveedor: "rocketfy", proveedorNombre: "Rocketfy", categoriaId: null, categoria: null, costoPropio: null, controlaStock: true,
  envioIncluido: true, costoFleteEstimado: null, entregas: [], imagenes: [], ...extra,
});
let siguienteIdProducto = 100;
const productosBot = [
  fichaBase("AUD-BT-001", "Audífonos Bluetooth Pro", "activo", "34.90", "18.50", "34.90", 4, {
    imagenUrl: "https://cdn.rocketfy.example/aud-bt-001.png",
    descripcion: "Audífonos inalámbricos con cancelación de ruido, hasta 30 horas de batería y estuche de carga.", tiempoEntrega: "2 a 4 días hábiles",
    variantes: "Negro, blanco", preguntasFrecuentes: "¿Trae cargador? Sí, cable USB-C incluido.", publicadoEn: ago(4000), publicadoPor: "freddy@azoshop.ec", actualizadoEn: ago(35),
    historial: [
      { accion: "editado", usuario: "freddy@azoshop.ec", cambios: { precio: ["29.90", "34.90"], tiempo_entrega: ["", "2 a 4 días hábiles"] }, creadoEn: ago(4100) },
      { accion: "publicado", usuario: "freddy@azoshop.ec", cambios: { estado: ["borrador", "activo"] }, creadoEn: ago(4000) },
      { accion: "creado", usuario: "freddy@azoshop.ec", cambios: { desde: "rocketfy" }, creadoEn: ago(9000) },
    ],
  }),
  fichaBase("RLJ-SM-014", "Reloj Inteligente Serie 7", "activo", "34.90", "20.00", "39.90", 62, {
    descripcion: "Reloj con monitor de actividad, notificaciones y resistencia al agua.", tiempoEntrega: "2 a 4 días hábiles", metodosPago: ["contraentrega", "transferencia"],
    publicadoEn: ago(2800), publicadoPor: "freddy@azoshop.ec", actualizadoEn: ago(300),
    historial: [{ accion: "publicado", usuario: "freddy@azoshop.ec", cambios: { estado: ["borrador", "activo"] }, creadoEn: ago(2800) }, { accion: "creado", usuario: "freddy@azoshop.ec", cambios: { desde: "rocketfy" }, creadoEn: ago(3000) }],
  }),
  fichaBase("LMP-LED-220", "Lámpara LED Recargable", "borrador", "24.99", "12.00", "24.99", 28, {
    descripcion: "Lámpara LED recargable con tres niveles de luz.", actualizadoEn: ago(20), historial: [{ accion: "creado", usuario: "freddy@azoshop.ec", cambios: { desde: "rocketfy" }, creadoEn: ago(20) }],
  }),
  fichaBase("CRG-RAP-33", "Cargador Rápido 33W", "pausado", "12.50", "7.00", "12.50", 140, {
    descripcion: "Cargador de pared de carga rápida 33W con cable USB-C.", tiempoEntrega: "2 a 4 días hábiles", publicadoEn: ago(6000), publicadoPor: "freddy@azoshop.ec", actualizadoEn: ago(1500),
    historial: [{ accion: "pausado", usuario: "freddy@azoshop.ec", cambios: { estado: ["activo", "pausado"] }, creadoEn: ago(1500) }],
  }),
  fichaBase("SPK-MIN-20", "Parlante Bluetooth Mini", "agotado", "22.00", "11.00", "22.00", 0, {
    descripcion: "Parlante portátil con sonido de 360° y batería de 8 horas.", tiempoEntrega: "2 a 4 días hábiles", actualizadoEn: ago(600),
  }),
  fichaBase("CAM-SEG-360", "Cámara de Seguridad 360°", "archivado", "39.99", "25.00", "39.99", 28, { descripcion: "Cámara Wi-Fi con giro de 360°.", tiempoEntrega: "3 a 5 días hábiles", actualizadoEn: ago(20000) }),
];

// ---------- Productos propios (ADR-012) ----------
// Las fotos se sirven desde este mismo servidor, imitando el bucket público «productos» de Supabase Storage.
const BUCKET = "productos";
const urlFoto = (ruta) => `http://127.0.0.1:${PORT}/storage/v1/object/public/${BUCKET}/${ruta}`;
const colorDe = (texto) => { let h = 0; for (const c of texto) h = (h * 31 + c.charCodeAt(0)) % 360; return h; };
const svgFoto = (ruta) => {
  const h = colorDe(ruta);
  return `<svg xmlns="http://www.w3.org/2000/svg" width="400" height="400" viewBox="0 0 400 400"><rect width="400" height="400" fill="hsl(${h},55%,82%)"/><circle cx="200" cy="170" r="80" fill="hsl(${h},55%,45%)"/><rect x="110" y="270" width="180" height="40" rx="20" fill="hsl(${h},55%,45%)"/></svg>`;
};
let siguienteIdImagen = 1;
let siguienteIdEntrega = 10;
const nuevaImagen = (carpeta, orden) => { const storagePath = `${carpeta}/foto-${siguienteIdImagen}.jpg`; return { id: siguienteIdImagen++, url: urlFoto(storagePath), storagePath, orden }; };
const categorias = [{ id: 1, nombre: "Calzado", activo: true }, { id: 2, nombre: "Ropa", activo: true }, { id: 3, nombre: "Accesorios", activo: true }];
let siguienteIdCategoria = 4;
const nombreCategoria = (id) => categorias.find((c) => c.id === id)?.nombre ?? null;
const propio = (sku, nombre, estado, precio, costo, stock, extra = {}) => {
  const f = fichaBase(sku, nombre, estado, precio, null, null, stock, {
    proveedor: "propio", proveedorNombre: "Producto propio", costoPropio: costo, rocketfyProductId: null, pesoKg: null, metodosPago: ["contraentrega", "transferencia"], ...extra,
  });
  f.categoria = nombreCategoria(f.categoriaId);
  f.carpetaFotos = `p${f.id}`;
  return f;
};
const zapatos = propio("PROP-0001", "Zapatos de cuero", "activo", "45.00", "28.00", 14, {
  descripcion: "Zapatos de cuero genuino, hechos a mano en Cuenca. Suela antideslizante y plantilla acolchada.", tiempoEntrega: "1 a 2 días en Cuenca; 3 a 5 días al resto del país",
  variantes: "Talla 38 al 43; negro y café", preguntasFrecuentes: "¿Son de cuero real? Sí, 100 % cuero.", categoriaId: 1, envioIncluido: false, costoFleteEstimado: null,
  publicadoEn: ago(1200), publicadoPor: "freddy@azoshop.ec", actualizadoEn: ago(90), maxUnidadesPorPedido: 3,
  historial: [{ accion: "publicado", usuario: "freddy@azoshop.ec", cambios: { estado: ["borrador", "activo"] }, creadoEn: ago(1200) }, { accion: "creado", usuario: "freddy@azoshop.ec", cambios: { desde: "propio" }, creadoEn: ago(1500) }],
});
zapatos.categoria = nombreCategoria(1);
zapatos.entregas = [
  { id: 1, nombre: "Envío dentro de Cuenca", tipo: "envio", costoCliente: "2.00", costoNegocio: "1.50", cantones: ["Cuenca"], provincias: [], restoDelPais: false, direccionRetiro: null, tiempoEntrega: "1 día", activo: true },
  { id: 2, nombre: "Retiro en el local", tipo: "retiro", costoCliente: "0.00", costoNegocio: null, cantones: [], provincias: [], restoDelPais: false, direccionRetiro: "Av. Remigio Crespo 3-45, Cuenca", tiempoEntrega: "Hoy mismo", activo: true },
  { id: 3, nombre: "Envío al resto del país", tipo: "envio", costoCliente: "5.00", costoNegocio: "4.20", cantones: [], provincias: [], restoDelPais: true, direccionRetiro: null, tiempoEntrega: "3 a 5 días", activo: true },
];
zapatos.imagenes = [nuevaImagen(zapatos.carpetaFotos, 0), nuevaImagen(zapatos.carpetaFotos, 1)];
const camiseta = propio("PROP-0002", "Camiseta de algodón", "borrador", "12.00", "5.50", null, {
  descripcion: "Camiseta de algodón peinado, corte regular.", tiempoEntrega: "2 a 3 días", variantes: "S, M, L, XL", categoriaId: 2, controlaStock: false, envioIncluido: true,
  costoFleteEstimado: "3.50", actualizadoEn: ago(30), historial: [{ accion: "creado", usuario: "freddy@azoshop.ec", cambios: { desde: "propio" }, creadoEn: ago(30) }],
});
productosBot.push(zapatos, camiseta);
const PEDIDOS_30D = { "AUD-BT-001": 23, "RLJ-SM-014": 9, "CRG-RAP-33": 4 };
function margenEnRiesgo(f) {
  if (!ajustes.confirmado || !["listo", "activo", "pausado", "agotado"].includes(f.estado)) return false;
  const precio = cents(f.precio), costo = costoDe(f);
  if (!precio || costo == null) return false;
  const gan = precio - costo - fleteDe(f) - cents(ajustes.otrosCostosFijos);
  return gan <= 0 || (gan / precio) * 100 < Number(ajustes.margenMinimoPct);
}
// Lo que cuesta una unidad según de dónde viene, y el flete que se resta de la ganancia (espejo de ventas/origen.py).
const esPropio = (f) => f.proveedor === "propio";
const costoDe = (f) => cents(esPropio(f) ? f.costoPropio : f.costoRocketfy);
const fleteDe = (f) => {
  if (!f.envioIncluido) return 0;
  const propio = cents(f.costoFleteEstimado);
  return propio ?? cents(ajustes.envioEstimado);
};
const resumenBot = (f) => ({
  pedidos30d: PEDIDOS_30D[f.sku] ?? 0, margenEnRiesgo: margenEnRiesgo(f), sku: f.sku, nombre: f.nombre, estado: f.estado, precio: f.precio, costoRocketfy: f.costoRocketfy, stockUltimo: f.stockUltimo,
  maxUnidadesPorPedido: f.maxUnidadesPorPedido, imagenUrl: f.imagenes[0]?.url ?? f.imagenUrl, publicadoEn: f.publicadoEn, actualizadoEn: f.actualizadoEn,
  proveedor: f.proveedor, proveedorNombre: f.proveedorNombre, categoria: f.categoria, controlaStock: f.controlaStock, envioIncluido: f.envioIncluido,
});
function verificarBot(f) {
  const bloqueos = [], avisos = [];
  if (!f.nombre.trim()) bloqueos.push("Falta el nombre del producto.");
  if (!f.descripcion.trim()) bloqueos.push("Falta la descripción: es lo que Victoria cuenta al cliente.");
  if (!f.tiempoEntrega.trim()) bloqueos.push("Falta el tiempo de entrega.");
  if (!f.metodosPago.length) bloqueos.push("Falta al menos un método de pago.");
  // Un producto propio no tiene el piso de $10 de Rocketfy (el recaudo mínimo es de su contra entrega) ni su stock.
  const piso = Math.max((costoDe(f) ?? 0) + (ajustes.confirmado ? fleteDe(f) : 0), esPropio(f) ? 0 : PISO_MIN), precio = cents(f.precio);
  if (precio == null || precio <= 0) bloqueos.push("El precio debe ser mayor que cero.");
  else if (precio < piso) bloqueos.push(`El precio ($${f.precio}) está por debajo del mínimo para vender ($${dinero(piso)}).`);
  if (esPropio(f)) {
    if (f.controlaStock && f.stockUltimo === 0) bloqueos.push("No quedan unidades: sube el stock para poder vender.");
    else if (f.controlaStock && f.stockUltimo != null && f.stockUltimo <= 5) avisos.push(`Quedan pocas unidades (${f.stockUltimo}): conviene vigilarlo.`);
    if (!f.envioIncluido && !f.entregas.some((o) => o.activo)) bloqueos.push("Falta definir el envío: el precio no lo incluye y no hay ninguna opción de entrega activa.");
  } else if (f.stockUltimo === 0) bloqueos.push("Rocketfy reporta 0 unidades en stock.");
  else if (f.stockUltimo != null && f.stockUltimo <= 5) avisos.push(`Quedan pocas unidades (${f.stockUltimo}): conviene vigilarlo.`);
  if (f.metodosPago.includes("transferencia")) avisos.push("Acepta transferencia: tendrás que confirmar cada pago a mano.");
  if (!f.preguntasFrecuentes) avisos.push("No tiene preguntas frecuentes: Victoria te consultará más seguido.");
  if (f.variantes) avisos.push("Tiene variantes: Victoria deberá preguntar cuál quiere el cliente.");
  // Fase E: lista de verificación (margen, uso de la IA y compra de prueba).
  if (ajustes.confirmado && precio != null && precio > 0 && costoDe(f) != null) {
    const gan = precio - costoDe(f) - fleteDe(f) - cents(ajustes.otrosCostosFijos), mg = (gan / precio) * 100;
    if (gan <= 0) avisos.push(`Con este precio pierdes $${dinero(-gan)} por unidad (con tu envío estimado).`);
    else if (mg < Number(ajustes.margenMinimoPct)) avisos.push(`Tu margen (${mg.toFixed(1)} %) está por debajo del mínimo que definiste (${ajustes.margenMinimoPct} %).`);
  }
  if (f.estado === "borrador" || f.estado === "listo") {
    if (f.historial.some((h) => h.accion === "redactado_ia")) avisos.push("Parte de la ficha se redactó con IA: verifica que cada dato sea cierto antes de publicar (la IA puede equivocarse).");
    const sim = f.historial.find((h) => h.accion === "simulacion_completa"), edi = f.historial.find((h) => h.accion === "editado");
    if (!sim) avisos.push("Todavía no probaste una compra completa con Victoria: usa «Probar con Victoria» antes de publicar.");
    else if (edi && edi.creadoEn > sim.creadoEn) avisos.push("Cambiaste la ficha después de tu última compra de prueba con Victoria: conviene repetirla.");
  }
  return { bloqueos, avisos };
}
const detalleBot = (f) => ({ ...f, verificacion: verificarBot(f) });
const ACCIONES_BOT = { publicar: [["borrador", "listo"], "activo", "publicado"], reanudar: [["pausado", "agotado"], "activo", "reanudado"], pausar: [["activo"], "pausado", "pausado"], archivar: [["borrador", "listo", "activo", "pausado", "agotado"], "archivado", "archivado"], restaurar: [["archivado"], "borrador", "restaurado"] };

// ---------- Ajustes de precios y calculadora (Fase C) ----------
// Espejo reducido de backend/.../calculadora.py, en centavos enteros.
let ajustes = {
  margenMinimoPct: "25.00", margenObjetivoPct: "35.00", envioEstimado: "5.00", otrosCostosFijos: "0.00", otrosCostosPct: "0.00",
  redondeo: "terminado_99", topeRedaccionesDia: 20, topePruebasDia: 100, confirmado: false, actualizadoPor: null, actualizadoEn: ago(600),
  calibracionEnvio: { observaciones: 2, minimo: "7.20", mediana: "8.47", maximo: "9.10" },
};
function recomendacionBot(f, precioTxt, competenciaTxt) {
  // ADR-012: el costo y el flete salen del producto (propio o de Rocketfy); un propio no tiene el recaudo mínimo de $10 de Rocketfy.
  const costo = costoDe(f), env = fleteDe(f), fijos = cents(ajustes.otrosCostosFijos);
  const otros = Number(ajustes.otrosCostosPct) / 100, mmin = Number(ajustes.margenMinimoPct) / 100, mobj = Number(ajustes.margenObjetivoPct) / 100;
  const piso = Math.max((costo ?? 0) + (ajustes.confirmado ? env : 0), esPropio(f) ? 0 : PISO_MIN);
  const sugerido = cents(f.precioSugeridoRocketfy);
  const comp = competenciaTxt ? cents(competenciaTxt) : cents(f.precioCompetencia);
  const base = { ajustesConfirmados: ajustes.confirmado, costo: costo == null ? null : dinero(costo), piso: dinero(piso), envioEstimado: ajustes.envioEstimado,
    otrosCostosFijos: ajustes.otrosCostosFijos, otrosCostosPct: ajustes.otrosCostosPct, margenMinimoPct: ajustes.margenMinimoPct, margenObjetivoPct: ajustes.margenObjetivoPct,
    precioSugerido: sugerido == null ? null : dinero(sugerido), precioCompetencia: comp == null ? null : dinero(comp), niveles: [], evaluacion: null, avisos: [] };
  if (costo == null) { base.avisos.push("Todavía no hay costo guardado para este producto: en uno de Rocketfy pulsa «Actualizar desde Rocketfy»; en uno propio anota cuánto te cuesta. Con el costo se puede calcular el precio."); return base; }
  const ganancia = (p) => p - costo - env - fijos - Math.round(p * otros);
  const margen = (p, g) => (p > 0 ? (g / p * 100).toFixed(1) : "0.0");
  const redondear = (x) => (ajustes.redondeo === "terminado_99" ? Math.max(0, Math.ceil((x - 99) / 100)) * 100 + 99 : x);
  const precioPara = (m) => redondear(Math.max(Math.ceil((costo + env + fijos) / (1 - m - otros) - 1e-9), piso));
  const fila = (clave, nombre, p) => { const g = ganancia(p); return { clave, nombre, precio: dinero(p), ganancia: dinero(g), margenPct: margen(p, g) }; };
  const pMin = precioPara(mmin), pRec = precioPara(mobj);
  base.niveles = [fila("minimo", "Mínimo", pMin), fila("recomendado", "Recomendado", pRec)];
  if (sugerido && sugerido > pRec) base.niveles.push(fila("premium", "Premium", sugerido));
  else if (sugerido && pMin > sugerido) base.avisos.push(`Aun con tu margen mínimo, el precio ($${dinero(pMin)}) queda por encima del sugerido por Rocketfy ($${dinero(sugerido)}): vendiendo al sugerido ganarías menos de tu margen mínimo.`);
  else if (sugerido && pRec > sugerido) base.avisos.push(`Para tu margen objetivo el precio recomendado ($${dinero(pRec)}) queda por encima del sugerido por Rocketfy ($${dinero(sugerido)}): puede costarte competitividad.`);
  const pe = precioTxt ? cents(precioTxt) : null;
  if (pe) {
    const g = ganancia(pe), bajoPiso = pe < piso, bajoMargen = g / pe * 100 < Number(ajustes.margenMinimoPct);
    base.evaluacion = { precio: dinero(pe), ganancia: g < 0 ? "-" + dinero(-g) : dinero(g), margenPct: margen(pe, g), bajoPiso, bajoMargenMinimo: bajoMargen };
    if (bajoPiso) base.avisos.push(`Con $${dinero(pe)} no se podrá publicar: el mínimo para publicar es $${dinero(piso)}.`);
    if (g <= 0) base.avisos.push(`Con este precio pierdes $${dinero(-g)} por unidad (con el envío estimado).`);
    else if (bajoMargen) base.avisos.push(`Con este precio tu margen (${margen(pe, g)} %) queda por debajo de tu mínimo (${Number(ajustes.margenMinimoPct)} %).`);
    if (comp && pe > comp) base.avisos.push(`Tu precio ($${dinero(pe)}) es mayor que el de la competencia que anotaste ($${dinero(comp)}).`);
  }
  return base;
}
function manejarAjustes(req, res, send) {
  let raw = "";
  req.on("data", (c) => (raw += c));
  req.on("end", () => {
    if (req.method === "GET") return send(ajustes);
    const b = raw ? JSON.parse(raw) : {};
    const pct = (v) => /^\d{1,2}(\.\d{1,2})?$/.test(String(v));
    if (!pct(b.margenMinimoPct) || !pct(b.margenObjetivoPct) || !pct(b.otrosCostosPct)) return send({ error: "Datos inválidos.", detalle: { margenMinimoPct: ["Porcentaje inválido."] } }, 422);
    if (Number(b.margenObjetivoPct) < Number(b.margenMinimoPct)) return send({ error: "Datos inválidos.", detalle: { margenObjetivoPct: ["El margen objetivo no puede ser menor que el mínimo."] } }, 422);
    ajustes = { ...ajustes, ...b, confirmado: true, actualizadoPor: "freddy@azoshop.ec", actualizadoEn: new Date().toISOString() };
    return send(ajustes);
  });
}


// ---------- Parámetros del sistema (ADR-011) ----------
// El catálogo sale del propio backend (parametros-catalogo.json, generado desde
// src/config/parametros): así las explicaciones y los rangos son los reales. Para
// regenerarlo, ver el README de esta carpeta.
const catalogoParametros = JSON.parse(fs.readFileSync(new URL("./parametros-catalogo.json", import.meta.url), "utf8"));
const parametrosBase = catalogoParametros.grupos.flatMap((g) => g.parametros);
// Estado inicial de demostración: uno guardado en la app, uno que viene del servidor y uno con aviso.
const guardadosEnLaApp = new Map([["stock.umbral_bajo", { valor: 8, por: "freddy@azoshop.ec", en: ago(95) }]]);
const delServidor = new Map([["bot.max_mensajes_historial", 30]]);
const avisosDemo = new Map([["bot.max_turnos_herramientas", ["La variable BOT_MAX_TURNOS_HERRAMIENTAS del servidor tiene un valor no válido y se ignora (Debe ser un número entero entre 2 y 10 vueltas.)."]]]);
let historialParametros = [
  { clave: "stock.umbral_bajo", nombre: "Qué cuenta como «stock bajo»", valorAnterior: null, valorNuevo: "8", usuario: "freddy@azoshop.ec", creadoEn: ago(95) },
];
function parametroActual(base) {
  const app = guardadosEnLaApp.get(base.clave);
  const servidor = delServidor.has(base.clave) ? delServidor.get(base.clave) : null;
  const valorOriginal = servidor ?? base.valorOriginal;
  return {
    ...base,
    valor: app ? app.valor : valorOriginal,
    origen: app ? "app" : servidor !== null ? "servidor" : "original",
    valorOriginal,
    valorApp: app ? app.valor : null,
    valorServidor: servidor,
    avisos: avisosDemo.get(base.clave) ?? [],
    actualizadoPor: app ? app.por : null,
    actualizadoEn: app ? new Date(app.en).toISOString() : null,
  };
}
function maxMensajesPrueba() {
  return parametroActual(parametrosBase.find((x) => x.clave === "pruebas.max_mensajes")).valor;
}
function manejarParametros(req, res, p, q, send) {
  let raw = "";
  req.on("data", (c) => (raw += c));
  req.on("end", () => {
    if (p === "/parametros" && req.method === "GET") {
      return send({ grupos: catalogoParametros.grupos.map((g) => ({ ...g, parametros: g.parametros.map(parametroActual) })) });
    }
    if (p === "/parametros/historial") return send(historialParametros.slice(0, Number(q.get("limite") || 50)));
    const m = p.match(/^\/parametros\/(.+)$/);
    const base = m && parametrosBase.find((x) => x.clave === decodeURIComponent(m[1]));
    if (!base) return send({ error: "No existe ese parámetro." }, 404);
    const registrar = (anterior, nuevo) => historialParametros.unshift({ clave: base.clave, nombre: base.nombre, valorAnterior: anterior, valorNuevo: nuevo, usuario: "freddy@azoshop.ec", creadoEn: new Date().toISOString() });
    if (req.method === "PUT") {
      const { valor } = raw ? JSON.parse(raw) : {};
      const invalido = (mensaje) => send({ error: mensaje, detalle: { valor: [mensaje] } }, 422);
      if (base.tipo === "entero") {
        if (!Number.isInteger(valor) || valor < base.minimo || valor > base.maximo) return invalido(`Debe ser un número entero entre ${base.minimo} y ${base.maximo} ${base.unidad}.`);
      } else if (base.tipo === "booleano") {
        if (typeof valor !== "boolean") return invalido("Debe ser sí o no.");
      } else if (base.tipo === "opcion") {
        if (!base.opciones.some((o) => o.valor === valor)) return invalido("Elige una de las opciones de la lista.");
      } else if (typeof valor !== "string" || !valor.trim() || valor.trim().length > base.largoMaximo) return invalido(`Debe tener entre 1 y ${base.largoMaximo} caracteres.`);
      const antes = parametroActual(base);
      guardadosEnLaApp.set(base.clave, { valor: typeof valor === "string" ? valor.trim() : valor, por: "freddy@azoshop.ec", en: Date.now() });
      registrar(antes.origen === "app" ? String(antes.valor) : null, String(valor));
      return send(parametroActual(base));
    }
    if (req.method === "DELETE") {
      const antes = guardadosEnLaApp.get(base.clave);
      if (antes) { guardadosEnLaApp.delete(base.clave); registrar(String(antes.valor), null); }
      return send(parametroActual(base));
    }
    send({ error: "mock: método no implementado" }, 405);
  });
}

// ---------- Instrucciones de Victoria (ADR-011, P3) ----------
// Las secciones salen del backend (instrucciones-secciones.json): títulos, ayudas y textos originales reales.
const instruccionesBase = JSON.parse(fs.readFileSync(new URL("./instrucciones-secciones.json", import.meta.url), "utf8"));
let instrPublicada = null; // { id, secciones, nota, creadoPor, creadoEn, publicadaEn }
let instrBorrador = null;
let instrArchivadas = [];
let instrSiguienteId = 1;
const textosEditables = () => Object.fromEntries(instruccionesBase.secciones.filter((x) => x.editable).map((x) => [x.id, x.original]));
const versionDto = (v, estado) => v && { id: v.id, estado, nota: v.nota ?? null, creadoPor: v.creadoPor, creadoEn: v.creadoEn, publicadaEn: v.publicadaEn ?? null };
function instruccionesDto() {
  return {
    secciones: instruccionesBase.secciones.map((x) => ({
      ...x,
      vigente: x.editable ? instrPublicada?.secciones[x.id] ?? x.original : x.original,
      borrador: x.editable && instrBorrador ? instrBorrador.secciones[x.id] : null,
    })),
    usando: instrPublicada ? "publicada" : "original",
    publicada: versionDto(instrPublicada, "publicada"),
    borrador: versionDto(instrBorrador, "borrador"),
    versiones: [instrPublicada && versionDto(instrPublicada, "publicada"), ...instrArchivadas.map((v) => versionDto(v, "archivada"))].filter(Boolean).sort((a, b) => b.id - a.id),
    maximoTotal: instruccionesBase.maximoTotal,
    caracteresFijos: instruccionesBase.caracteresFijos,
  };
}
function manejarInstrucciones(req, res, p, send) {
  let raw = "";
  req.on("data", (c) => (raw += c));
  req.on("end", () => {
    const body = raw ? JSON.parse(raw) : {};
    const ahoraIso = new Date().toISOString();
    if (p === "/instrucciones-victoria" && req.method === "GET") return send(instruccionesDto());
    if (p === "/instrucciones-victoria/borrador" && req.method === "PUT") {
      const detalle = {};
      for (const x of instruccionesBase.secciones.filter((y) => y.editable)) {
        const t = String(body.secciones?.[x.id] ?? "").trim();
        if (!t) detalle[x.id] = ["No puede quedar vacía."];
        else if (t.length > x.maximo) detalle[x.id] = [`Es demasiado larga: máximo ${x.maximo} caracteres (tiene ${t.length}).`];
        else if (/^#{1,6}\s/m.test(t)) detalle[x.id] = ["No uses títulos con «#»: los títulos de cada sección los pone el sistema."];
      }
      if (Object.keys(detalle).length) return send({ error: "Las instrucciones no son válidas.", detalle }, 422);
      instrBorrador = { id: instrBorrador?.id ?? instrSiguienteId++, secciones: Object.fromEntries(Object.entries(body.secciones).map(([k, v]) => [k, String(v).trim()])), nota: body.nota, creadoPor: "freddy@azoshop.ec", creadoEn: ahoraIso };
      return send(instruccionesDto());
    }
    if (p === "/instrucciones-victoria/borrador" && req.method === "DELETE") { instrBorrador = null; return send(instruccionesDto()); }
    if (p === "/instrucciones-victoria/publicar") {
      if (!instrBorrador) return send({ error: "No hay un borrador para publicar." }, 409);
      if (instrPublicada) instrArchivadas.push(instrPublicada);
      instrPublicada = { ...instrBorrador, nota: body.nota ?? instrBorrador.nota, publicadaEn: ahoraIso };
      instrBorrador = null;
      return send(instruccionesDto());
    }
    if (p === "/instrucciones-victoria/volver-a-la-original") { if (instrPublicada) instrArchivadas.push(instrPublicada); instrPublicada = null; return send(instruccionesDto()); }
    const c = p.match(/^\/instrucciones-victoria\/versiones\/(\d+)\/cargar$/);
    if (c) {
      const v = [instrPublicada, ...instrArchivadas].filter(Boolean).find((x) => x.id === Number(c[1]));
      if (!v) return send({ error: `No existe la versión ${c[1]}.` }, 404);
      instrBorrador = { id: instrBorrador?.id ?? instrSiguienteId++, secciones: { ...textosEditables(), ...v.secciones }, nota: `Cargada desde la versión ${v.id}`, creadoPor: "freddy@azoshop.ec", creadoEn: ahoraIso };
      return send(instruccionesDto());
    }
    send({ error: "mock: ruta no implementada" }, 404);
  });
}

// ---------- Redactar con IA (Fase D) ----------
// Borrador de mentira, pero con la forma de la API real: fuentes por campo, alertas
// generales y por campo, y una cifra "inventada" (30) para ver cómo se marca.
let usadasIA = 3;
function borradorIA(f, b) {
  const notas = b.notas || {};
  const todos = {
    nombre: f.nombre,
    descripcion: `${f.nombre} liviano y práctico para el día a día. ${notas.destacar ? "Destaca: " + notas.destacar + ". " : ""}Dura hasta 30 horas de uso.`,
    variantes: "Negro, blanco",
    preguntasFrecuentes: "¿Incluye estuche? Sí.\n¿Funciona con Android y iPhone? Sí.\n¿Cuánto tarda la entrega? Eso lo confirma una persona.",
    temasNoResponder: "Garantía, devoluciones, usos médicos",
  };
  const fuentes = { nombre: "rocketfy", descripcion: "ia", variantes: "notas", preguntasFrecuentes: "mixto", temasNoResponder: "ia" };
  let alertas = [
    { campo: null, texto: "No hay datos sobre la garantía, así que no se mencionó.", origen: "ia" },
    { campo: "descripcion", texto: "Menciona «30», que no aparece en los datos de Rocketfy ni en tus notas. Verifica que sea cierto o bórralo.", origen: "verificacion" },
    { campo: "preguntasFrecuentes", texto: "La respuesta sobre Android y iPhone viene de Rocketfy: confírmala.", origen: "ia" },
  ];
  if (b.productoDeSalud) alertas.push({ campo: "descripcion", texto: "Producto de salud: no debe prometer ni sugerir beneficios; revísalo con cuidado antes de aceptarlo.", origen: "verificacion" });
  if (String(notas.otrosDatos || "").includes("INYECCION")) alertas.unshift({ campo: null, texto: "El texto de Rocketfy contiene frases que parecen instrucciones («Ignora las instrucciones»). Se trataron como datos y se ignoraron; revisa el borrador con más cuidado.", origen: "verificacion" });
  const pedidos = Array.isArray(b.campos) && b.campos.length ? b.campos : Object.keys(todos);
  const campos = {}, fu = {};
  for (const c of pedidos) { campos[c] = todos[c]; fu[c] = fuentes[c]; }
  alertas = alertas.filter((a) => a.campo === null || pedidos.includes(a.campo));
  return { campos, fuentes: fu, alertas };
}


// ---------- Probar con Victoria (Fase E) ----------
// Victoria de mentira (reglas por palabras clave), pero con la forma de la API real:
// herramientas usadas, estado de la venta en curso, pedido simulado y avisos.
let usadasPruebas = 7;
function turnoVictoria(f, b) {
  const msg = String(b.mensaje || ""), bajo = msg.toLowerCase();
  const e = {
    nombreCliente: null, direccion: null, canton: null, provincia: null, productoSku: null, productoNombre: null, productoVariante: null, cantidad: 1, total: null, subtotal: null, costoEnvio: "0.00",
    entregaOpcionId: null, entregaNombre: null, entregaTipo: null, metodoPago: null, estado: "recopilando_datos", idPedidoLocal: null, idPedidoRocketfy: null, datosConfirmacionPedidaEn: null, datosConfirmadosEn: null, ...(b.estado || {}),
  };
  const herramientas = [], avisos = [], fotos = [], solicitudes = [];
  let escalada = false, pedido = null, respuesta = "", ventaManual = null;
  const propia = esPropio(f);
  const usar = (nombre, entrada, resultado) => herramientas.push({ nombre, entrada, resultado });
  // Pide al dueño que atienda (productos propios): queda en «Por gestionar» y llega un aviso por Telegram.
  const pedirGestion = (tipo, etiqueta, detalle) => {
    solicitudes.push({ tipo, etiqueta, detalle });
    usar("solicitar_gestion", { tipo, detalle }, "Listo: el dueño ya sabe que este cliente necesita atención. Despídete con naturalidad y dile que lo contactarán enseguida.");
    avisos.push({ canal: "telegram", texto: `${etiqueta}: ${detalle}` });
  };
  const registrar = (n) => {
    const max = f.maxUnidadesPorPedido;
    if (n > max) { usar("registrar_producto", { producto_sku: f.sku, producto_nombre: f.nombre, cantidad: n }, `De este producto solo se puede pedir hasta ${max} ${max === 1 ? "unidad" : "unidades"} por pedido. Explícaselo al cliente con naturalidad.`); return false; }
    if (propia && f.controlaStock && f.stockUltimo != null && n > f.stockUltimo) { usar("registrar_producto", { producto_sku: f.sku, producto_nombre: f.nombre, cantidad: n }, `Solo quedan ${f.stockUltimo} unidades de este producto. Explícaselo al cliente con naturalidad.`); return false; }
    e.productoSku = f.sku; e.productoNombre = f.nombre; e.cantidad = n; e.subtotal = dinero(cents(f.precio) * n); e.total = dinero(cents(f.precio) * n + (cents(e.costoEnvio) ?? 0));
    usar("registrar_producto", { producto_sku: f.sku, producto_nombre: f.nombre, cantidad: n }, `Producto registrado: ${n} x ${f.nombre}. Total a cobrar: $${e.total}. Ese es el monto exacto que debes comunicarle al cliente; no lo cambies.`);
    return true;
  };
  const escalar = (motivo) => {
    escalada = true; usar("escalar_a_humano", { motivo }, "Escalado correctamente. Este es tu último mensaje — despídete cordialmente informando que un asesor la va a contactar en breve.");
    avisos.push({ canal: "telegram", texto: `Victoria escaló la conversación. Motivo: ${motivo}` });
  };
  // --- Productos propios: el pedido no se crea solo; pasa al dueño (ADR-012) ---
  const sinTildes = (t) => String(t || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();
  const aplicables = () => {
    const activas = f.entregas.filter((o) => o.activo), explicita = (o) => o.cantones.length > 0 || o.provincias.length > 0;
    const cubre = (o) => o.cantones.some((c) => sinTildes(c) === sinTildes(e.canton)) || o.provincias.some((x) => sinTildes(x) === sinTildes(e.provincia));
    const cubierto = activas.some((o) => o.tipo === "envio" && explicita(o) && cubre(o));
    return activas.filter((o) => o.tipo === "retiro" || (explicita(o) ? cubre(o) : o.restoDelPais && !cubierto));
  };
  const cerrarPropio = () => {
    const sub = cents(f.precio) * e.cantidad, env = cents(e.costoEnvio) ?? 0, opcion = f.entregas.find((o) => o.id === e.entregaOpcionId);
    const costoProd = costoDe(f) == null ? null : costoDe(f) * e.cantidad, envNegocio = f.envioIncluido ? fleteDe(f) : cents(opcion?.costoNegocio);
    const conSigno = (c) => (c < 0 ? "-" : "") + dinero(Math.abs(c));
    e.subtotal = dinero(sub); e.total = dinero(sub + env); e.estado = "por_gestionar";
    ventaManual = {
      producto: f.nombre, variante: e.productoVariante, cantidad: e.cantidad, subtotal: dinero(sub), costoEnvioCliente: dinero(env), total: dinero(sub + env),
      costoProductos: costoProd == null ? null : dinero(costoProd), costoEnvioNegocio: envNegocio == null ? null : dinero(envNegocio),
      ganancia: costoProd == null || envNegocio == null ? null : conSigno(sub + env - costoProd - envNegocio), entrega: e.entregaNombre ?? "Envío incluido en el precio", metodoPago: e.metodoPago, canal: "WhatsApp",
    };
    solicitudes.push({ tipo: "pedido_cerrado", etiqueta: "Pedido cerrado, gestionar envío", detalle: `${e.nombreCliente} · ${f.nombre} × ${e.cantidad} · $${e.total}` });
    avisos.push({ canal: "telegram", texto: `Pedido cerrado, gestionar envío: ${e.nombreCliente} (${e.canton}) — ${f.nombre} × ${e.cantidad}, total $${e.total}` });
    usar("cerrar_venta", {}, "Pedido registrado y pasado al dueño. Comunícaselo al cliente: lo contactarán para coordinar la entrega y el pago. No prometas fechas ni des cuentas bancarias.");
    respuesta = `¡Listo, ${e.nombreCliente}! Registré tu pedido: ${e.cantidad} × ${f.nombre}, total $${e.total}. Una persona del equipo te escribe enseguida para coordinar la entrega y el pago 😊`;
  };
  const elegirEntrega = (texto) => {
    const ap = aplicables(), t = sinTildes(texto), n = Number((/^\s*(\d+)\s*[).]?\s*$/.exec(texto) || [])[1] || 0);
    if (!ap.length) { pedirGestion("sin_cobertura", "Sin cobertura de envío", `${e.nombreCliente} (${e.canton}, ${e.provincia}) no tiene ninguna opción de entrega`); escalada = true; respuesta = "Para tu zona necesito confirmar la entrega con una persona del equipo; te escriben enseguida 🙋"; return; }
    const op = n ? ap[n - 1] : /retiro|retirar|recoger/.test(t) ? ap.find((o) => o.tipo === "retiro") : /envio|domicilio|casa/.test(t) ? ap.find((o) => o.tipo === "envio") : null;
    if (!op) {
      const lista = ap.map((o, i) => `${i + 1}) ${o.nombre}: ${cents(o.costoCliente) > 0 ? "$" + o.costoCliente : "sin costo"}${o.direccionRetiro ? " · se retira en " + o.direccionRetiro : ""}${o.tiempoEntrega ? " · " + o.tiempoEntrega : ""}`).join("\n");
      usar("registrar_entrega", { canton: e.canton, provincia: e.provincia }, `Opciones que le aplican a este cliente:\n${lista}\nOfrécele solo estas y, cuando elija, vuelve a llamar con su elección.`);
      respuesta = `Para tu pedido tengo estas opciones de entrega:\n${lista}\n¿Cuál prefieres?`;
      return;
    }
    e.entregaOpcionId = op.id; e.entregaNombre = op.nombre; e.entregaTipo = op.tipo; e.costoEnvio = op.costoCliente;
    e.total = dinero((cents(e.subtotal) ?? 0) + cents(op.costoCliente));
    usar("registrar_entrega", { canton: e.canton, provincia: e.provincia, opcion_id: op.id }, `Entrega registrada: ${op.nombre}. Total final con el envío: $${e.total}. Es el único monto que puedes decirle.`);
    cerrarPropio();
  };
  const datosCompletos = () => ["nombreCliente", "direccion", "canton", "provincia", "metodoPago"].every((k) => e[k]);
  if (propia && /rebaja|barato|descuento/.test(bajo)) { pedirGestion("quiere_negociar", "Quiere negociar", "Pide una rebaja si lleva más de una unidad"); escalada = true; respuesta = "Eso lo define el dueño directamente: ya le avisé y te escribe enseguida para conversarlo 🙋"; }
  else if (propia && /ir a ver|ver el producto|verlo en persona/.test(bajo)) { pedirGestion("quiere_ver_producto", "Quiere ver el producto", "Quiere verlo antes de comprarlo"); escalada = true; respuesta = "¡Claro! Le acabo de avisar al dueño para que coordine contigo; te escribe enseguida 🙋"; }
  else if (propia && /pagar/.test(bajo) && !/transferencia|contra/.test(bajo)) {
    if (!e.productoSku) registrar(1);
    pedirGestion("quiere_pagar", "Quiere pagar", "Pregunta cómo pagar");
    respuesta = "Perfecto, ya le avisé al dueño para que te indique cómo pagar. Mientras tanto, ¿me das tu nombre, dirección, cantón y provincia para dejar el pedido listo?";
  }
  else if (propia && e.productoSku && !f.envioIncluido && !e.entregaOpcionId && datosCompletos() && !/soy\s/.test(bajo)) elegirEntrega(msg);
  else if (/garant|cuotas|tarjeta|factura/.test(bajo)) { escalar("El cliente pregunta algo que no está en la ficha del producto"); respuesta = "Eso no lo tengo confirmado, así que te paso con un asesor que te lo aclara enseguida 🙋"; }
  else if (/persona|asesor|humano/.test(bajo)) { escalar("El cliente pidió hablar con una persona"); respuesta = "¡Claro! Ya te conecto con un asesor humano 🙋"; }
  else if (/foto|imagen|c[oó]mo se ve/.test(bajo)) {
    const yaEnviada = (b.historial || []).some((h) => h.rol === "bot" && h.contenido.includes(`(${f.sku})`) && h.contenido.startsWith("📷"));
    if (yaEnviada) { usar("enviar_foto_producto", { producto_sku: f.sku }, "Ya le enviaste la foto de este producto a este cliente: no la repitas."); respuesta = "¡Ya te la mandé arriba! Si quieres otro detalle, dime 😊"; }
    else if (!f.imagenes.length && !f.imagenUrl) { usar("enviar_foto_producto", { producto_sku: f.sku }, "Este producto no tiene fotos disponibles. Dile al cliente que por el momento no hay imágenes y descríbeselo con la información de su ficha; no le prometas fotos."); respuesta = `Por el momento no hay imágenes de este producto, pero te lo describo: ${f.descripcion}`; }
    else {
      // Galería propia (hasta el máximo por envío, 3 por defecto); si no hay, la foto de Rocketfy.
      const urls = f.imagenes.length ? f.imagenes.slice(0, 3).map((i) => i.url) : [f.imagenUrl];
      urls.forEach((url, i) => fotos.push({ mensaje: `📷 Foto${urls.length > 1 ? ` ${i + 1} de ${urls.length}` : ""} de ${f.nombre} (${f.sku})`, url, descripcion: f.nombre }));
      usar("enviar_foto_producto", { producto_sku: f.sku }, `${urls.length === 1 ? "Foto enviada" : urls.length + " fotos enviadas"} al cliente. Puedes decirle que ya se las mandaste.`);
      respuesta = `¡Claro! Te acabo de enviar ${urls.length === 1 ? "la foto" : "unas fotos"} 📷 ¿Te gustaría pedirlo?`;
    }
  }
  else if (/env[ií]o|demora|llega/.test(bajo) && !/soy\s/.test(bajo)) { respuesta = `La entrega es en ${f.tiempoEntrega || "el plazo que acordemos"}. Sobre el costo del envío no tengo información confirmada, ¿quieres que lo consulte con un asesor?`; }
  else if (/transferencia/.test(bajo)) {
    if (!f.metodosPago.includes("transferencia")) respuesta = "Por ahora este producto solo se paga contra entrega: pagas al recibirlo 😊";
    else { e.metodoPago = "transferencia"; e.estado = "esperando_pago"; usar("registrar_metodo_pago", { metodo_pago: "transferencia" }, "Método de pago registrado."); respuesta = "Perfecto, por transferencia. Envíame la foto del comprobante cuando lo hagas y un asesor lo confirma."; }
  } else if (/(\d+)\s*unidades?|\bdos\b/.test(bajo)) {
    const n = Number((/(\d+)\s*unidades?/.exec(bajo) || [])[1] || 2);
    respuesta = registrar(n) ? `Anotado: ${n} × ${f.nombre}. El total es $${e.total}. ¿Me das tu nombre, dirección, cantón y provincia?` : `De este producto puedes pedir hasta ${f.maxUnidadesPorPedido} por pedido. ¿Te registro ${f.maxUnidadesPorPedido}?`;
  } else if (/comprar|quiero|llevo/.test(bajo) && !e.nombreCliente && !/soy\s/.test(bajo)) {
    registrar(1);
    respuesta = `¡Genial! ${f.nombre} cuesta $${e.total}. Para enviarlo necesito tu nombre completo, dirección, cantón, provincia y si pagas contra entrega.`;
  } else if (/soy\s/.test(bajo)) {
    const nombre = (/soy ([^,.]+)/i.exec(msg) || [])[1]?.trim(), prov = provincias.find((x) => bajo.includes(x.toLowerCase())), canton = prov && cantones[prov].find((x) => bajo.includes(x.toLowerCase()));
    const dir = (/vivo en (.+?),\s*[A-ZÁÉÍÓÚ]/.exec(msg) || [])[1]?.trim();
    if (!e.productoSku) registrar(1);
    if (nombre) e.nombreCliente = nombre; if (dir) e.direccion = dir; if (canton) e.canton = canton; if (prov) e.provincia = prov;
    usar("guardar_datos_cliente", { nombre_cliente: e.nombreCliente, direccion: e.direccion, canton: e.canton, provincia: e.provincia }, "Datos guardados correctamente.");
    if (/contra ?entrega/.test(bajo)) { e.metodoPago = "contraentrega"; usar("registrar_metodo_pago", { metodo_pago: "contraentrega" }, "Método de pago registrado."); }
    const falta = ["nombreCliente", "direccion", "canton", "provincia", "metodoPago"].filter((k) => !e[k]);
    if (falta.length) respuesta = `Me falta: ${falta.join(", ")}. ¿Me los confirmas?`;
    else if (propia) { if (f.envioIncluido) cerrarPropio(); else elegirEntrega(msg); }
    else if (Number(e.total) < 10) { escalar("El total ($" + e.total + ") es menor al recaudo mínimo de contraentrega ($10.00)"); respuesta = "Un asesor te contactará para terminar tu pedido 🙋"; }
    else {
      e.idPedidoLocal = Math.floor(Date.now() / 1000); e.idPedidoRocketfy = 9000001; e.estado = "despachado";
      pedido = { confirmado: true, payload: { id: e.idPedidoLocal, name: e.nombreCliente, phone: "990000000", address: e.direccion, address_2: "", city: e.canton, province: e.provincia, total: e.total, order_details: JSON.stringify([{ sku: f.sku, name: f.nombre, quantity: e.cantidad }]), not_COD: 0, carrier_observations: "" } };
      usar("cerrar_venta", {}, `¡Pedido confirmado! Llega en ${f.tiempoEntrega}. Comunícaselo al cliente y agradécele.`);
      respuesta = `¡Pedido confirmado, ${e.nombreCliente}! Llega en ${f.tiempoEntrega}. Total a pagar al recibir: $${e.total}. ¡Gracias por tu compra!`;
    }
  } else { respuesta = `¡Hola! Soy Victoria de AzoShop 😊 Te cuento sobre ${f.nombre}: ${f.descripcion} ¿Te gustaría pedirlo?`; }
  // Victoria clasifica la temperatura del lead en cada turno (herramienta clasificar_lead); con una venta cerrada la fija el sistema.
  if (!pedido && !ventaManual) {
    const temperatura = /pagar|total|direcci|comprar|quiero/.test(bajo) ? "caliente" : /caro|no gracias|despu[eé]s/.test(bajo) ? "frio" : "tibio";
    usar("clasificar_lead", { temperatura, motivo: temperatura === "caliente" ? "Pide pagar o dar sus datos de envío" : "Sigue preguntando por el producto" }, "Temperatura registrada. Sigue atendiendo con normalidad.");
  }
  return { respuesta, herramientas, estado: e, escalada, pedido, avisos, fotos, ventaManual, solicitudes };
}

function manejarProductosBot(req, res, p, q, send) {
  let raw = "";
  req.on("data", (c) => (raw += c));
  req.on("end", () => {
    const body = raw ? JSON.parse(raw) : {};
    const usuario = "freddy@azoshop.ec";
    const hist = (f, accion, cambios) => f.historial.unshift({ accion, usuario, cambios, creadoEn: new Date().toISOString() });
    if (p === "/productos-bot" && req.method === "GET") return send(productosBot.filter((f) => q.get("incluirArchivados") === "true" || f.estado !== "archivado").map(resumenBot));
    if (p === "/productos-bot" && req.method === "POST") {
      const rk = catalogo.find((x) => x.sku === body.sku);
      if (!rk) return send({ error: `El SKU '${body.sku}' no existe en el catálogo de Rocketfy.` }, 422);
      if (productosBot.some((f) => f.sku === rk.sku)) return send({ error: `El producto '${rk.sku}' ya tiene ficha.` }, 409);
      const f = fichaBase(rk.sku, rk.name, "borrador", rk.price, String(Math.round(Number(rk.price) * 55) / 100), rk.price, rk.stock, { descripcion: `${rk.name}.`, actualizadoEn: new Date().toISOString() });
      f.costoRocketfy = dinero(Math.round((cents(rk.price) ?? 0) * 0.55));
      hist(f, "creado", { desde: "rocketfy" }); productosBot.unshift(f);
      return send(detalleBot(f), 201);
    }
    // --- Productos propios (ADR-012) ---
    if (p === "/productos-bot/propios" && req.method === "POST") {
      const detalle = {};
      if (!String(body.nombre || "").trim()) detalle.nombre = ["Escribe el nombre del producto."];
      if (!(cents(body.precio) > 0)) detalle.precio = ["El precio debe ser mayor que cero."];
      if (!body.envioIncluido && !(body.entregas || []).some((o) => o.activo !== false)) detalle.entregas = ["Agrega al menos una opción de entrega o marca que el precio ya incluye el envío."];
      if (Object.keys(detalle).length) return send({ error: "Datos inválidos.", detalle }, 422);
      const n = productosBot.filter((x) => x.proveedor === "propio").length + 1;
      const f = propio(`PROP-${String(n).padStart(4, "0")}`, String(body.nombre).trim(), "borrador", body.precio, body.costoPropio ?? null, body.controlaStock ? body.stock ?? 0 : null, {
        descripcion: body.descripcion || "", variantes: body.variantes || null, tiempoEntrega: body.tiempoEntrega || "", metodosPago: body.metodosPago?.length ? body.metodosPago : ["contraentrega"],
        preguntasFrecuentes: body.preguntasFrecuentes || null, temasNoResponder: body.temasNoResponder || null, maxUnidadesPorPedido: body.maxUnidadesPorPedido || 1,
        categoriaId: body.categoriaId ?? null, controlaStock: !!body.controlaStock, envioIncluido: !!body.envioIncluido, costoFleteEstimado: body.costoFleteEstimado || null, actualizadoEn: new Date().toISOString(),
      });
      f.categoria = nombreCategoria(f.categoriaId);
      f.entregas = (body.entregas || []).map((o) => ({ id: siguienteIdEntrega++, ...o }));
      hist(f, "creado", { desde: "propio" }); productosBot.unshift(f);
      return send(detalleBot(f), 201);
    }
    const sub = p.match(/^\/productos-bot\/([^/]+)\/(entregas|imagenes)(?:\/([^/]+))?$/);
    if (sub) {
      const f = productosBot.find((x) => x.sku === decodeURIComponent(sub[1]));
      if (!f) return send({ error: `No existe el producto '${decodeURIComponent(sub[1])}'.` }, 404);
      if (f.estado === "archivado") return send({ error: "Un producto archivado no se puede editar: restáuralo primero." }, 409);
      f.actualizadoEn = new Date().toISOString();
      if (sub[2] === "entregas" && !sub[3] && req.method === "PUT") {
        const lista = body.entregas || [];
        for (const [i, o] of lista.entries()) {
          if (!String(o.nombre || "").trim()) return send({ error: "Datos inválidos.", detalle: { entregas: [`Opción ${i + 1}: falta el nombre (por ejemplo «Envío dentro de Cuenca»).`] } }, 422);
          if (o.tipo === "retiro" && !String(o.direccionRetiro || "").trim()) return send({ error: "Datos inválidos.", detalle: { entregas: [`Opción ${i + 1}: un retiro necesita la dirección donde se retira.`] } }, 422);
        }
        f.entregas = lista.map((o) => ({ id: siguienteIdEntrega++, ...o }));
        hist(f, "editado", { entregas: [null, `${lista.length} opciones`] });
        return send(detalleBot(f));
      }
      if (sub[2] === "entregas" && sub[3] === "copiar" && req.method === "POST") {
        const origen = productosBot.find((x) => x.sku === body.desdeSku);
        if (!origen) return send({ error: `No existe el producto '${body.desdeSku}'.` }, 404);
        f.entregas = origen.entregas.map((o) => ({ ...o, id: siguienteIdEntrega++ }));
        hist(f, "editado", { entregas: [null, `copiadas de ${origen.sku}`] });
        return send(detalleBot(f));
      }
      if (sub[2] === "imagenes" && !sub[3] && req.method === "POST") {
        if (!String(body.storagePath || "").startsWith(`${f.carpetaFotos}/`)) return send({ error: "La foto debe estar en la carpeta de este producto." }, 422);
        if (f.imagenes.length >= 8) return send({ error: "Máximo 8 fotos por producto." }, 409);
        f.imagenes.push({ id: siguienteIdImagen++, url: urlFoto(body.storagePath), storagePath: body.storagePath, orden: f.imagenes.length });
        hist(f, "editado", { fotos: [f.imagenes.length - 1, f.imagenes.length] });
        return send(detalleBot(f));
      }
      if (sub[2] === "imagenes" && sub[3] === "orden" && req.method === "PUT") {
        const ids = body.ids || [];
        f.imagenes = ids.map((id, i) => ({ ...f.imagenes.find((x) => x.id === id), orden: i })).filter((x) => x.id);
        return send(detalleBot(f));
      }
      if (sub[2] === "imagenes" && sub[3] && req.method === "DELETE") {
        const antes = f.imagenes.length;
        f.imagenes = f.imagenes.filter((x) => String(x.id) !== sub[3]).map((x, i) => ({ ...x, orden: i }));
        if (f.imagenes.length === antes) return send({ error: "Esa foto no pertenece a este producto." }, 404);
        hist(f, "editado", { fotos: [antes, f.imagenes.length] });
        return send(detalleBot(f));
      }
      return send({ error: "mock: ruta no implementada " + p }, 404);
    }
    if (p === "/productos-bot/contenido/uso") { const tope = ajustes.topeRedaccionesDia; return send({ tope, usadas: usadasIA, restantes: Math.max(0, tope - usadasIA) }); }
    if (p === "/productos-bot/pruebas/uso") { const tope = ajustes.topePruebasDia; return send({ tope, usadas: usadasPruebas, restantes: Math.max(0, tope - usadasPruebas), maxMensajes: maxMensajesPrueba() }); }
    const pr = p.match(/^\/productos-bot\/([^/]+)\/probar$/);
    if (pr && req.method === "POST") {
      const f = productosBot.find((x) => x.sku === decodeURIComponent(pr[1]));
      if (!f) return send({ error: `No existe el producto '${decodeURIComponent(pr[1])}'.` }, 404);
      if (f.estado === "archivado") return send({ error: "Un producto archivado no se puede probar: restáuralo primero." }, 409);
      const faltan = [];
      if (!f.nombre.trim()) faltan.push("Falta el nombre del producto.");
      if (!f.descripcion.trim()) faltan.push("Falta la descripción de ventas: es lo que Victoria sabe del producto.");
      if (!f.tiempoEntrega.trim()) faltan.push("Falta el tiempo de entrega.");
      if (!f.metodosPago.length) faltan.push("Falta elegir al menos un método de pago.");
      if (!(cents(f.precio) > 0)) faltan.push("El precio de venta debe ser mayor que cero.");
      if (faltan.length) return send({ error: "El producto no cumple lo mínimo para esa acción.", bloqueos: faltan }, 422);
      if (body.usarBorrador && !instrBorrador) return send({ error: "No hay un borrador de instrucciones para probar: guarda uno en Parámetros → Instrucciones de Victoria." }, 409);
      const mensaje = String(body.mensaje || "").trim();
      if (!mensaje || mensaje.length > 1000) return send({ error: "Datos inválidos.", detalle: { mensaje: ["Escribe un mensaje de hasta 1000 caracteres."] } }, 422);
      if (body.escalada) return send({ error: "Victoria ya pasó esta conversación a una persona: en la vida real no seguiría respondiendo. Reinicia la prueba para empezar otra." }, 409);
      if (body.estado?.estado === "despachado" || body.estado?.estado === "por_gestionar") return send({ error: "La compra de esta prueba ya se cerró: en la vida real, si el cliente vuelve a escribir, lo atiende una persona. Reinicia la prueba para empezar otra." }, 409);
      if ((body.historial || []).filter((h) => h.rol === "cliente").length >= maxMensajesPrueba()) return send({ error: `La prueba llegó a ${maxMensajesPrueba()} mensajes. Reiníciala para empezar de nuevo.` }, 409);
      const tope = ajustes.topePruebasDia;
      if (usadasPruebas >= tope) return send({ error: `Ya usaste los ${tope} mensajes de prueba de hoy. El contador se reinicia a medianoche (hora de Ecuador); puedes subir el tope en Ajustes de precios.`, uso: { tope, usadas: usadasPruebas, restantes: 0 } }, 429);
      if (mensaje.includes("SIN_IA")) return send({ error: "Probar con Victoria no está configurado en el servidor (falta la clave de la IA)." }, 503);
      usadasPruebas += 1;
      const turno = turnoVictoria(f, { ...body, mensaje });
      if (turno.pedido || turno.ventaManual) hist(f, "simulacion_completa", null);
      return setTimeout(() => send({ ...turno, uso: { tope, usadas: usadasPruebas, restantes: Math.max(0, tope - usadasPruebas), maxMensajes: maxMensajesPrueba() } }), Number(process.env.DELAY_IA || 600));
    }
    const g = p.match(/^\/productos-bot\/([^/]+)\/contenido\/generar$/);
    if (g && req.method === "POST") {
      const f = productosBot.find((x) => x.sku === decodeURIComponent(g[1]));
      if (!f) return send({ error: `No existe el producto '${decodeURIComponent(g[1])}'.` }, 404);
      if (f.estado === "archivado") return send({ error: "Un producto archivado no se puede editar: restáuralo primero." }, 409);
      const tope = ajustes.topeRedaccionesDia;
      if (usadasIA >= tope) return send({ error: `Ya usaste los ${tope} borradores de IA de hoy. El contador se reinicia a medianoche (hora de Ecuador); puedes subir el tope en Ajustes de precios.`, uso: { tope, usadas: usadasIA, restantes: 0 } }, 429);
      if (String(body.notas?.otrosDatos || "").includes("SIN_IA")) return send({ error: "La redacción con IA no está configurada en el servidor." }, 503);
      usadasIA += 1;
      hist(f, "redactado_ia", { campos: (Array.isArray(body.campos) && body.campos.length ? body.campos : ["nombre", "descripcion", "variantes", "preguntas_frecuentes", "temas_no_responder"]).map((c) => c.replace(/[A-Z]/g, (m) => "_" + m.toLowerCase())) });
      return setTimeout(() => send({ ...borradorIA(f, body), uso: { tope, usadas: usadasIA, restantes: Math.max(0, tope - usadasIA) } }), Number(process.env.DELAY_IA || 600));
    }
    const m = p.match(/^\/productos-bot\/([^/]+)(?:\/([a-z-]+))?$/);
    if (!m) return send({ error: "mock: ruta no implementada " + p }, 404);
    const f = productosBot.find((x) => x.sku === decodeURIComponent(m[1]));
    if (!f) return send({ error: `No existe el producto '${decodeURIComponent(m[1])}'.` }, 404);
    const accion = m[2];
    if (!accion && req.method === "GET") return send(detalleBot(f));
    if (accion === "precio" && req.method === "GET") return send(recomendacionBot(f, q.get("precio"), q.get("competencia")));
    if (!accion && req.method === "PATCH") {
      if (f.estado === "archivado") return send({ error: "Un producto archivado no se puede editar: restáuralo primero." }, 409);
      const cambios = {};
      const columna = (k) => k.replace(/[A-Z]/g, (m) => "_" + m.toLowerCase()).replace("metodos_pago", "metodos_pago_aceptados");
      for (const [k, v] of Object.entries(body)) if (JSON.stringify(f[k]) !== JSON.stringify(v)) { cambios[columna(k)] = [f[k] ?? null, v]; }
      const antes = new Set(verificarBot(f).bloqueos);
      const propuesto = { ...f, ...body };
      if (f.estado === "activo") { const peor = verificarBot(propuesto).bloqueos.filter((b) => !antes.has(b)); if (peor.length) return send({ error: "El producto no cumple lo mínimo para esa acción.", bloqueos: peor }, 422); }
      Object.assign(f, body, { actualizadoEn: new Date().toISOString() });
      // ADR-012: el stock de un producto propio lo lleva la app; la categoría viaja como id y se muestra su nombre.
      if ("stock" in body) { f.stockUltimo = body.stock; delete f.stock; }
      if ("categoriaId" in body) f.categoria = nombreCategoria(body.categoriaId);
      if (Object.keys(cambios).length) hist(f, "editado", cambios);
      return send(detalleBot(f));
    }
    if (accion === "actualizar-rocketfy") { f.stockActualizadoEn = new Date().toISOString(); f.actualizadoEn = f.stockActualizadoEn; return send(detalleBot(f)); }
    const regla = ACCIONES_BOT[accion];
    if (!regla) return send({ error: "mock: acción no implementada " + accion }, 404);
    if (!regla[0].includes(f.estado)) return send({ error: `No se puede ${accion} un producto que está en estado '${f.estado}'.` }, 409);
    if (regla[1] === "activo") { const { bloqueos } = verificarBot(f); if (bloqueos.length) return send({ error: "El producto no cumple lo mínimo para esa acción.", bloqueos }, 422); }
    hist(f, regla[2], { estado: [f.estado, regla[1]] });
    f.estado = regla[1]; f.actualizadoEn = new Date().toISOString();
    if (regla[1] === "activo") { f.publicadoEn = f.actualizadoEn; f.publicadoPor = usuario; }
    return send(detalleBot(f));
  });
}

// ---------- Por gestionar (ADR-012) ----------
// Lo que espera al dueño con un producto propio. Se guarda en memoria para poder atender solicitudes.
const ETIQUETAS_SOLICITUD = { quiere_comprar: "Quiere comprar", quiere_pagar: "Quiere pagar", pide_envio: "Pide envío", quiere_ver_producto: "Quiere ver el producto", quiere_negociar: "Quiere negociar", sin_cobertura: "Sin cobertura de envío", pedido_cerrado: "Pedido cerrado, gestionar envío", otro: "Otro" };
const solicitud = (id, conversacionId, tipo, detalle, min, extra = {}) => ({
  id, conversacionId, tipo, tipoEtiqueta: ETIQUETAS_SOLICITUD[tipo], detalle, estado: "pendiente", notaAtencion: null, atendidaPor: null, creadaEn: ago(min), atendidaEn: null,
  canal: "whatsapp", idExterno: null, telefono: null, nombreCliente: null, direccion: null, canton: null, provincia: null, producto: null, variante: null, cantidad: null, metodoPago: null, entrega: null, total: null, proveedor: "propio", tienePedido: false,
  // La venta ligada: cobro y cancelación (migración 022). Las acciones disponibles las calcula `conAcciones`.
  ventaId: null, ventaEstado: null, ventaCobradaEn: null, ventaCobradaPor: null, ventaNotaCobro: null, ventaCanceladaEn: null, ventaCanceladaPor: null, ventaMotivoCancelacion: null,
  puedeCobrar: false, puedeDeshacerCobro: false, puedeCancelar: false, ...extra,
});
// Espejo de backend/src/routes/ventas/reglas.py (todas las ventas de este servidor falso son de productos propios).
const conAcciones = (x) => {
  if (x.ventaId == null) return { ...x, puedeCobrar: false, puedeDeshacerCobro: false, puedeCancelar: false };
  const cancelada = x.ventaEstado === "cancelada", cobrada = !!x.ventaCobradaEn;
  return { ...x, puedeCobrar: !cancelada && !cobrada, puedeDeshacerCobro: !cancelada && cobrada, puedeCancelar: !cancelada && !cobrada };
};
const solicitudesGestion = [
  solicitud(6, 292, "pedido_cerrado", "Pedido completo: solo falta coordinar la entrega y el pago.", 9, {
    telefono: "593955667788", nombreCliente: "Marcelo Ortiz", direccion: "Av. Remigio Crespo 3-45", canton: "Cuenca", provincia: "Azuay", producto: "Zapatos de cuero", variante: "Talla 41, negro",
    cantidad: 1, metodoPago: "contraentrega", entrega: "Envío dentro de Cuenca", total: "47.00", tienePedido: true, ventaId: 61, ventaEstado: "por_gestionar",
  }),
  solicitud(7, 295, "quiere_comprar", "Quiere la lámpara; aún no dio su teléfono.", 14, { canal: "instagram", idExterno: "17841400000000002", telefono: null, nombreCliente: "Valeria Quishpe", producto: "Lámpara LED Recargable", canton: "Loja", provincia: "Loja" }),
  solicitud(5, 298, "quiere_ver_producto", "Quiere probarse los zapatos antes de comprarlos.", 32, { telefono: "593961234567", nombreCliente: "Lucía Mendoza", producto: "Zapatos de cuero", canton: "Cuenca", provincia: "Azuay" }),
  solicitud(4, 299, "quiere_negociar", "Pide una rebaja si lleva dos pares.", 75, { telefono: "593976543210", nombreCliente: null, producto: "Zapatos de cuero", cantidad: 2 }),
  solicitud(3, 296, "sin_cobertura", "Vive en Galápagos y ninguna opción de entrega cubre ese destino.", 240, { telefono: "593958899001", nombreCliente: "Andrea Salazar", canton: "San Cristóbal", provincia: "Galápagos", producto: "Camiseta de algodón" }),
  solicitud(2, 300, "pedido_cerrado", "Pedido completo.", 60 * 20, {
    estado: "atendida", notaAtencion: "Se coordinó el envío por Servientrega; pagó contra entrega.", atendidaPor: "freddy@azoshop.ec", atendidaEn: ago(60 * 18), telefono: "593998877665", nombreCliente: "Carlos Andrade",
    direccion: "Calle Los Pinos N45-12", canton: "Quito", provincia: "Pichincha", producto: "Camiseta de algodón", variante: "M", cantidad: 2, metodoPago: "transferencia", entrega: "Envío al resto del país", total: "29.00", tienePedido: true,
    ventaId: 62, ventaEstado: "gestionada",
  }),
  // Atendida y ya cobrada (muestra «Cobrada» y deja deshacer el cobro).
  solicitud(7, 295, "pedido_cerrado", "Pedido completo.", 60 * 40, {
    estado: "atendida", notaAtencion: "Entregado en mano.", atendidaPor: "freddy@azoshop.ec", atendidaEn: ago(60 * 38), telefono: "593972233445", nombreCliente: "Gabriela Núñez",
    direccion: "Av. Universitaria s/n", canton: "Portoviejo", provincia: "Manabí", producto: "Zapatos de cuero", variante: "Talla 38, café", cantidad: 1, metodoPago: "contraentrega", entrega: "Envío al resto del país", total: "50.00", tienePedido: true,
    ventaId: 63, ventaEstado: "gestionada", ventaCobradaEn: ago(60 * 36), ventaCobradaPor: "freddy@azoshop.ec", ventaNotaCobro: "Cobrado al entregar",
  }),
  // Venta cancelada (muestra el motivo y no deja hacer nada más).
  solicitud(8, 294, "pedido_cerrado", "Pedido completo.", 60 * 60, {
    estado: "atendida", notaAtencion: "Venta cancelada: el cliente se arrepintió", atendidaPor: "freddy@azoshop.ec", atendidaEn: ago(60 * 58), telefono: "593983344556", nombreCliente: "Esteban Ruiz",
    direccion: "Av. de los Shyris N36-12", canton: "Quito", provincia: "Pichincha", producto: "Zapatos de cuero", variante: "Talla 42, negro", cantidad: 2, metodoPago: "transferencia", entrega: "Envío al resto del país", total: "95.00", tienePedido: true,
    ventaId: 64, ventaEstado: "cancelada", ventaCanceladaEn: ago(60 * 57), ventaCanceladaPor: "freddy@azoshop.ec", ventaMotivoCancelacion: "El cliente se arrepintió",
  }),
  solicitud(1, 297, "quiere_pagar", "Preguntó cómo pagar.", 60 * 30, { estado: "atendida", notaAtencion: null, atendidaPor: "freddy@azoshop.ec", atendidaEn: ago(60 * 29), telefono: "593984455667", nombreCliente: "Daniela Vera", producto: "Zapatos de cuero" }),
];
function manejarGestion(req, res, p, q, send) {
  let raw = "";
  req.on("data", (c) => (raw += c));
  req.on("end", () => {
    if (p === "/gestion" && req.method === "GET") {
      const estado = q.get("estado") || "pendiente";
      return send(solicitudesGestion.filter((x) => x.estado === estado).sort((a, b) => new Date(b.creadaEn) - new Date(a.creadaEn)).map(conAcciones));
    }
    if (p === "/gestion/resumen") return send({ pendientes: solicitudesGestion.filter((x) => x.estado === "pendiente").length });
    const m = p.match(/^\/gestion\/(\d+)\/atender$/);
    if (m && req.method === "POST") {
      const x = solicitudesGestion.find((y) => y.id === Number(m[1]));
      if (!x) return send({ error: "No existe esa solicitud." }, 404);
      if (x.estado === "atendida") return send({ error: "Esa solicitud ya estaba atendida." }, 409);
      const nota = raw ? JSON.parse(raw).nota : null;
      Object.assign(x, { estado: "atendida", notaAtencion: nota || null, atendidaPor: "freddy@azoshop.ec", atendidaEn: new Date().toISOString() });
      if (x.ventaEstado === "por_gestionar") x.ventaEstado = "gestionada";
      return send(conAcciones(x));
    }
    send({ error: "mock: ruta no implementada " + p }, 404);
  });
}
// Cobrar, deshacer el cobro y cancelar una venta (espejo de backend/src/routes/ventas/controllers.py).
function manejarVentas(req, res, p, send) {
  let raw = "";
  req.on("data", (c) => (raw += c));
  req.on("end", () => {
    const m = p.match(/^\/ventas\/(\d+)\/(cobrar|deshacer-cobro|cancelar)$/);
    if (!m || req.method !== "POST") return send({ error: "mock: ruta no implementada " + p }, 404);
    const x = solicitudesGestion.find((y) => y.ventaId === Number(m[1]));
    if (!x) return send({ error: `No existe la venta ${m[1]}.` }, 404);
    const cuerpo = raw ? JSON.parse(raw) : {};
    const usuario = "freddy@azoshop.ec", ahoraIso = new Date().toISOString();
    const cancelada = x.ventaEstado === "cancelada", cobrada = !!x.ventaCobradaEn;
    const respuesta = (extra = {}) => ({ id: x.ventaId, estado: x.ventaEstado, total: x.total, cobrada: !!x.ventaCobradaEn, stockDevuelto: 0, productoSigueAgotado: false, ...extra });
    if (m[2] === "cobrar") {
      if (cancelada) return send({ error: "Esa venta está cancelada: no se puede cobrar." }, 409);
      if (cobrada) return send({ error: "Esa venta ya estaba marcada como cobrada." }, 409);
      Object.assign(x, { ventaCobradaEn: ahoraIso, ventaCobradaPor: usuario, ventaNotaCobro: String(cuerpo.nota || "").trim() || null });
      return send(respuesta());
    }
    if (m[2] === "deshacer-cobro") {
      if (!cobrada) return send({ error: "Esa venta no estaba marcada como cobrada." }, 409);
      Object.assign(x, { ventaCobradaEn: null, ventaCobradaPor: null, ventaNotaCobro: null });
      return send(respuesta());
    }
    if (cancelada) return send({ error: "Esa venta ya estaba cancelada." }, 409);
    if (cobrada) return send({ error: "Esa venta está marcada como cobrada. Si vas a devolver el dinero, deshaz primero el cobro y luego cancélala." }, 409);
    const motivo = String(cuerpo.motivo || "").trim() || null;
    Object.assign(x, { ventaEstado: "cancelada", ventaCanceladaEn: ahoraIso, ventaCanceladaPor: usuario, ventaMotivoCancelacion: motivo });
    if (x.estado === "pendiente") Object.assign(x, { estado: "atendida", atendidaPor: usuario, atendidaEn: ahoraIso, notaAtencion: "Venta cancelada" + (motivo ? ": " + motivo : ".") });
    // Devuelve el stock de los zapatos de ejemplo (la camiseta no lleva control de stock).
    const devuelto = x.producto === "Zapatos de cuero" ? x.cantidad || 1 : 0;
    if (devuelto) zapatos.stockUltimo += devuelto;
    return send(respuesta({ stockDevuelto: devuelto }));
  });
}
function manejarCategorias(req, res, p, send) {
  let raw = "";
  req.on("data", (c) => (raw += c));
  req.on("end", () => {
    const conteo = (id) => productosBot.filter((f) => f.categoriaId === id).length;
    if (req.method === "GET") return send(categorias.map((c) => ({ ...c, productos: conteo(c.id) })));
    if (req.method === "POST") {
      const nombre = String((raw ? JSON.parse(raw) : {}).nombre || "").trim();
      if (!nombre) return send({ error: "Datos inválidos.", detalle: { nombre: ["Escribe el nombre de la categoría."] } }, 422);
      if (categorias.some((c) => c.nombre.toLowerCase() === nombre.toLowerCase())) return send({ error: `Ya existe la categoría «${nombre}».` }, 409);
      const nueva = { id: siguienteIdCategoria++, nombre, activo: true };
      categorias.push(nueva);
      return send({ ...nueva, productos: 0 }, 201);
    }
    send({ error: "mock: método no implementado" }, 405);
  });
}

// ---------- servidor ----------
function paginar(arr, q) {
  const page = Number(q.get("page") || 1), pageSize = Number(q.get("pageSize") || 20);
  return { items: arr.slice((page - 1) * pageSize, page * pageSize), total: arr.length, page, pageSize };
}
function totalesConv() {
  const esc = conversaciones.filter((c) => c.estado === "escalada");
  return { escaladas: esc.length, escaladasSinRevisar: esc.filter((c) => c.sinRevisar).length, esperandoPago: conversaciones.filter((c) => c.estado === "esperando_pago").length, enGestion: conversaciones.filter((c) => c.estado === "en_gestion").length, manual: conversaciones.filter((c) => c.estado === "manual").length };
}

const server = http.createServer((req, res) => {
  const url = new URL(req.url, `http://${req.headers.host}`);
  const p = url.pathname, q = url.searchParams;
  res.setHeader("Access-Control-Allow-Origin", req.headers.origin || "*");
  res.setHeader("Access-Control-Allow-Headers", req.headers["access-control-request-headers"] || "*");
  res.setHeader("Access-Control-Allow-Methods", "GET,POST,PUT,PATCH,DELETE,OPTIONS");
  res.setHeader("Access-Control-Allow-Credentials", "true");
  if (req.method === "OPTIONS") { res.writeHead(204); return res.end(); }
  const send = (data, status = 200) => { res.writeHead(status, { "Content-Type": "application/json" }); res.end(JSON.stringify(data)); };
  const delay = Number(process.env.DELAY || 0);
  const go = () => {
    if (p === "/health") return send({ status: "ok", scheduler: true });
    if (p === "/auth/v1/token") return send(SESSION());
    if (p === "/auth/v1/user") return send(USER);
    if (p === "/auth/v1/logout") { res.writeHead(204); return res.end(); }
    if (p === "/conversaciones") {
      let items = conversaciones;
      if (q.get("estado")) items = items.filter((c) => c.estado === q.get("estado"));
      if (q.get("origen")) items = items.filter((c) => c.origen === q.get("origen"));
      if (q.get("canal")) items = items.filter((c) => c.canal === q.get("canal"));
      if (q.get("q")) items = items.filter((c) => (c.idExterno + (c.telefono || "") + (c.nombre || "") + (c.nombreCliente || "")).toLowerCase().includes(q.get("q").toLowerCase()));
      return send({ ...paginar(items, q), totalesPorFiltroRapido: totalesConv() });
    }
    let m;
    if ((m = p.match(/^\/conversaciones\/(\d+)$/))) return send(convDetalle(m[1]));
    if ((m = p.match(/^\/conversaciones\/\d+\/mensajes\/(\d+)\/archivo$/))) {
      if (m[1].endsWith("51")) {
        // Un WAV de 0,2 s en silencio: lo justo para que el reproductor se vea.
        const n = 1600, buf = Buffer.alloc(44 + n * 2);
        buf.write("RIFF", 0); buf.writeUInt32LE(36 + n * 2, 4); buf.write("WAVEfmt ", 8); buf.writeUInt32LE(16, 16); buf.writeUInt16LE(1, 20);
        buf.writeUInt16LE(1, 22); buf.writeUInt32LE(8000, 24); buf.writeUInt32LE(16000, 28); buf.writeUInt16LE(2, 32); buf.writeUInt16LE(16, 34);
        buf.write("data", 36); buf.writeUInt32LE(n * 2, 40);
        res.writeHead(200, { "Content-Type": "audio/wav" }); return res.end(buf);
      }
      res.writeHead(200, { "Content-Type": "image/svg+xml" }); return res.end(svgFoto("/comprobante.svg"));
    }
    if (p.match(/^\/conversaciones\/\d+\/(mensajes|reactivar|tomar|notas)$/)) return send({ ok: true });
    if (p === "/pedidos" && req.method === "GET") {
      let items = pedidos;
      if (q.get("estado")) items = items.filter((x) => x.estadoLocal === q.get("estado"));
      return send(paginar(items, q));
    }
    if (p === "/pedidos" && req.method === "POST") return send({ idLocal: 1041 }, 201);
    if ((m = p.match(/^\/pedidos\/(\d+)$/))) return send(pedidoDetalle(m[1]));
    if (p.match(/^\/pedidos\/\d+\/rechazar$/)) return send({ ok: true });
    if (p === "/incidencias/eventos") return send(paginar(eventos, q));
    if (p === "/incidencias/stock") return send(paginar(alertas, q));
    if (p === "/metricas/generales") return send(metricas);
    if (p === "/productos") {
      const term = (q.get("q") || "").toLowerCase();
      const data = catalogo.filter((x) => !term || (x.name + x.sku).toLowerCase().includes(term));
      return send({ data, pagination: { current_page: 1, last_page: 1, per_page: 20, total: data.length } });
    }
    if (p === "/productos/monitoreados") return send(monitoreados);
    if (p === "/catalogos/ubicaciones") return send({ provincias });
    if ((m = p.match(/^\/catalogos\/ubicaciones\/(.+)\/cantones$/))) return send({ cantones: cantones[decodeURIComponent(m[1])] || [] });
    if (p === "/ajustes/negocio") return manejarAjustes(req, res, send);
    if (p === "/parametros" || p.startsWith("/parametros/")) return manejarParametros(req, res, p, q, send);
    if (p === "/instrucciones-victoria" || p.startsWith("/instrucciones-victoria/")) return manejarInstrucciones(req, res, p, send);
    if (p.startsWith("/productos-bot")) return manejarProductosBot(req, res, p, q, send);
    if (p === "/gestion" || p.startsWith("/gestion/")) return manejarGestion(req, res, p, q, send);
    if (p === "/anuncios" || p.startsWith("/anuncios/")) return manejarAnuncios(req, res, p, send);
    if (p === "/leads" || p.startsWith("/leads/") || p.startsWith("/contactos/")) return manejarLeads(req, res, p, q, send);
    if (p.startsWith("/ventas/")) return manejarVentas(req, res, p, send);
    if (p === "/categorias-producto") return manejarCategorias(req, res, p, send);
    // Imita Supabase Storage: las fotos públicas se leen por su enlace; subir y borrar archivos responde que sí.
    if (p.startsWith("/storage/v1/object/public/")) { res.writeHead(200, { "Content-Type": "image/svg+xml", "Cache-Control": "no-store" }); return res.end(svgFoto(p)); }
    if (p.startsWith("/storage/v1/object/")) { req.on("data", () => {}); return req.on("end", () => send(req.method === "DELETE" ? [] : { Key: p.replace("/storage/v1/object/", ""), Id: "mock" })); }
    send({ error: "mock: ruta no implementada " + p }, 404);
  };
  delay ? setTimeout(go, delay) : go();
});
server.listen(PORT, "127.0.0.1", () => console.log("mock escuchando en", PORT));
