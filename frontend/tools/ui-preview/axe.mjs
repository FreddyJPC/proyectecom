import { chromium } from "playwright-core";
import fs from "node:fs";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const axeSrc = fs.readFileSync(require.resolve("axe-core/axe.min.js"), "utf8");
const BASE = "http://localhost:3100";
const exe = process.env.CHROMIUM_PATH || undefined;
const rutas = ["/login", "/", "/conversaciones", "/conversaciones/301", "/pedidos", "/pedidos/1040", "/pedidos/nuevo", "/incidencias", "/catalogo", "/metricas"];
const browser = await chromium.launch({ executablePath: exe, args: ["--no-sandbox"] });
const resumen = new Map();
for (const theme of ["light", "dark"]) {
  for (const [vn, vp] of [["desktop", { width: 1440, height: 900 }], ["movil", { width: 390, height: 844 }]]) {
    const ctx = await browser.newContext({ viewport: vp, colorScheme: theme, locale: "es-EC" });
    const page = await ctx.newPage();
    await page.goto(BASE + "/login", { waitUntil: "networkidle" });
    // login
    if (theme === "light" && vn === "desktop") {}
    await page.fill("#email", "a@b.c"); await page.fill("#password", "x");
    await Promise.all([page.waitForURL((u) => !u.pathname.startsWith("/login")), page.click("button[type=submit]")]);
    for (const r of rutas) {
      if (r === "/login") continue;
      await page.goto(BASE + r, { waitUntil: "networkidle" });
      await page.waitForTimeout(500);
      await page.evaluate(axeSrc);
      const res = await page.evaluate(async () => await axe.run(document, { runOnly: ["wcag2a", "wcag2aa", "wcag21aa", "best-practice"], resultTypes: ["violations"] }));
      for (const v of res.violations) {
        // el indicador de desarrollo de Next no es parte del producto
        const nodos = v.nodes.filter((n) => !n.target.join(" ").includes("nextjs-portal"));
        if (!nodos.length) continue;
        const k = `${v.id} [${v.impact}] ${v.help}`;
        const arr = resumen.get(k) ?? [];
        arr.push(`${theme}/${vn} ${r} (${nodos.length}) ${nodos[0].target.join(" ").slice(0, 90)}`);
        resumen.set(k, arr);
      }
    }
    await ctx.close();
  }
}
await browser.close();
if (!resumen.size) console.log("SIN VIOLACIONES");
for (const [k, arr] of resumen) { console.log("\n" + k + "  — " + arr.length + " casos"); arr.slice(0, 4).forEach((a) => console.log("   ", a)); }
