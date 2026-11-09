// Capturas de las interacciones de Leads (detalle, cambiar temperatura, «no contactar», filtros) en móvil y escritorio.
// Uso (con el servidor falso y la app corriendo, ver README.md):  node interact-leads.mjs   (OUT=carpeta, THEME=dark)
import { chromium } from "playwright-core";
import fs from "node:fs";

const BASE = process.env.BASE || "http://localhost:3100";
const OUT = process.env.OUT || "shots";
const THEME = process.env.THEME || "light";
fs.mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined, args: ["--no-sandbox"] });
const hide = (p) => p.addStyleTag({ content: "nextjs-portal{display:none!important}" });
const shot = async (page, name) => {
  await hide(page);
  await page.waitForTimeout(450);
  await page.screenshot({ path: `${OUT}/${name}.png` });
  console.log("ok", name);
};

async function sesion(vp, mobile) {
  const ctx = await browser.newContext({ viewport: vp, deviceScaleFactor: mobile ? 2 : 1, colorScheme: THEME, locale: "es-EC", isMobile: mobile, hasTouch: mobile });
  const page = await ctx.newPage();
  page.on("pageerror", (e) => console.log("[pageerror]", e.message.slice(0, 160)));
  await page.goto(BASE + "/login", { waitUntil: "networkidle" });
  await page.fill("#email", "a@b.c");
  await page.fill("#password", "x");
  await Promise.all([page.waitForURL((u) => !u.pathname.startsWith("/login")), page.click("button[type=submit]")]);
  return { ctx, page };
}

// ---- ESCRITORIO
{
  const { ctx, page } = await sesion({ width: 1440, height: 900 }, false);
  await page.goto(BASE + "/leads", { waitUntil: "networkidle" });
  await shot(page, "l-d-lista");

  await page.getByRole("button", { name: "Filtros" }).click();
  await shot(page, "l-d-filtros");
  await page.keyboard.press("Escape");

  await page.getByRole("button", { name: "Perdidos" }).click();
  await page.waitForTimeout(500);
  await shot(page, "l-d-perdidos");

  // Un lead al que el sistema ya le escribió (empujón y plantilla): se ve en su línea de tiempo.
  await page.getByRole("button", { name: "Todos", exact: true }).click();
  await page.getByPlaceholder("Buscar cliente o producto").fill("Daniela");
  await page.getByRole("button", { name: "Daniela Vera" }).first().click();
  await page.getByText("Se le envió la plantilla").waitFor();
  await shot(page, "l-d-seguimientos");
  await page.keyboard.press("Escape");
  await page.getByPlaceholder("Buscar cliente o producto").fill("");
  await page.getByRole("button", { name: "Abiertos" }).click();
  await page.getByRole("button", { name: "María Fernanda Loor" }).click();
  await page.getByText("Cómo ha cambiado").waitFor();
  await shot(page, "l-d-detalle");

  await page.getByRole("button", { name: "Cambiar temperatura" }).click();
  await page.getByRole("radio", { name: /Perdido/ }).check();
  await shot(page, "l-d-cambiar");
  await page.getByRole("button", { name: "Guardar" }).click();
  await page.getByText("Lead marcado como perdido.").waitFor();
  await shot(page, "l-d-cambiado");

  await page.getByRole("switch", { name: /No contactar/ }).click();
  await shot(page, "l-d-no-contactar");
  await ctx.close();
}

// ---- MÓVIL
{
  const { ctx, page } = await sesion({ width: 390, height: 844 }, true);
  await page.goto(BASE + "/leads", { waitUntil: "networkidle" });
  await shot(page, "l-m-lista");
  await page.getByRole("button", { name: "Filtros" }).click();
  await shot(page, "l-m-filtros");
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: /Carlos Andrade/ }).click();
  await page.getByText("Cómo ha cambiado").waitFor();
  await shot(page, "l-m-detalle");
  await page.getByRole("button", { name: "Cambiar temperatura" }).click();
  await shot(page, "l-m-cambiar");
  await ctx.close();
}

// ---- PROBAR CON VICTORIA: cliente recurrente y la temperatura que Victoria le pone al cliente
{
  const { ctx, page } = await sesion({ width: 390, height: 844 }, true);
  await page.goto(BASE + "/catalogo/producto/AUD-BT-001", { waitUntil: "networkidle" });
  await page.getByRole("button", { name: "Abrir la prueba" }).click();
  await page.getByRole("checkbox", { name: /ya nos compró antes/ }).click();
  await page.getByRole("button", { name: "Quiero comprarlo" }).click();
  await page.getByText("Herramientas que usó").first().waitFor();
  await page.getByText("Herramientas que usó").first().click();
  await page.getByText("Clasificó al cliente (temperatura)").first().scrollIntoViewIfNeeded();
  await shot(page, "l-m-prueba");
  await ctx.close();
}
await browser.close();
