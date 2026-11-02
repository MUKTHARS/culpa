// Records the Culpa demo in a visible Chrome window (app mode: only Culpa on screen) and turns it into a video.
//
//   node scripts/record-demo.mjs            record the flow, then encode (needs ffmpeg on PATH)
//   node scripts/record-demo.mjs --encode   encode frames from an earlier run
//
// The flow: buyer agent -> PayPal (recording PAUSES; you log in and approve) -> merchant ships ->
// analyst opens a dispute -> verdict -> partial refund -> benchmark. Needs the API and web app running (scripts\dev.ps1).
import { spawn, spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync, existsSync, readdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

const ROOT = resolve(import.meta.dirname, "..");
const OUT_DIR = join(ROOT, "demo-recording");
const FRAMES = join(OUT_DIR, "frames");
const VIDEO = join(OUT_DIR, "culpa-demo.mp4");
const WEB = "http://127.0.0.1:3000";
const CHROME = "C:/Program Files/Google/Chrome/Application/chrome.exe";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// ffmpeg on PATH, or a fresh winget install the current terminal doesn't see yet.
function ffmpegPath() {
  const root = join(process.env.LOCALAPPDATA || "", "Microsoft", "WinGet", "Packages");
  try {
    for (const pkg of readdirSync(root).filter((d) => d.startsWith("Gyan.FFmpeg"))) {
      for (const build of readdirSync(join(root, pkg))) {
        const exe = join(root, pkg, build, "bin", "ffmpeg.exe");
        if (existsSync(exe)) return exe;
      }
    }
  } catch {}
  return "ffmpeg";
}

function encode() {
  const list = join(OUT_DIR, "frames.txt");
  if (!existsSync(list)) return console.log("No frames found. Run the recording first.");
  const r = spawnSync(ffmpegPath(), ["-y", "-f", "concat", "-safe", "0", "-i", list, "-vf",
    "scale=1280:-2:flags=lanczos,format=yuv420p", "-r", "30", "-c:v", "libx264", "-crf", "20", VIDEO], { stdio: "inherit" });
  if (r.error) {
    console.log("\nffmpeg is not installed. Install it with:  winget install Gyan.FFmpeg");
    console.log("Then open a new terminal and run:        node scripts/record-demo.mjs --encode");
  } else console.log(`\nVideo saved: ${VIDEO}`);
}

if (process.argv.includes("--encode")) { encode(); process.exit(0); }

const env = Object.fromEntries(readFileSync(join(ROOT, "apps/api/.env"), "utf8").replace(/^\uFEFF/, "").split(/\r?\n/)
  .filter((l) => l.includes("=") && !l.trim().startsWith("#")).map((l) => [l.slice(0, l.indexOf("=")).trim(), l.slice(l.indexOf("=") + 1).trim()]));

rmSync(OUT_DIR, { recursive: true, force: true });
mkdirSync(FRAMES, { recursive: true });
const chrome = spawn(CHROME, ["--remote-debugging-port=9360", `--user-data-dir=${mkdtempSync(join(tmpdir(), "culpa-rec-"))}`,
  "--window-size=1280,800", "--no-first-run", "--no-default-browser-check", `--app=${WEB}/`], { stdio: "ignore" });

let target;
for (let i = 0; i < 60 && !target; i++) {
  await sleep(250);
  try { target = (await (await fetch("http://127.0.0.1:9360/json")).json()).find((t) => t.type === "page"); } catch {}
}
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((r) => (ws.onopen = r));
let id = 0;
const pending = new Map();
const frames = []; // [file, timestamp]
let recording = false;
const send = (method, params = {}) => new Promise((r) => { const n = ++id; pending.set(n, r); ws.send(JSON.stringify({ id: n, method, params })); });
ws.onmessage = (m) => {
  const msg = JSON.parse(m.data);
  if (msg.id && pending.has(msg.id)) pending.get(msg.id)(msg);
  if (msg.method === "Page.screencastFrame") {
    const { data, sessionId, metadata } = msg.params;
    send("Page.screencastFrameAck", { sessionId });
    if (!recording) return;
    const file = join(FRAMES, `${String(frames.length).padStart(6, "0")}.jpg`);
    writeFileSync(file, Buffer.from(data, "base64"));
    frames.push([file, metadata.timestamp]);
  }
};
const ev = async (expr) => (await send("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true })).result?.result?.value;
const waitFor = async (expr, ms = 30000) => { for (let t = 0; t < ms; t += 250) { if (await ev(expr)) return true; await sleep(250); } throw new Error(`timed out waiting for: ${expr}`); };
const click = (sel, text) => ev(`(() => { const el = [...document.querySelectorAll(${JSON.stringify(sel)})].find(e => e.textContent.trim().startsWith(${JSON.stringify(text)})); if (el) { el.scrollIntoView({block: "center"}); el.click(); } return !!el; })()`);
const type = async (sel, text) => { await ev(`document.querySelector(${JSON.stringify(sel)}).focus()`); await send("Input.insertText", { text }); };
const go = async (path) => { await send("Page.navigate", { url: WEB + path }); await waitFor("document.readyState === 'complete'"); await sleep(1500); };
const scroll = async (y, ms = 1500) => { await ev(`window.scrollTo({top: ${y}, behavior: "smooth"})`); await sleep(ms); };
const start = async () => { recording = true; await send("Page.startScreencast", { format: "jpeg", quality: 85, maxWidth: 1280, maxHeight: 800 }); };
const stop = async () => { recording = false; await send("Page.stopScreencast"); };

try {
  await send("Page.enable");
  await send("Runtime.enable");
  await go("/");
  await start();
  console.log("Recording: home page");
  await sleep(4000);

  console.log("Recording: buyer agent");
  await go("/agent");
  await click("button", "Ambiguous size");
  await sleep(2500);
  await click("button", "Sign mandate and shop");
  await waitFor(`document.body.innerText.includes("Search results")`, 60000);
  await sleep(2500);
  await ev(`document.querySelector("section[aria-labelledby=search-results]").scrollIntoView({behavior: "smooth"})`);
  await sleep(4000);
  await scroll(0, 2000);

  await click("a", "Approve");
  await stop();
  console.log("\n>>> Recording PAUSED. In the Chrome window, log in to PayPal with the sandbox buyer and approve.");
  console.log(">>> Recording resumes by itself when PayPal sends you back to Culpa.\n");
  await waitFor(`location.href.startsWith("${WEB}/checkout/return")`, 10 * 60000);
  await waitFor(`document.body.innerText.includes("Evidence root")`, 60000);
  await start();
  console.log("Recording: payment captured");
  await sleep(4000);

  console.log("Recording: merchant ships");
  await go("/merchant");
  await click("button", "Ship");
  await sleep(3500);

  console.log("Recording: analyst login and dispute");
  await go("/login");
  await type("input[autocomplete=username]", env.ANALYST_USERNAME ?? "");
  await type("input[type=password]", env.ANALYST_PASSWORD ?? "");
  await sleep(800);
  await click("button", "Log in");
  await sleep(2500);
  await go("/orders");
  await click("button", "Open dispute");
  await sleep(2000);
  await click("label", "It's not as described");
  await sleep(1200);
  await ev(`(() => { const s = [...document.querySelectorAll("label")].find(l => l.textContent.startsWith("What was wrong?")).querySelector("select");
    Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value").set.call(s, "size"); s.dispatchEvent(new Event("change", {bubbles: true})); })()`);
  await sleep(1000);
  await type("section[aria-labelledby^=dispute] input", "US 9");
  await sleep(2000);
  await click("section[aria-labelledby^=dispute] button", "Open dispute");

  console.log("Recording: verdict");
  await waitFor(`location.pathname.startsWith("/cases/") && !document.body.innerText.includes("Analyzing the dispute")
    && document.body.innerText.includes("Who is at fault")`, 90000);
  await sleep(5000);
  await scroll(500, 4000);
  await scroll(1100, 4000);
  await scroll(0, 2000);

  console.log("Recording: settlement");
  await click("label", "Partial refund");
  await sleep(2000);
  await click("button", "Confirm and");
  await waitFor(`document.body.innerText.includes("Outcome")`, 90000);
  await sleep(5000);

  console.log("Recording: benchmark");
  await go("/benchmark");
  await sleep(5000);
  await stop();
} catch (e) {
  await stop().catch(() => {});
  console.log(`\nStopped early: ${e.message}. Frames recorded so far are kept.`);
}

// ffmpeg concat list: each frame shown until the next one (pauses at PayPal are not in the video).
const lines = [];
for (let i = 0; i < frames.length; i++) {
  const dur = i + 1 < frames.length ? Math.min(frames[i + 1][1] - frames[i][1], 2) : 1;
  lines.push(`file '${frames[i][0].replace(/\\/g, "/")}'`, `duration ${Math.max(dur, 0.01).toFixed(3)}`);
}
if (frames.length) lines.push(`file '${frames.at(-1)[0].replace(/\\/g, "/")}'`);
writeFileSync(join(OUT_DIR, "frames.txt"), lines.join("\n"));
console.log(`\n${frames.length} frames recorded.`);
ws.close();
chrome.kill();
encode();
