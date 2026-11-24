// README screenshots and GIF frames, captured from the live site with headless Microsoft Edge
// over the Chrome DevTools Protocol (no extra packages: Node 22's built-in WebSocket and fetch).
//
//   node tools/screenshots.mjs [siteUrl]
//
// Writes docs/img/readme/*.png (stills) and docs/img/readme/frames/*.png (GIF frames; turn them
// into a GIF with: uv run python tools/make_gif.py). Edge's path is the Windows default; set
// EDGE_PATH to override. One-shot "--screenshot" mode is not used because it stalls MapLibre's
// web worker (D015), so this drives a real page and waits in real time.

import { spawn } from "node:child_process";
import { mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const SITE = process.argv[2] || "https://koiiphish.github.io/AlgalBloom/";
const OUT = "docs/img/readme";
const EDGE = process.env.EDGE_PATH || "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// Start Edge with remote debugging and return a small "send a command" helper for one tab.
async function openBrowser() {
  const port = 9300 + Math.floor(Math.random() * 500);
  const profile = mkdtempSync(join(tmpdir(), "edge-shots-"));
  const edge = spawn(EDGE, ["--headless=new", `--remote-debugging-port=${port}`,
    `--user-data-dir=${profile}`, "--hide-scrollbars", "about:blank"], { stdio: "ignore" });
  let targets = [];
  for (let i = 0; i < 50 && !targets.length; i++) {
    try { targets = (await (await fetch(`http://127.0.0.1:${port}/json`)).json()).filter((t) => t.type === "page"); } catch { /* not up yet */ }
    await sleep(200);
  }
  const ws = new WebSocket(targets[0].webSocketDebuggerUrl);
  await new Promise((r) => ws.addEventListener("open", r));
  let id = 0;
  const waiting = new Map();
  ws.addEventListener("message", (m) => {
    const msg = JSON.parse(m.data);
    if (msg.id && waiting.has(msg.id)) { waiting.get(msg.id)(msg.result); waiting.delete(msg.id); }
  });
  const send = (method, params = {}) => new Promise((r) => { const i = ++id; waiting.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
  return { send, close: () => { ws.close(); edge.kill(); } };
}

// Set the window size (phone sizes also switch on mobile emulation).
async function viewport(send, width, height) {
  await send("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: 1, mobile: width < 700 });
}

// Run a bit of JavaScript in the page (e.g. type into the search box, click a button).
async function run(send, js) {
  await send("Runtime.evaluate", { expression: js, awaitPromise: true });
}

// Save the current view as a PNG file.
async function shot(send, path) {
  const r = await send("Page.captureScreenshot", { format: "png" });
  writeFileSync(path, Buffer.from(r.data, "base64"));
  console.log("saved", path);
}

// The tour: each step does something, waits for the map to settle, and saves a picture.
const TYPE = (text) => `(() => { const s = document.getElementById("area-search"); s.value = ${JSON.stringify(text)}; s.dispatchEvent(new Event("input")); })()`;
const CLICK = (sel) => `document.querySelector(${JSON.stringify(sel)})?.click()`;

async function main() {
  mkdirSync(`${OUT}/frames`, { recursive: true });
  const { send, close } = await openBrowser();
  await send("Page.enable");
  try {
    // Desktop tour (also the GIF frames).
    await viewport(send, 1280, 800);
    await send("Page.navigate", { url: `${SITE}?shots=${Date.now()}` });
    await sleep(14000);
    await shot(send, `${OUT}/map.png`);
    await shot(send, `${OUT}/frames/01.png`);
    await run(send, TYPE("Swansea"));
    await sleep(6000);
    await shot(send, `${OUT}/search.png`);
    await shot(send, `${OUT}/frames/02.png`);
    await run(send, CLICK(".place-areas button"));
    await sleep(6000);
    await shot(send, `${OUT}/panel.png`);
    await shot(send, `${OUT}/frames/03.png`);
    await run(send, CLICK(".more-info summary"));
    await sleep(3000);
    await shot(send, `${OUT}/frames/04.png`);
    await run(send, CLICK("input[value=chl]"));
    await sleep(6000);
    await shot(send, `${OUT}/chlorophyll.png`);
    await shot(send, `${OUT}/frames/05.png`);
    // Verification page.
    await send("Page.navigate", { url: `${SITE}verification.html?shots=${Date.now()}` });
    await sleep(4000);
    await shot(send, `${OUT}/verification.png`);
    // Phone view with an area open.
    await viewport(send, 390, 844);
    await send("Page.navigate", { url: `${SITE}?shots=${Date.now()}` });
    await sleep(12000);
    await run(send, CLICK("#area-items button"));
    await sleep(5000);
    await shot(send, `${OUT}/mobile.png`);
  } finally {
    close();
  }
}

main();
