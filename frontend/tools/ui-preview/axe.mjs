import { chromium } from "playwright-core";
import fs from "node:fs";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const axeSrc = fs.readFileSync(require.resolve("axe-core/axe.min.js"), "utf8");
const BASE = "http://localhost:3100";
const exe = process.env.CHROMIUM_PATH || undefined;
const SOLO = (process.env.ONLY || "").split(",").filter(Boolean);
const rutas = ["/login", "/", "/conversaciones", "/conversaciones/301", "/pedidos", "/pedidos/1040", "/pedidos/nuevo", "/incidencias", "/catalogo", "/catalogo?tab=mis-productos", "/catalogo?tab=monitoreados", "/catalogo/producto/AUD-BT-001", "/catalogo/producto/LMP-LED-220", "/catalogo/producto/CAM-SEG-360", "/catalogo/producto/PROP-0001", "/catalogo/producto/PROP-0002", "/catalogo/propio/nuevo", "/gestion", "/anuncios", "/metricas", "/parametros", "/parametros/instrucciones"];
const browser = await chromium.launch({ executablePath: exe, args: ["--no-sandbox"] });
const resumen = new Map();
const SIN_INFOS = process.env.SIN_INFOS === "1"; // SIN_INFOS=1 salta los cuadros ⓘ (más rápido)
let infosAuditados = 0;
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
      if (SOLO.length && !SOLO.some((x) => r.startsWith(x))) continue; // ONLY=/gestion,/catalogo/propio para auditar solo algunas rutas
      await page.goto(BASE + r, { waitUntil: "networkidle" });
      await page.waitForTimeout(500);
      await page.evaluate(axeSrc);
      const auditar = async (etiqueta) => {
        // Con un cuadro abierto, el resto de la página queda inerte detrás del velo y el desenfoque: axe lo mediría
        // mezclado con lo que casualmente haya debajo (p. ej. la barra inferior sobre un botón). Ese contraste ya se
        // audita en el estado normal de la página; aquí se mide el cuadro.
        const res = await page.evaluate(async () => {
          const cuadros = document.querySelectorAll('[role="dialog"], [role="alertdialog"]');
          const cuadro = cuadros.length ? cuadros[cuadros.length - 1] : null; // el de más arriba (un ⓘ puede abrirse sobre otro cuadro)
          return await axe.run(cuadro ?? document, { runOnly: ["wcag2a", "wcag2aa", "wcag21aa", "best-practice"], resultTypes: ["violations"] });
        });
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
      // Botones ⓘ (InfoButton): se abre cada uno de la pantalla y se audita su cuadro. `dentro` limita la búsqueda a un cuadro abierto.
      const auditarInfos = async (etiqueta, dentro) => {
        const alcance = dentro ? page.locator('[role="dialog"]').last() : page;
        const infos = alcance.locator('[aria-label^="Más información"]');
        const total = Math.min(await infos.count(), 30);
        for (let i = 0; i < total; i++) {
          const boton = infos.nth(i);
          if (!(await boton.isVisible())) continue;
          const nombre = await boton.getAttribute("aria-label");
          await boton.scrollIntoViewIfNeeded();
          await boton.click();
          await page.getByRole("dialog").last().getByRole("button", { name: "Entendido" }).waitFor();
          await page.waitForTimeout(250);
          await auditar(`${etiqueta} [${nombre}]`);
          await page.keyboard.press("Escape");
          await page.getByRole("button", { name: "Entendido" }).waitFor({ state: "detached" });
          await page.waitForTimeout(150);
        }
        return total;
      };
      if (!SIN_INFOS) {
        const abiertos = await auditarInfos(r, false);
        infosAuditados += abiertos;
      }
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
        if (!SIN_INFOS) infosAuditados += await auditarInfos(r + " [ajustes abierto]", true);
        await page.keyboard.press("Escape");

        // Redactar con IA: se audita el paso de las notas y el del borrador.
        await page.getByRole("button", { name: "Redactar con IA" }).click();
        await page.getByLabel("¿A quién va dirigido?").waitFor();
        await page.waitForTimeout(300);
        await auditar(r + " [ia notas]");
        if (!SIN_INFOS) infosAuditados += await auditarInfos(r + " [ia notas]", true);
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
        if (!SIN_INFOS) infosAuditados += await auditarInfos(r + " [prueba vacia]", true);
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
        if (!SIN_INFOS) infosAuditados += await auditarInfos(r + " [ajustes de precios]", true);
        await page.keyboard.press("Escape");
      }
      // Instrucciones de Victoria: error de sección, borrador guardado, prueba del borrador, publicar y volver a las originales.
      if (r === "/parametros/instrucciones") {
        await page.getByRole("heading", { name: "Qué usa Victoria hoy" }).waitFor();
        await page.getByRole("textbox", { name: "Personalidad y tono" }).fill("Hablas como una persona de la costa: cercana, breve y con calidez.");
        await page.getByRole("textbox", { name: "Reglas que nunca rompe" }).fill("");
        await page.getByText("No puede quedar vacía.").waitFor();
        await auditar(r + " [error de seccion]");

        await page.getByRole("button", { name: "Poner el texto original de esta sección" }).last().click();
        await page.getByRole("button", { name: "Guardar borrador" }).click();
        await page.getByRole("button", { name: "Descartar borrador" }).waitFor();
        await page.waitForTimeout(500);
        await auditar(r + " [borrador guardado]");

        await page.getByRole("button", { name: "Abrir la prueba" }).click();
        await page.getByText("Escribe como lo haría un cliente").waitFor();
        await page.waitForTimeout(300);
        await auditar(r + " [prueba del borrador]");
        if (!SIN_INFOS) infosAuditados += await auditarInfos(r + " [prueba del borrador]", true);
        await page.keyboard.press("Escape");

        await page.getByRole("button", { name: "Publicar", exact: true }).click();
        await page.getByRole("alertdialog").waitFor();
        await page.waitForTimeout(300);
        await auditar(r + " [confirmar publicar]");
        await page.getByRole("button", { name: "Sí, publicar" }).click();
        await page.getByRole("alertdialog").waitFor({ state: "detached" });
        await page.getByText("Versión publicada").first().waitFor();
        await page.waitForTimeout(400);
        await auditar(r + " [publicada]");

        // Deja el servidor falso como estaba para la siguiente pasada.
        await page.getByRole("button", { name: "Volver a las originales" }).click();
        await page.getByRole("alertdialog").waitFor();
        await page.waitForTimeout(300); // que termine la animación del cuadro antes de medir contraste
        await auditar(r + " [confirmar volver a la original]");
        await page.getByRole("button", { name: "Sí, volver a las originales" }).click();
        await page.getByRole("alertdialog").waitFor({ state: "detached" });
        await page.getByText("Instrucciones originales").first().waitFor();
        await page.waitForTimeout(300);
      }
      // Anuncios: vincular un anuncio nuevo, cambiar el producto de uno vinculado (pide confirmar) y quitar un vínculo.
      if (r === "/anuncios") {
        await page.getByText("Audífonos Bluetooth Pro · 30 h de batería").first().waitFor();
        await page.getByRole("button", { name: "Vincular un anuncio" }).click();
        await page.getByRole("dialog").waitFor();
        await page.waitForTimeout(300);
        await auditar(r + " [vincular uno nuevo]");
        await page.keyboard.press("Escape");

        await page.getByRole("button", { name: "Vincular con un producto" }).first().click();
        await page.getByRole("dialog").waitFor();
        await page.waitForTimeout(300);
        await auditar(r + " [vincular uno de la lista]");
        await page.keyboard.press("Escape");

        // Cambiar el producto de un anuncio ya vinculado: el servidor pide confirmar. Se audita el aviso y se cancela (no cambia datos).
        await page.getByRole("button", { name: "Cambiar producto" }).first().click();
        await page.getByRole("dialog").waitFor();
        await page.getByRole("combobox", { name: "Producto" }).click();
        await page.getByRole("option", { name: /Cargador|Lámpara|Reloj|Camiseta/ }).first().click();
        await page.getByRole("button", { name: "Vincular", exact: true }).click();
        await page.getByText("Sí, cambiar el producto").waitFor();
        await page.waitForTimeout(300);
        await auditar(r + " [confirmar cambio de producto]");
        await page.keyboard.press("Escape");

        await page.getByRole("button", { name: "Quitar vínculo" }).first().click();
        await page.getByRole("alertdialog").waitFor();
        await page.waitForTimeout(300);
        await auditar(r + " [quitar vinculo]");
        await page.keyboard.press("Escape");
      }
      // ADR-012: «Por gestionar», atender una solicitud (cuadro con nota) y la lista de atendidas.
      if (r === "/gestion") {
        await page.getByRole("button", { name: "Marcar como atendida" }).first().click();
        await page.getByRole("dialog").waitFor();
        await page.waitForTimeout(300);
        await auditar(r + " [atender]");
        await page.keyboard.press("Escape");
        // Cobrar y cancelar una venta (cuadros de confirmación). Solo se abren y se cierran: no cambian datos.
        await page.getByRole("button", { name: "Marcar cobrada" }).first().click();
        await page.getByRole("dialog").waitFor();
        await page.waitForTimeout(300);
        await auditar(r + " [cobrar]");
        await page.keyboard.press("Escape");
        await page.getByRole("button", { name: "Cancelar venta" }).first().click();
        await page.getByRole("dialog").waitFor();
        await page.waitForTimeout(300);
        await auditar(r + " [cancelar]");
        await page.keyboard.press("Escape");
        await page.getByRole("button", { name: /Atendidas/ }).click();
        await page.getByText("Se coordinó el envío por Servientrega").waitFor();
        await page.waitForTimeout(300);
        await auditar(r + " [atendidas]");
      }
      // Producto propio nuevo: errores de validación del formulario y las opciones de entrega abiertas.
      if (r === "/catalogo/propio/nuevo") {
        await page.getByRole("button", { name: "Agregar envío" }).click();
        await page.getByRole("button", { name: "Agregar retiro" }).click();
        await page.waitForTimeout(300);
        await auditar(r + " [opciones de entrega]");
        await page.getByRole("button", { name: /Publicar|Crear|Guardar/ }).last().click();
        await page.waitForTimeout(500);
        await auditar(r + " [errores de validacion]");
      }
      // Ficha de un producto propio: la galería con fotos y una prueba completa con su cierre manual.
      if (r === "/catalogo/producto/PROP-0001") {
        await page.getByText("Fotos del producto").first().waitFor();
        await page.getByRole("button", { name: "Abrir la prueba" }).click();
        await page.getByRole("button", { name: "Quiero comprarlo" }).click();
        await page.getByText("Herramientas que usó").first().waitFor();
        await page.getByLabel("Mensaje del cliente de prueba").fill("Soy Ana Pérez, vivo en Av. Remigio Crespo 3-45, Cuenca, Azuay. Pago contra entrega");
        await page.getByRole("button", { name: "Enviar" }).click();
        await page.getByText("Para tu pedido tengo estas opciones de entrega").waitFor();
        await page.getByLabel("Mensaje del cliente de prueba").fill("1");
        await page.getByRole("button", { name: "Enviar" }).click();
        await page.getByText("Pedido que te habría llegado para gestionar").waitFor();
        await page.waitForTimeout(300);
        await auditar(r + " [prueba cierre manual]");
        await page.getByRole("button", { name: "Reiniciar prueba" }).click();
        await page.getByRole("button", { name: "Quiero verlo en persona" }).click();
        await page.getByText("Lo que te habría llegado en «Por gestionar»").waitFor();
        await page.waitForTimeout(300);
        await auditar(r + " [prueba ver producto]");
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
console.log(`Cuadros ⓘ abiertos y auditados: ${infosAuditados}`);
if (!resumen.size) console.log("SIN VIOLACIONES");
for (const [k, arr] of resumen) { console.log("\n" + k + "  — " + arr.length + " casos"); arr.slice(0, 4).forEach((a) => console.log("   ", a)); }
