import { chromium } from "playwright-core";
import fs from "node:fs";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const axeSrc = fs.readFileSync(require.resolve("axe-core/axe.min.js"), "utf8");
const BASE = "http://localhost:3100";
const exe = process.env.CHROMIUM_PATH || undefined;
const rutas = ["/login", "/", "/conversaciones", "/conversaciones/301", "/pedidos", "/pedidos/1040", "/pedidos/nuevo", "/incidencias", "/catalogo", "/catalogo?tab=mis-productos", "/catalogo?tab=monitoreados", "/catalogo/producto/AUD-BT-001", "/catalogo/producto/LMP-LED-220", "/catalogo/producto/CAM-SEG-360", "/metricas", "/parametros"];
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
      const auditar = async (etiqueta) => {
        const res = await page.evaluate(async () => await axe.run(document, { runOnly: ["wcag2a", "wcag2aa", "wcag21aa", "best-practice"], resultTypes: ["violations"] }));
        for (const v of res.violations) {
          // el indicador de desarrollo de Next no es parte del producto
          const nodos = v.nodes.filter((n) => !n.target.join(" ").includes("nextjs-portal"));
          if (!nodos.length) continue;
          const k = `${v.id} [${v.impact}] ${v.help}`;
          const arr = resumen.get(k) ?? [];
          arr.push(`${theme}/${vn} ${etiqueta} (${nodos.length}) ${nodos[0].target.join(" ").slice(0, 90)}`);
          resumen.set(k, arr);
        }
        // Desborde horizontal: nada debe quedar fuera de pantalla (ni la página ni un cuadro abierto).
        const desborde = await page.evaluate(() => {
          const cuadros = [...document.querySelectorAll('[role="dialog"], [role="alertdialog"]')].filter((d) => d.scrollWidth > d.clientWidth + 1);
          return { pagina: document.documentElement.scrollWidth > window.innerWidth + 1, cuadro: cuadros.length > 0 };
        });
        if (desborde.pagina || desborde.cuadro) {
          const k = "desborde-horizontal [serious] Hay contenido fuera de pantalla (scroll horizontal)";
          const arr = resumen.get(k) ?? [];
          arr.push(`${theme}/${vn} ${etiqueta} (${desborde.cuadro ? "cuadro" : "página"})`);
          resumen.set(k, arr);
        }
      };
      await auditar(r);
      // Fase F: alertas nuevas de Incidencias y la insignia de margen en la lista (necesita ajustes confirmados).
      if (r === "/incidencias") {
        await page.getByRole("tab", { name: "Stock y precio" }).click();
        await page.getByText("Se pausó: sin stock").first().waitFor();
        await page.waitForTimeout(300);
        await auditar(r + " [alertas stock y precio]");
      }
      if (r === "/catalogo?tab=mis-productos") {
        await page.getByRole("button", { name: "Ajustes de precios" }).click();
        await page.getByRole("button", { name: "Guardar ajustes" }).click();
        await page.getByRole("button", { name: "Guardar ajustes" }).waitFor({ state: "detached" });
        await page.getByText("Margen en riesgo").first().waitFor();
        await page.waitForTimeout(400);
        await auditar(r + " [margen en riesgo]");
      }
      // Cuadros que solo existen al abrirlos: también se auditan.
      if (r === "/catalogo/producto/LMP-LED-220") {
        await page.getByRole("button", { name: "Ajustes de precios" }).click();
        await page.getByLabel("Costo de envío estimado (USD)").waitFor();
        await page.waitForTimeout(300);
        await auditar(r + " [ajustes abierto]");
        await page.keyboard.press("Escape");

        // Redactar con IA: se audita el paso de las notas y el del borrador.
        await page.getByRole("button", { name: "Redactar con IA" }).click();
        await page.getByLabel("¿A quién va dirigido?").waitFor();
        await page.waitForTimeout(300);
        await auditar(r + " [ia notas]");
        await page.getByRole("button", { name: "Redactar borrador" }).click();
        await page.getByRole("button", { name: "Aceptar", exact: true }).first().waitFor();
        await page.waitForTimeout(300);
        await auditar(r + " [ia borrador]");
        await page.keyboard.press("Escape");

        // Probar con Victoria: se audita el chat vacío, con una conversación y con el pedido simulado.
        await page.getByRole("button", { name: "Abrir la prueba" }).click();
        await page.getByText("Escribe como lo haría un cliente").waitFor();
        await page.waitForTimeout(300);
        await auditar(r + " [prueba vacia]");
        await page.keyboard.press("Escape");
      }
      // Parámetros del sistema: error de validación, confirmación de un cambio sensible y el cuadro de ajustes de precios.
      if (r === "/parametros") {
        const fila = (nombre) => page.locator("li", { has: page.getByRole("heading", { name: nombre, exact: true }) });
        await fila("Memoria de la conversación").getByRole("textbox").fill("5");
        await fila("Memoria de la conversación").getByRole("textbox").blur();
        await page.getByText("Escribe un número entero entre 10 y 100 mensajes.").waitFor();
        await auditar(r + " [error de validacion]");

        await fila("Modelo de IA").getByRole("combobox").click();
        await page.getByRole("option", { name: "Haiku 5.5 (más barato)" }).click();
        await page.waitForTimeout(200);
        await auditar(r + " [modelo elegido]");
        await fila("Modelo de IA").getByRole("button", { name: "Guardar" }).click();
        await page.getByRole("alertdialog").waitFor();
        await page.waitForTimeout(300);
        await auditar(r + " [confirmacion]");
        await page.getByRole("button", { name: "Sí, cambiar" }).click();
        await page.getByRole("alertdialog").waitFor({ state: "detached" });
        await page.getByText("Haiku 5.5 (más barato)").first().waitFor();
        await page.waitForTimeout(400);
        await auditar(r + " [tras guardar]");

        // Restaurar el valor original (deja el servidor falso como estaba para la siguiente pasada).
        await fila("Modelo de IA").getByRole("button", { name: "Restaurar original" }).click();
        await page.getByRole("alertdialog").waitFor();
        await page.waitForTimeout(300);
        await auditar(r + " [confirmacion restaurar]");
        await page.getByRole("button", { name: "Sí, restaurar" }).click();
        await page.getByRole("alertdialog").waitFor({ state: "detached" });
        await fila("Modelo de IA").getByText("Valor original", { exact: true }).first().waitFor();
        await page.waitForTimeout(300);

        await page.getByRole("button", { name: "Abrir ajustes" }).click();
        await page.getByLabel("Costo de envío estimado (USD)").waitFor();
        await page.waitForTimeout(300);
        await auditar(r + " [ajustes de precios]");
        await page.keyboard.press("Escape");
      }
      if (r === "/catalogo/producto/AUD-BT-001") {
        await page.getByRole("button", { name: "Abrir la prueba" }).click();
        await page.getByRole("button", { name: "Quiero comprarlo" }).click();
        await page.getByText("Herramientas que usó").first().waitFor();
        await page.getByText("Herramientas que usó").first().click();
        await page.waitForTimeout(300);
        await auditar(r + " [prueba chat]");
        await page.getByLabel("Mensaje del cliente de prueba").fill("Soy Ana Pérez, vivo en Av. Amazonas 123 y Colón, Quito, Pichincha. Pago contra entrega");
        await page.getByRole("button", { name: "Enviar" }).click();
        await page.getByText("Pedido que se habría enviado a Rocketfy").waitFor();
        await page.waitForTimeout(300);
        await auditar(r + " [prueba pedido]");
        await page.getByRole("button", { name: "Reiniciar prueba" }).click();
        await page.getByRole("button", { name: "Pregunta fuera de la ficha" }).click();
        await page.getByText("Avisos que se habrían enviado a Telegram").waitFor();
        await page.waitForTimeout(300);
        await auditar(r + " [prueba escalada]");
        await page.getByRole("button", { name: "Reiniciar prueba" }).click();
        await page.getByRole("button", { name: "Quiero ver una foto" }).click();
        await page.getByText("Foto enviada: Audífonos Bluetooth Pro").waitFor();
        await page.waitForTimeout(300);
        await auditar(r + " [prueba foto]");
        await page.keyboard.press("Escape");
      }
    }
    await ctx.close();
  }
}
await browser.close();
if (!resumen.size) console.log("SIN VIOLACIONES");
for (const [k, arr] of resumen) { console.log("\n" + k + "  — " + arr.length + " casos"); arr.slice(0, 4).forEach((a) => console.log("   ", a)); }
