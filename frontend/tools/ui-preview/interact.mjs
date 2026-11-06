import { chromium } from "playwright-core";
import fs from "node:fs";
const BASE = "http://localhost:3100";
const OUT = process.env.OUT || "shots"; fs.mkdirSync(OUT, { recursive: true });
const exe = process.env.CHROMIUM_PATH || undefined;
const browser = await chromium.launch({ executablePath: exe, args: ["--no-sandbox"] });
const hide = (p) => p.addStyleTag({ content: "nextjs-portal{display:none!important}" });

async function sesion(vp, mobile) {
  const ctx = await browser.newContext({ viewport: vp, deviceScaleFactor: mobile ? 2 : 1, locale: "es-EC", isMobile: mobile, hasTouch: mobile });
  const page = await ctx.newPage();
  page.on("pageerror", (e) => console.log("[pageerror]", e.message.slice(0, 160)));
  await page.goto(BASE + "/login", { waitUntil: "networkidle" });
  await page.fill("#email", "a@b.c"); await page.fill("#password", "x");
  await Promise.all([page.waitForURL((u) => !u.pathname.startsWith("/login")), page.click("button[type=submit]")]);
  return { ctx, page };
}
const shot = async (page, name) => { await hide(page); await page.waitForTimeout(500); await page.screenshot({ path: `${OUT}/${name}.png` }); console.log("ok", name); };

