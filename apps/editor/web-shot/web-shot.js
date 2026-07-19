// web-shot.js — captura print de página/notícia para o agente editor.
// Usa o Chrome já instalado via puppeteer-core (não baixa Chromium).
//
// Uso:
//   node web-shot.js --url "<url>" --out "<arquivo.png>" [opções]
//
// Opções:
//   --sel "<css>"       captura só esse elemento (ex.: "article", ".c-card")
//   --w 1280 --h 800    viewport (default 1280x800)
//   --full              página inteira (rolagem toda) em vez do viewport
//   --wait 2500         ms extras após load (lazy-load/imagens; default 2500)
//   --dark              força tema escuro (prefers-color-scheme: dark)
//
// Fecha automaticamente banners de cookie/consent comuns antes do print.

const puppeteer = require("puppeteer-core");
const fs = require("fs");

function arg(name, def) {
  const i = process.argv.indexOf("--" + name);
  if (i === -1) return def;
  const v = process.argv[i + 1];
  return v && !v.startsWith("--") ? v : true; // flags sem valor viram true
}

const CHROMES = [
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
];

function acharChrome() {
  for (const p of CHROMES) if (fs.existsSync(p)) return p;
  throw new Error("Chrome/Edge não encontrado nos caminhos padrão.");
}

// texto de botões de aceite de cookie mais comuns (pt/en)
const CONSENT_TXT = [
  "aceitar todos", "aceitar", "aceito", "concordo", "entendi", "prosseguir",
  "accept all", "accept", "i agree", "agree", "got it", "continue",
];

async function fecharConsent(page) {
  try {
    await page.evaluate((textos) => {
      const alvos = [...document.querySelectorAll("button, a, [role=button]")];
      for (const el of alvos) {
        const t = (el.innerText || el.textContent || "").trim().toLowerCase();
        if (t && textos.some((x) => t === x || t.startsWith(x))) {
          el.click();
          return;
        }
      }
    }, CONSENT_TXT);
  } catch (_) {}
}

(async () => {
  const url = arg("url");
  const out = arg("out");
  if (!url || !out) {
    console.error('Faltou --url e/ou --out. Ex.: node web-shot.js --url "https://..." --out "shot.png"');
    process.exit(2);
  }
  const w = parseInt(arg("w", "1280"), 10);
  const h = parseInt(arg("h", "800"), 10);
  const full = arg("full", false) === true;
  const dark = arg("dark", false) === true;
  const sel = arg("sel", null);
  const waitExtra = parseInt(arg("wait", "2500"), 10);

  const browser = await puppeteer.launch({
    executablePath: acharChrome(),
    headless: "new",
    args: ["--no-sandbox", "--disable-dev-shm-usage", "--lang=pt-BR"],
  });
  try {
    const page = await browser.newPage();
    await page.setViewport({ width: w, height: h, deviceScaleFactor: 2 }); // 2x = nítido no vídeo
    if (dark) await page.emulateMediaFeatures([{ name: "prefers-color-scheme", value: "dark" }]);
    await page.setUserAgent(
      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    );

    await page.goto(url, { waitUntil: "networkidle2", timeout: 45000 });
    await fecharConsent(page);
    await new Promise((r) => setTimeout(r, waitExtra));

    let alvo = page;
    if (sel) {
      const el = await page.$(sel);
      if (!el) throw new Error(`Seletor não encontrado: ${sel}`);
      alvo = el;
    }
    await alvo.screenshot({ path: out, fullPage: sel ? false : full });

    const titulo = await page.title();
    console.log(JSON.stringify({ ok: true, out, titulo, url }));
  } catch (e) {
    console.log(JSON.stringify({ ok: false, erro: String(e.message || e), url }));
    process.exitCode = 1;
  } finally {
    await browser.close();
  }
})();
