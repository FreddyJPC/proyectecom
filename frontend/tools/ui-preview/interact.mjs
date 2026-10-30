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
  await ctx.close();
}
// ---- ESCRITORIO
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