// ---- MÓVIL
{
  const { ctx, page } = await sesion({ width: 390, height: 844 }, true);
  await page.goto(BASE + "/", { waitUntil: "networkidle" });
  await page.getByRole("button", { name: "Más" }).click();
  await shot(page, "m-menu-mas");
  await page.keyboard.press("Escape");

  await page.goto(BASE + "/conversaciones/301", { waitUntil: "networkidle" });
  await page.getByRole("button", { name: "Ver datos del cliente" }).click();
  await shot(page, "m-panel-datos");
  await page.keyboard.press("Escape");

  await page.goto(BASE + "/pedidos/1040", { waitUntil: "networkidle" });
  await page.getByRole("button", { name: /Modificar/ }).click();
  await shot(page, "m-dialog-modificar");
  await page.keyboard.press("Escape");

  // estado de error simulado
  await page.route("**/pedidos?*", (r) => r.abort());
  await page.goto(BASE + "/pedidos", { waitUntil: "networkidle" });
  await shot(page, "m-error-pedidos");
  await page.unroute("**/pedidos?*");

  // estado vacío simulado
  await page.route("**/pedidos?*", (r) => r.fulfill({ json: { items: [], total: 0, page: 1, pageSize: 20 } }));
  await page.goto(BASE + "/pedidos", { waitUntil: "networkidle" });
  await shot(page, "m-vacio-pedidos");

  // ---- Mis productos (Fase B): publicar bloqueado, editar con barra de guardado
  await page.goto(BASE + "/catalogo?tab=mis-productos", { waitUntil: "networkidle" });
  const filaBorrador = page.getByRole("listitem").filter({ hasText: "Lámpara LED Recargable" });
  await filaBorrador.getByRole("button", { name: "Publicar" }).click();
  await shot(page, "m-productos-publicar-confirmar");
  await page.getByRole("button", { name: "Sí, publicar" }).click();
  await page.getByRole("alert").waitFor();
  await shot(page, "m-productos-publicar-bloqueado");
  await page.keyboard.press("Escape");

  await page.goto(BASE + "/catalogo/producto/AUD-BT-001", { waitUntil: "networkidle" });
  await page.getByLabel("Precio de venta (USD)").fill("8");
  await page.getByLabel("Tiempo de entrega").fill("");
  await shot(page, "m-ficha-editando");

  // ---- Calculadora de precio (Fase C)
  await page.goto(BASE + "/catalogo/producto/CRG-RAP-33", { waitUntil: "networkidle" });
  await page.getByText("Precios recomendados").scrollIntoViewIfNeeded();
  await shot(page, "m-ficha-precio");
  await page.getByRole("button", { name: "Revisar mis ajustes" }).click();
  await shot(page, "m-ajustes-dialog");
  await page.keyboard.press("Escape");

  // ---- Redactar con IA (Fase D) a 390 px
  await page.goto(BASE + "/catalogo/producto/LMP-LED-220", { waitUntil: "networkidle" });
  await page.getByRole("button", { name: "Redactar con IA" }).click();
  await page.getByLabel("¿Qué quieres destacar?").fill("batería larga");
  await shot(page, "m-ia-notas");
  await page.getByRole("button", { name: "Redactar borrador" }).click();
  await page.getByRole("button", { name: "Aceptar", exact: true }).first().waitFor();
  await shot(page, "m-ia-borrador");
  await page.keyboard.press("Escape");

  // ---- Probar con Victoria (Fase E) a 390 px
  await page.goto(BASE + "/catalogo/producto/AUD-BT-001", { waitUntil: "networkidle" });
  await page.getByRole("button", { name: "Abrir la prueba" }).click();
  await page.getByRole("button", { name: "Quiero comprarlo" }).click();
  await page.getByText("Herramientas que usó").first().waitFor();
  await shot(page, "m-prueba-chat");
  await page.getByLabel("Mensaje del cliente de prueba").fill("Soy Ana Pérez, vivo en Av. Amazonas 123 y Colón, Quito, Pichincha. Pago contra entrega");
  await page.getByRole("button", { name: "Enviar" }).click();
  await page.getByText("Pedido que se habría enviado a Rocketfy").waitFor();
  await page.getByText("Pedido que se habría enviado a Rocketfy").scrollIntoViewIfNeeded();
  await shot(page, "m-prueba-pedido");
  await ctx.close();
}
{
  const { ctx, page } = await sesion({ width: 1440, height: 900 }, false);
  await page.goto(BASE + "/pedidos/nuevo?nombreCliente=Mar%C3%ADa%20Loor&telefono=593987654321&direccion=Av.%209%20de%20Octubre&provincia=Guayas&canton=Guayaquil&productoSku=AUD-BT-001&productoNombre=Aud%C3%ADfonos%20Bluetooth%20Pro&total=8", { waitUntil: "networkidle" });
  await shot(page, "d-nuevo-prefill-aviso");
  await page.getByRole("button", { name: /Agregar/ }).first().click();
  await shot(page, "d-nuevo-agregar-producto");
  await page.keyboard.press("Escape");

  await page.goto(BASE + "/catalogo", { waitUntil: "networkidle" });
  await page.getByRole("button", { name: /Vigilar$/ }).first().click();
  await shot(page, "d-catalogo-vigilar");
  await page.keyboard.press("Escape");
  await page.getByRole("tab", { name: /Vigilados/ }).click();
  await shot(page, "d-catalogo-vigilados");

  await page.goto(BASE + "/incidencias", { waitUntil: "networkidle" });
  await page.getByRole("tab", { name: "Stock y precio" }).click();
  await shot(page, "d-incidencias-stock");

  // chat: enviar mensaje (optimista) + hover tema
  await page.goto(BASE + "/conversaciones/301", { waitUntil: "networkidle" });
  await page.getByLabel("Escribe una respuesta").fill("Hola María, soy Freddy. Te llamo ahora mismo.");
  await page.keyboard.press("Enter");
  await shot(page, "d-chat-enviado");

  // ---- Mis productos (Fase B): crear desde el catálogo, guardar, publicar y pausar
  await page.goto(BASE + "/catalogo", { waitUntil: "networkidle" });
  await page.getByRole("button", { name: "Preparar para vender" }).first().click();
  await page.waitForURL(/\/catalogo\/producto\//);
  await page.getByRole("heading", { level: 1 }).waitFor();
  await shot(page, "d-ficha-recien-creada");

  await page.goto(BASE + "/catalogo/producto/LMP-LED-220", { waitUntil: "networkidle" });
  await page.getByLabel("Tiempo de entrega").fill("2 a 4 días hábiles");
  await page.getByLabel("Precio de venta (USD)").fill("9.50");
  await shot(page, "d-ficha-editando-precio-bajo");
  await page.getByLabel("Precio de venta (USD)").fill("24.99");
  await page.getByRole("button", { name: "Guardar cambios" }).click();
  await page.getByRole("button", { name: "Guardar cambios" }).waitFor({ state: "detached" });
  await shot(page, "d-ficha-guardada");
  await page.getByRole("button", { name: "Publicar" }).click();
  await shot(page, "d-ficha-publicar-confirmar");
  await page.getByRole("button", { name: "Sí, publicar" }).click();
  await page.getByText("A la venta").first().waitFor();
  await shot(page, "d-ficha-publicada");
  await page.getByRole("button", { name: "Pausar" }).click();
  await page.getByRole("button", { name: "Sí, pausar" }).click();
  await page.getByText("Pausado").first().waitFor();
  await shot(page, "d-ficha-pausada");

  await page.goto(BASE + "/catalogo/producto/NO-EXISTE", { waitUntil: "networkidle" });
  await shot(page, "d-ficha-no-existe");

  // ---- Calculadora de precio (Fase C): ajustes de partida -> confirmar -> recomendado
  await page.goto(BASE + "/catalogo/producto/CRG-RAP-33", { waitUntil: "networkidle" });
  await page.getByText("Precios recomendados").waitFor();
  await shot(page, "d-precio-partida");
  await page.getByRole("button", { name: "Revisar mis ajustes" }).click();
  await shot(page, "d-ajustes-partida");
  await page.getByLabel("Margen objetivo (%)").fill("20");
  await shot(page, "d-ajustes-error");
  await page.getByLabel("Margen objetivo (%)").fill("35");
  await page.getByRole("button", { name: /^Usar \$8\.47/ }).click();
  await page.getByRole("button", { name: "Guardar ajustes" }).click();
  await page.getByText("Estos cálculos usan valores de partida").waitFor({ state: "detached" });
  await page.getByLabel("Precio de venta (USD)").fill("10");
  await page.getByText("pierdes").first().waitFor();
  await shot(page, "d-precio-pierde");
  await page.getByRole("button", { name: /Recomendado/ }).click();
  await page.getByLabel("Precio de la competencia (USD)").fill("9");
  await page.getByText("competencia que anotaste").waitFor();
  await shot(page, "d-precio-recomendado-competencia");

  // ---- Redactar con IA (Fase D): notas -> borrador -> aceptar -> guardar -> historial
  await page.goto(BASE + "/catalogo/producto/LMP-LED-220", { waitUntil: "networkidle" });
  await page.getByRole("button", { name: "Redactar con IA" }).click();
  await page.getByLabel("¿Qué quieres destacar?").fill("batería larga");
  await shot(page, "d-ia-notas");
  await page.getByRole("button", { name: "Redactar borrador" }).click();
  await page.getByRole("button", { name: "Aceptar", exact: true }).first().waitFor();
  await shot(page, "d-ia-borrador");
  await page.getByRole("button", { name: "Aceptar", exact: true }).nth(1).click(); // la descripción
  await page.getByText("Aplicado a la ficha").first().waitFor();
  await shot(page, "d-ia-aplicado");
  await page.getByRole("button", { name: "Regenerar" }).nth(1).click();
  await page.getByRole("button", { name: "Regenerar" }).nth(1).waitFor();
  await page.getByRole("button", { name: "Aceptar todo" }).click();
  await page.getByRole("button", { name: "Listo" }).click();
  await page.getByRole("button", { name: "Guardar cambios" }).waitFor();
  await shot(page, "d-ia-ficha-con-cambios");
  await page.getByRole("button", { name: "Guardar cambios" }).click();
  await page.getByRole("button", { name: "Guardar cambios" }).waitFor({ state: "detached" });
  await page.waitForTimeout(400);
  await page.getByText("Borrador redactado con IA").first().scrollIntoViewIfNeeded();
  await shot(page, "d-ia-historial");

  // La IA no está disponible: el mensaje sale dentro del cuadro y no se pierde nada
  await page.getByRole("button", { name: "Redactar con IA" }).click();
  await page.getByLabel("Otros datos que sepas del producto").fill("SIN_IA");
  await page.getByRole("button", { name: "Redactar borrador" }).click();
  await page.getByText("no está configurada en el servidor").waitFor();
  await shot(page, "d-ia-error");
  await page.keyboard.press("Escape");

  // Tope diario: se baja a 1 en Ajustes de precios y el cuadro de IA lo respeta
  await page.getByRole("button", { name: "Ajustes de precios" }).click();
  await page.getByLabel("Borradores de IA por día").fill("1");
  await page.getByRole("button", { name: "Guardar ajustes" }).click();
  await page.getByLabel("Borradores de IA por día").waitFor({ state: "detached" });
  await page.getByRole("button", { name: "Redactar con IA" }).click();
  await page.getByText("Llegaste al tope de hoy").waitFor();
  await shot(page, "d-ia-tope");
  await page.keyboard.press("Escape");

  // ---- Probar con Victoria (Fase E): faltan datos -> lista de verificación -> chat -> compra completa -> escalar -> tope
  await page.goto(BASE + "/catalogo", { waitUntil: "networkidle" });
  await page.getByRole("button", { name: "Preparar para vender" }).first().click();
  await page.waitForURL(/\/catalogo\/producto\//);
  const fichaNueva = page.url();
  await page.getByRole("heading", { level: 1 }).waitFor();
  await shot(page, "d-ficha-con-prueba");
  await page.getByRole("button", { name: "Abrir la prueba" }).click();
  await page.getByText("Escribe como lo haría un cliente").waitFor();
  await shot(page, "d-prueba-vacia");
  await page.getByRole("button", { name: "Quiero comprarlo" }).click();
  await page.getByText("Antes de probar, completa esto en la ficha").waitFor();
  await shot(page, "d-prueba-faltan");
  await page.keyboard.press("Escape");
  await page.locator("#tiempoEntrega").fill("2 a 4 días hábiles");
  await page.getByRole("button", { name: "Guardar cambios" }).click();
  await page.getByRole("button", { name: "Guardar cambios" }).waitFor({ state: "detached" });

  // Lista de verificación al publicar: todavía no se probó una compra completa
  await page.getByRole("button", { name: "Publicar" }).click();
  const dialogo = page.getByRole("alertdialog");
  await dialogo.getByText("Ten en cuenta antes de confirmar").waitFor();
  await dialogo.getByText("Todavía no probaste una compra completa con Victoria").waitFor();
  await shot(page, "d-publicar-lista");
  await page.keyboard.press("Escape");

  await page.getByRole("button", { name: "Abrir la prueba" }).click();
  await page.getByRole("button", { name: "Quiero comprarlo" }).click();
  await page.getByText("Herramientas que usó").first().waitFor();
  await page.getByText("Herramientas que usó").first().click();
  await shot(page, "d-prueba-chat");
  await page.getByLabel("Mensaje del cliente de prueba").fill("Soy Ana Pérez, vivo en Av. Amazonas 123 y Colón, Quito, Pichincha. Pago contra entrega");
  await page.getByRole("button", { name: "Enviar" }).click();
  await page.getByText("Pedido que se habría enviado a Rocketfy").waitFor();
  await page.getByText("La compra se cerró").waitFor();
  await shot(page, "d-prueba-pedido");

  await page.getByRole("button", { name: "Reiniciar prueba" }).click();
  await page.getByRole("button", { name: "Pregunta fuera de la ficha" }).click();
  await page.getByText("Victoria pasó la conversación a una persona").waitFor();
  await page.getByText("Avisos que se habrían enviado a Telegram").waitFor();
  await shot(page, "d-prueba-escalada");

  await page.getByRole("button", { name: "Reiniciar prueba" }).click();
  await page.getByRole("button", { name: "Quiero 2 unidades" }).click();
  await page.getByText("puedes pedir hasta 1 por pedido").waitFor();
  await page.getByText("Herramientas que usó").first().click();
  await shot(page, "d-prueba-dos-unidades");
  await page.getByRole("button", { name: "Cerrar", exact: true }).click();

  // Con la compra de prueba hecha, el aviso desaparece de la lista de verificación
  await page.goto(fichaNueva, { waitUntil: "networkidle" });
  await page.getByRole("button", { name: "Publicar" }).click();
  await page.getByRole("alertdialog").getByText("Ten en cuenta antes de confirmar").waitFor();
  if (await page.getByText("Todavía no probaste una compra completa").count()) throw new Error("el aviso de la compra de prueba debía desaparecer");
  await shot(page, "d-publicar-lista-despues");
  await page.keyboard.press("Escape");

  // Tope de pruebas: se baja a 1 en Ajustes de precios y el cuadro de la prueba lo respeta
  await page.getByRole("button", { name: "Ajustes de precios" }).click();
  await page.getByLabel("Mensajes de prueba con Victoria por día").fill("1");
  await page.getByRole("button", { name: "Guardar ajustes" }).click();
  await page.getByLabel("Mensajes de prueba con Victoria por día").waitFor({ state: "detached" });
  await page.getByRole("button", { name: /la prueba$/ }).click();
  await page.getByText("Llegaste al tope de hoy (1 mensajes de prueba)").waitFor();
  await shot(page, "d-prueba-tope");
  await page.keyboard.press("Escape");

  // Mis productos: el botón de ajustes también está en la lista
  await page.goto(BASE + "/catalogo?tab=mis-productos", { waitUntil: "networkidle" });
  await shot(page, "d-mis-productos-ajustes");
  await ctx.close();
}
// ---- TABLET
{
  const { ctx, page } = await sesion({ width: 820, height: 1180 }, false);
  for (const [n, r] of [["resumen", "/"], ["conversaciones", "/conversaciones"], ["pedidos", "/pedidos"], ["conversacion", "/conversaciones/301"]]) {
    await page.goto(BASE + r, { waitUntil: "networkidle" });
    await shot(page, `t-${n}`);
  }
  await ctx.close();
}
await browser.close();
