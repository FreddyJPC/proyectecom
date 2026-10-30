import { chromium } from "playwright-core";
import fs from "node:fs";
const BASE = process.env.BASE || "http://localhost:3100";
const OUT = process.env.OUT || "shots";
const ONLY = (process.env.ONLY || "").split(",").filter(Boolean);
const THEME = process.env.THEME || "light";
fs.mkdirSync(OUT, { recursive: true });
const exe = process.env.CHROMIUM_PATH || undefined;
const rutas = [
  ["login", "/login", false],
  ["resumen", "/", true],
  ["conversaciones", "/conversaciones", true],
  ["conversacion-detalle", "/conversaciones/301", true],
  ["pedidos", "/pedidos", true],
  ["pedido-detalle", "/pedidos/1040", true],
  ["pedido-nuevo", "/pedidos/nuevo", true],
  ["incidencias", "/incidencias", true],
  ["catalogo", "/catalogo", true],
  ["metricas", "/metricas", true],
];
const vistas = [["desktop", { width: 1440, height: 900 }], ["movil", { width: 390, height: 844 }]];
const browser = await chromium.launch({ executablePath: exe, args: ["--no-sandbox"] });
for (const [vn, vp] of vistas) {
  const ctx = await browser.newContext({ viewport: vp, deviceScaleFactor: vn === "movil" ? 2 : 1, colorScheme: THEME, locale: "es-EC", isMobile: vn === "movil", hasTouch: vn === "movil" });
  const page = await ctx.newPage();
  page.on("pageerror", (e) => console.log("[pageerror]", vn, e.message.slice(0, 200)));
  page.on("console", (m) => { if (m.type() === "error") console.log("[console.error]", vn, m.text().slice(0, 200)); });
  await page.goto(BASE + "/login", { waitUntil: "networkidle" });
  if (!ONLY.length || ONLY.includes("login")) {
    await page.addStyleTag({ content: "nextjs-portal{display:none!important}" });
    await page.screenshot({ path: `${OUT}/login-${vn}.png`, fullPage: true });
  }
  await page.fill("#email", "freddy@azoshop.ec"); await page.fill("#password", "x");
  await Promise.all([page.waitForURL((u) => !u.pathname.startsWith("/login"), { timeout: 20000 }), page.click("button[type=submit]")]);
  for (const [name, path, auth] of rutas) {
    if (!auth) continue;
    if (ONLY.length && !ONLY.includes(name)) continue;
    await page.goto(BASE + path, { waitUntil: "networkidle" });
    await page.addStyleTag({ content: "nextjs-portal{display:none!important}" });
    await page.waitForTimeout(700);
    await page.screenshot({ path: `${OUT}/${name}-${vn}.png`, fullPage: process.env.FULL !== "0" });
    console.log("ok", vn, name);
  }
  await ctx.close();
}
await browser.close();
