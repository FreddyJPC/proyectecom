// Servidor de prueba local: simula Supabase Auth y el backend Flask con datos
// realistas, SOLO para ver y capturar la UI. No toca nada real.
// Ver README.md de esta carpeta.
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
  ["593987654321", "María Fernanda Loor", "fep", "escalada", "Audífonos Bluetooth Pro", true, "cliente", "Mejor prefiero hablar con una persona, ¿pueden llamarme?", 4],
  ["593998877665", "Carlos Andrade", "fep", "esperando_pago", "Reloj Inteligente Serie 7", false, "bot", "Perfecto Carlos, te comparto los datos para la transferencia.", 26],
  ["593961234567", "Lucía Mendoza", "directo", "activa", "Lámpara LED Recargable", false, "bot", "¿Me confirmas tu dirección completa y el cantón?", 41],
  ["593976543210", null, "fep", "activa", null, false, "cliente", "Hola, vi el anuncio, ¿cuánto cuesta?", 55],
  ["593984455667", "Daniela Vera", "web_formulario", "escalada", "Cargador Rápido 33W", true, "cliente", "Mi pedido llegó con el cable roto", 120],
  ["593991122334", "Pedro Villacís", "directo", "cerrada", "Reloj Inteligente Serie 7", false, "bot", "¡Gracias por tu compra, Pedro! Tu pedido va en camino.", 60 * 20],
  ["593958899001", "Andrea Salazar", "fep", "fria", "Audífonos Bluetooth Pro", false, "bot", "Quedo atenta por si deseas continuar con tu pedido.", 60 * 52],
  ["593967788990", "Santiago Caicedo", "fep", "activa", "Lámpara LED Recargable", false, "cliente", "Sí, la quiero en color blanco", 8],
  ["593972233445", "Gabriela Núñez", "directo", "esperando_pago", "Audífonos Bluetooth Pro", false, "cliente", "Ya hice la transferencia, te envío el comprobante", 15],
];
const conversaciones = convs.map((c, i) => ({
  id: 301 - i, telefono: c[0], nombreCliente: c[1], origen: c[2], estado: c[3], productoInteres: c[4], sinRevisar: c[5],
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
  return base.map((m, i) => ({ id: c.id * 100 + i, rol: m[0], contenido: m[1], tipo: "texto", creadoEn: ago(180 - i * 22) }));
};
const convDetalle = (id) => {
  const c = conversaciones.find((x) => String(x.id) === String(id)) || conversaciones[0];
  const cerrada = ["fria", "cerrada"].includes(c.estado);
  return {
    conversacion: {
      id: c.id, telefono: c.telefono, origen: c.origen, estado: c.estado, idAnuncio: c.origen === "fep" ? "120210000123" : null,
      notasInternas: c.estado === "escalada" ? "Cliente pidió llamada. Escribirle primero por aquí." : "",
      ventanaAbierta: !cerrada, ventanaExpiraEn: cerrada ? null : new Date(now + 17 * 3600000).toISOString(), creadaEn: c.creadaEn, actualizadaEn: c.actualizadaEn,
    },
    lead: c.nombreCliente ? {
      nombreCliente: c.nombreCliente, direccion: "Av. 9 de Octubre 1234 y Boyacá", canton: "Guayaquil", provincia: "Guayas",
      productoSku: "AUD-BT-001", productoNombre: c.productoInteres, productoVariante: "Negro", total: "34.90", metodoPago: c.estado === "esperando_pago" ? "transferencia" : "contraentrega",
      estadoPago: null, estado: c.estado === "cerrada" ? "despachado" : "en_proceso", idPedidoLocal: c.estado === "cerrada" ? 1035 : null, idPedidoRocketfy: c.estado === "cerrada" ? 884035 : null,
    } : null,
    mensajes: mensajesDe(c),
  };
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
].map((a, i) => ({ id: 50 - i, sku: a[0], tipo: a[1], detalle: a[2], creadoEn: ago(a[3]) }));

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

// ---------- servidor ----------
function paginar(arr, q) {
  const page = Number(q.get("page") || 1), pageSize = Number(q.get("pageSize") || 20);
  return { items: arr.slice((page - 1) * pageSize, page * pageSize), total: arr.length, page, pageSize };
}
function totalesConv() {
  const esc = conversaciones.filter((c) => c.estado === "escalada");
  return { escaladas: esc.length, escaladasSinRevisar: esc.filter((c) => c.sinRevisar).length, esperandoPago: conversaciones.filter((c) => c.estado === "esperando_pago").length };
}

const server = http.createServer((req, res) => {
  const url = new URL(req.url, `http://${req.headers.host}`);
  const p = url.pathname, q = url.searchParams;
  res.setHeader("Access-Control-Allow-Origin", req.headers.origin || "*");
  res.setHeader("Access-Control-Allow-Headers", req.headers["access-control-request-headers"] || "*");
  res.setHeader("Access-Control-Allow-Methods", "GET,POST,PATCH,DELETE,OPTIONS");
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
      if (q.get("q")) items = items.filter((c) => (c.telefono + (c.nombreCliente || "")).toLowerCase().includes(q.get("q").toLowerCase()));
      return send({ ...paginar(items, q), totalesPorFiltroRapido: totalesConv() });
    }
    let m;
    if ((m = p.match(/^\/conversaciones\/(\d+)$/))) return send(convDetalle(m[1]));
    if (p.match(/^\/conversaciones\/\d+\/(mensajes|reactivar|notas)$/)) return send({ ok: true });
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
    send({ error: "mock: ruta no implementada " + p }, 404);
  };
  delay ? setTimeout(go, delay) : go();
});
server.listen(PORT, "127.0.0.1", () => console.log("mock escuchando en", PORT));
