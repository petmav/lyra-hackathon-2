import {
  Presentation,
  PresentationFile,
  FileBlob,
  column,
  row,
  grid,
  layers,
  panel,
  text,
  image,
  shape,
  rule,
  fill,
  hug,
  fixed,
  grow,
  fr,
  wrap,
  drawSlideToCtx,
} from "@oai/artifact-tool";
import { Canvas } from "skia-canvas";
import fs from "node:fs/promises";
import path from "node:path";

const W = 1920;
const H = 1080;
const OUT = path.resolve("..");
const ROOT = path.resolve("..", "..");
const ASSETS = path.resolve("scratch", "assets");
const RENDERS = path.resolve("scratch", "renders");
const PPTX_RENDERS = path.resolve("scratch", "pptx-renders");

const C = {
  ink: "#070A0F",
  ink2: "#0B1018",
  panel: "#111821",
  ivory: "#F7F2E7",
  muted: "#9CA3AF",
  cyan: "#2DE2E6",
  cyan2: "#70F0FF",
  gold: "#F4C95D",
  green: "#7DFFA8",
  red: "#FF6B6B",
  line: "#25303D",
  white: "#FFFFFF",
};

const font = {
  display: "Aptos Display",
  body: "Aptos",
  mono: "Cascadia Mono",
};

const img = (p) => path.resolve(ROOT, p);
const emblem = path.resolve(ASSETS, "praetor-emblem.png");
const DATA_URLS = new Map();
const IMAGE_FILES = [
  ["emblem", emblem],
  ["screenshots/e2e/chromium-desktop-pitch-workflows.png", img("screenshots/e2e/chromium-desktop-pitch-workflows.png")],
  ["screenshots/e2e/chromium-desktop-pitch-dashboard.png", img("screenshots/e2e/chromium-desktop-pitch-dashboard.png")],
  ["screenshots/e2e/chromium-desktop-pitch-live-run.png", img("screenshots/e2e/chromium-desktop-pitch-live-run.png")],
  ["screenshots/e2e/chromium-desktop-pitch-evidence.png", img("screenshots/e2e/chromium-desktop-pitch-evidence.png")],
  ["screenshots/e2e/chromium-desktop-pitch-hooks.png", img("screenshots/e2e/chromium-desktop-pitch-hooks.png")],
];

async function preloadImages() {
  for (const [key, file] of IMAGE_FILES) {
    const data = await fs.readFile(file);
    DATA_URLS.set(key, `data:image/png;base64,${data.toString("base64")}`);
  }
}

function dataUrl(key) {
  const value = DATA_URLS.get(key);
  if (!value) throw new Error(`Missing preloaded image: ${key}`);
  return value;
}

function title(textValue, size = 76, width = 1220) {
  return text(textValue, {
    name: "slide-title",
    width: wrap(width),
    height: hug,
    style: {
      fontFace: font.display,
      fontSize: size,
      bold: true,
      color: C.ivory,
    },
  });
}

function eyebrow(value, color = C.cyan) {
  return text(value, {
    name: "eyebrow",
    width: hug,
    height: hug,
    style: {
      fontFace: font.mono,
      fontSize: 18,
      bold: true,
      color,
      letterSpacing: 0,
    },
  });
}

function body(value, size = 30, color = C.muted, width = 1000) {
  return text(value, {
    name: "body",
    width: wrap(width),
    height: hug,
    style: {
      fontFace: font.body,
      fontSize: size,
      color,
      lineSpacing: 1.12,
    },
  });
}

function small(value, color = C.muted, width = 520) {
  return text(value, {
    name: "small-label",
    width: wrap(width),
    height: hug,
    style: { fontFace: font.body, fontSize: 20, color, lineSpacing: 1.12 },
  });
}

function bg(children, extra = []) {
  return layers(
    { name: "stage", width: fill, height: fill },
    [
      shape({ name: "background", width: fill, height: fill, fill: C.ink }),
      shape({ name: "top-band", width: fill, height: fixed(12), fill: C.cyan }),
      ...extra,
      ...children,
    ],
  );
}

function deckMark() {
  return row(
    { name: "wordmark", width: fixed(196), height: hug, gap: 12, align: "center" },
    [
      image({
        name: "praetor-emblem-small",
        dataUrl: dataUrl("emblem"),
        width: fixed(42),
        height: fixed(42),
        fit: "cover",
        borderRadius: "rounded-full",
        alt: "Praetor shield emblem",
      }),
      text("PRAETOR", {
        name: "wordmark-text",
        width: fixed(116),
        height: hug,
        style: {
          fontFace: font.mono,
          fontSize: 16,
          bold: true,
          color: C.ivory,
          letterSpacing: 0,
        },
      }),
    ],
  );
}

function shell(content, footer = "") {
  return bg([
    column(
      {
        name: "root",
        width: fill,
        height: fill,
        padding: { x: 92, y: 56 },
        gap: 30,
      },
      [
        row(
          { name: "topline", width: fill, height: hug, justify: "between", align: "center" },
          [
            deckMark(),
            text("2 minute pitch", {
              name: "context",
              width: hug,
              height: hug,
              style: { fontFace: font.mono, fontSize: 16, color: "#64748B" },
            }),
          ],
        ),
        content,
        row(
          { name: "footer", width: fill, height: hug, justify: "between", align: "center" },
          [
            text(footer, {
              name: "source",
              width: wrap(1220),
              height: hug,
              style: { fontFace: font.body, fontSize: 13, color: "#5D6875" },
            }),
            text("2026 Lyra x Relevance AI x January Capital x OpenAI hackathon", {
              name: "date",
              width: hug,
              height: hug,
              style: { fontFace: font.body, fontSize: 13, color: "#5D6875" },
            }),
          ],
        ),
      ],
    ),
  ]);
}

function screen(pathValue, name, fit = "contain") {
  return panel(
    {
      name: `${name}-frame`,
      width: fill,
      height: fill,
      padding: 0,
      fill: "#05070B",
      borderRadius: "rounded-lg",
    },
    image({
      name,
      dataUrl: dataUrl(pathValue),
      width: fill,
      height: fill,
      fit,
      borderRadius: "rounded-lg",
      alt: `${name} product screenshot`,
    }),
  );
}

function slide(presentation, node) {
  const s = presentation.slides.add();
  s.compose(node, { frame: { left: 0, top: 0, width: W, height: H }, baseUnit: 8 });
  return s;
}

function cover(p) {
  slide(
    p,
    bg(
      [
        grid(
          {
            name: "cover-root",
            width: fill,
            height: fill,
            columns: [fr(1.1), fr(0.9)],
            columnGap: 70,
            padding: { x: 96, y: 76 },
            alignItems: "center",
          },
          [
            column({ name: "cover-type", width: fill, height: hug, gap: 30 }, [
              eyebrow("AI governance that does the work", C.gold),
              text("PRAETOR", {
                name: "cover-title",
                width: fill,
                height: hug,
                style: {
                  fontFace: font.display,
                  fontSize: 128,
                  bold: true,
                  color: C.ivory,
                  letterSpacing: 0,
                },
              }),
              rule({ name: "cover-rule", width: fixed(380), stroke: C.cyan, weight: 5 }),
              body(
                "Run AI agents to do your compliance work. Govern the AI you ship. One control plane.",
                35,
                "#D6DEE8",
                780,
              ),
            ]),
            image({
              name: "cover-emblem",
              dataUrl: dataUrl("emblem"),
              width: fixed(620),
              height: fixed(620),
              fit: "cover",
              borderRadius: "rounded-full",
              alt: "Praetor generated shield emblem",
            }),
          ],
        ),
      ],
      [
        shape({ name: "gold-slab", width: fixed(420), height: fill, fill: "#1C1710" }),
      ],
    ),
  );
}

function problem(p) {
  slide(
    p,
    shell(
      grid(
        {
          name: "problem-grid",
          width: fill,
          height: grow(1),
          columns: [fr(1.04), fr(0.96)],
          columnGap: 76,
          alignItems: "center",
        },
        [
          column({ name: "problem-copy", width: fill, height: hug, gap: 20 }, [
            eyebrow("The timing problem"),
            title("AI work is scaling faster than AI evidence.", 72, 930),
            body(
              "Enterprises are letting agents read, reason, decide, and act across SaaS systems. Compliance teams still get screenshots, tickets, and archaeology.",
              31,
              "#CBD5E1",
              820,
            ),
          ]),
          column({ name: "problem-points", width: fill, height: fill, gap: 14, justify: "center" }, [
            row({ width: fill, height: hug, gap: 20, align: "start" }, [
              text("01", { width: fixed(72), height: hug, style: { fontFace: font.mono, fontSize: 29, bold: true, color: C.cyan } }),
              body("Tool calls cross trust boundaries before governance catches up.", 26, C.ivory, 640),
            ]),
            row({ width: fill, height: hug, gap: 20, align: "start" }, [
              text("02", { width: fixed(72), height: hug, style: { fontFace: font.mono, fontSize: 29, bold: true, color: C.gold } }),
              body("Audit proof is assembled after the fact, from systems that never agreed on state.", 26, C.ivory, 640),
            ]),
            row({ width: fill, height: hug, gap: 20, align: "start" }, [
              text("03", { width: fixed(72), height: hug, style: { fontFace: font.mono, fontSize: 29, bold: true, color: C.green } }),
              body("The next buyer asks: can I trust the agents that govern my agents?", 26, C.ivory, 640),
            ]),
          ]),
        ],
      ),
      "Source inputs: PRAETOR_PLAN_V2 and implementation handoff.",
    ),
  );
}

function product(p) {
  slide(
    p,
    shell(
      column({ name: "product-root", width: fill, height: grow(1), gap: 34 }, [
        column({ name: "product-title", width: fill, height: hug, gap: 12 }, [
          eyebrow("The product"),
          title("One control plane for governed agentic work.", 67, 1290),
          body(
            "Praetor runs compliance workflows and supervises production AI inside the same event, policy, sandbox, and evidence model.",
            28,
            "#C8D3DF",
            1200,
          ),
        ]),
        grid(
          {
            name: "two-surfaces",
            width: fill,
            height: fill,
            columns: [fr(1), fr(1)],
            columnGap: 34,
          },
          [
            column({ width: fill, height: fill, gap: 14 }, [
              text("Run governed workflows", {
                name: "workflow-label",
                width: fill,
                height: hug,
                style: { fontFace: font.display, fontSize: 30, bold: true, color: C.cyan },
              }),
              screen("screenshots/e2e/chromium-desktop-pitch-workflows.png", "workflows-screen", "cover"),
            ]),
            column({ width: fill, height: fill, gap: 14 }, [
              text("Supervise production AI", {
                name: "supervise-label",
                width: fill,
                height: hug,
                style: { fontFace: font.display, fontSize: 30, bold: true, color: C.gold },
              }),
              screen("screenshots/e2e/chromium-desktop-pitch-dashboard.png", "dashboard-screen", "cover"),
            ]),
          ],
        ),
      ]),
      "Repo evidence: Next.js app routes for workflows, workflow runs, assets, evidence, hooks, inventory, obligations, and sandbox.",
    ),
  );
}

function demoFlow(p) {
  slide(
    p,
    shell(
      grid(
        {
          name: "demo-grid",
          width: fill,
          height: grow(1),
          columns: [fr(0.72), fr(1.28)],
          columnGap: 54,
        },
        [
          column({ name: "flow-copy", width: fill, height: fill, gap: 28, justify: "center" }, [
            eyebrow("Live path"),
            title("Scan, cite, patch.\nSandbox, approve.", 58, 610),
            body(
              "A compliance agent becomes a governed asset, runs inside the sandbox, emits a finding, proposes the change, and leaves a hash-chained trace.",
              29,
              "#CFDAE5",
              600,
            ),
            rule({ width: fixed(240), stroke: C.gold, weight: 4 }),
            small("The demo is deterministic when needed, but production-shaped: queued runs, leases, OPA gates, Redis events, Postgres persistence.", "#94A3B8", 590),
          ]),
          screen("screenshots/e2e/chromium-desktop-pitch-live-run.png", "live-run-screen", "cover"),
        ],
      ),
      "Verified in docs/PHASE_STATUS.md: production workflow runs, event streams, sandbox launches, and evidence consumption.",
    ),
  );
}

function differentiation(p) {
  const rows = [
    ["Automation apps", "Move data between tools", "Execute governed agent work"],
    ["AI governance tools", "Inventory and report posture", "Run controls where work happens"],
    ["Workflow builders", "Orchestrate steps", "Prove every decision, event, and external write"],
    ["Point GRC systems", "Collect evidence later", "Generate signed evidence continuously"],
  ];

  slide(
    p,
    shell(
      column({ name: "diff-root", width: fill, height: grow(1), gap: 34 }, [
        column({ width: fill, height: hug, gap: 12 }, [
          eyebrow("Why this is not Zapier for compliance", C.gold),
          title("Praetor is a runtime, not a router.", 70, 1260),
        ]),
        grid(
          {
            name: "diff-table",
            width: fill,
            height: fill,
            columns: [fr(0.95), fr(1.05), fr(1.25)],
            rows: [fixed(70), ...rows.map(() => fr(1))],
            columnGap: 0,
            rowGap: 0,
          },
          [
            text("Compared with", { width: fill, height: fill, style: { fontFace: font.mono, fontSize: 18, bold: true, color: "#7DD3FC" } }),
            text("They usually", { width: fill, height: fill, style: { fontFace: font.mono, fontSize: 18, bold: true, color: "#94A3B8" } }),
            text("Praetor", { width: fill, height: fill, style: { fontFace: font.mono, fontSize: 18, bold: true, color: C.gold } }),
            ...rows.flatMap((r, i) => [
              panel({ padding: { x: 18, y: 20 }, fill: i % 2 ? "#0C121B" : "#101923" }, text(r[0], { width: fill, height: hug, style: { fontFace: font.display, fontSize: 29, bold: true, color: C.ivory } })),
              panel({ padding: { x: 18, y: 20 }, fill: i % 2 ? "#0C121B" : "#101923" }, text(r[1], { width: fill, height: hug, style: { fontFace: font.body, fontSize: 27, color: "#AAB7C5" } })),
              panel({ padding: { x: 18, y: 20 }, fill: i % 2 ? "#12150F" : "#171A12" }, text(r[2], { width: fill, height: hug, style: { fontFace: font.body, fontSize: 27, bold: true, color: "#FFE9A6" } })),
            ]),
          ],
        ),
      ]),
      "Prompted by the plan's Zapier-vs-Praetor differentiation requirement.",
    ),
  );
}

function architecture(p) {
  function node(label, accent, sub) {
    return panel(
      {
        width: fill,
        height: hug,
        padding: { x: 24, y: 18 },
        fill: "#0F1722",
        borderRadius: "rounded-lg",
      },
      column({ width: fill, height: hug, gap: 6 }, [
        text(label, { width: fill, height: hug, style: { fontFace: font.display, fontSize: 28, bold: true, color: accent } }),
        text(sub, { width: fill, height: hug, style: { fontFace: font.body, fontSize: 18, color: "#A8B4C2" } }),
      ]),
    );
  }

  slide(
    p,
    shell(
      grid(
        {
          name: "arch-grid",
          width: fill,
          height: grow(1),
          columns: [fr(1), fr(1.15)],
          columnGap: 56,
        },
        [
          column({ name: "arch-copy", width: fill, height: fill, gap: 26, justify: "center" }, [
            eyebrow("The moat"),
            title("Workflow agents are governed assets.", 64, 780),
            body(
              "Every agent step runs with the same controls you sell to customers: sandbox, policy, corpus citations, external-effect gates, and evidence.",
              29,
              "#D0DAE5",
              760,
            ),
            screen("screenshots/e2e/chromium-desktop-pitch-evidence.png", "evidence-screen", "cover"),
          ]),
          column({ name: "arch-nodes", width: fill, height: fill, gap: 18, justify: "center" }, [
            node("FastAPI gateway + Postgres", C.ivory, "Canonical assets, runs, decisions, proposals, evidence"),
            node("Redis Streams + hash chain", C.cyan, "Every event is ordered, replayable, and tamper-evident"),
            node("OPA hot path + human gates", C.gold, "Sub-10ms policy decisions before external effects"),
            node("Docker sandbox orchestrator", C.green, "Agent execution, replay mode, hardened default isolation"),
            node("MCP + JSON Hook Stack", "#C4B5FD", "GitHub, Jira, Slack, ServiceNow, GRC, internal OpenAPI systems"),
          ]),
        ],
      ),
      "Technical basis: docs/IMPLEMENTATION_HANDOFF.md, docs/API.md, and repo subsystem layout.",
    ),
  );
}

function close(p) {
  slide(
    p,
    shell(
      grid(
        {
          name: "close-grid",
          width: fill,
          height: grow(1),
          columns: [fr(0.98), fr(1.02)],
          columnGap: 64,
          alignItems: "center",
        },
        [
          column({ width: fill, height: hug, gap: 28 }, [
            eyebrow("The landing"),
            title("Audit-ready AI operations while the work happens.", 63, 860),
            body(
              "Start with one painful GRC workflow and one production agent. Praetor proves the loop: work gets done, controls fire in real time, and evidence is already there.",
              30,
              "#D5DEE8",
              790,
            ),
            panel(
              { width: fill, height: hug, padding: { x: 28, y: 22 }, fill: "#111A12", borderRadius: "rounded-lg" },
              text("Ask: pilot the compliance scan + production-agent supervision path with a design partner.", {
                name: "ask",
                width: fill,
                height: hug,
                style: { fontFace: font.display, fontSize: 30, bold: true, color: "#E9FFD8" },
              }),
            ),
          ]),
          screen("screenshots/e2e/chromium-desktop-pitch-hooks.png", "hooks-screen", "cover"),
        ],
      ),
      "Built from current repo screenshots and local docs.",
    ),
  );
}

async function renderDeck(presentation, outDir) {
  await fs.rm(outDir, { recursive: true, force: true });
  await fs.mkdir(outDir, { recursive: true });
  for (const [i, s] of presentation.slides.items.entries()) {
    const canvas = new Canvas(W, H);
    const ctx = canvas.getContext("2d");
    await drawSlideToCtx(s, presentation, ctx);
    await canvas.toFile(path.join(outDir, `slide-${String(i + 1).padStart(2, "0")}.png`));
  }
}

async function makeMontage(inDir, outPath) {
  const { default: sharp } = await import("sharp").catch(() => ({ default: null }));
  if (!sharp) return false;
  const files = (await fs.readdir(inDir)).filter((f) => f.endsWith(".png")).sort();
  const thumbW = 480;
  const thumbH = 270;
  const gap = 22;
  const cols = 2;
  const rows = Math.ceil(files.length / cols);
  const composites = [];
  for (const [i, file] of files.entries()) {
    const input = path.join(inDir, file);
    const buf = await sharp(input).resize(thumbW, thumbH).png().toBuffer();
    composites.push({ input: buf, left: gap + (i % cols) * (thumbW + gap), top: gap + Math.floor(i / cols) * (thumbH + gap) });
  }
  await sharp({
    create: {
      width: cols * thumbW + (cols + 1) * gap,
      height: rows * thumbH + (rows + 1) * gap,
      channels: 3,
      background: "#E5E7EB",
    },
  })
    .composite(composites)
    .png()
    .toFile(outPath);
  return true;
}

async function main() {
  await fs.mkdir(path.resolve("output"), { recursive: true });
  await fs.mkdir(RENDERS, { recursive: true });
  await fs.mkdir(PPTX_RENDERS, { recursive: true });
  await preloadImages();

  const p = Presentation.create({ slideSize: { width: W, height: H } });
  cover(p);
  problem(p);
  product(p);
  demoFlow(p);
  differentiation(p);
  architecture(p);
  close(p);

  const pptx = await PresentationFile.exportPptx(p);
  const deckPath = path.resolve("output", "praetor-2-minute-pitch.pptx");
  await pptx.save(deckPath);

  await renderDeck(p, RENDERS);

  const imported = await PresentationFile.importPptx(await FileBlob.load(deckPath));
  await renderDeck(imported, PPTX_RENDERS);

  const layoutReports = [];
  for (const [i, s] of imported.slides.items.entries()) {
    layoutReports.push({
      slide: i + 1,
      elementCount: s.elements.items.length,
      textCount: s.elements.items.filter((e) => e.constructor?.name === "Text" || e.text !== undefined).length,
    });
  }
  await fs.writeFile(path.resolve("scratch", "pptx-inspection-summary.json"), JSON.stringify(layoutReports, null, 2));

  await makeMontage(RENDERS, path.resolve("scratch", "render-montage.png")).catch(() => false);
  await makeMontage(PPTX_RENDERS, path.resolve("scratch", "pptx-render-montage.png")).catch(() => false);

  console.log(JSON.stringify({
    deckPath,
    renders: RENDERS,
    pptxRenders: PPTX_RENDERS,
    slides: p.slides.items.length,
  }, null, 2));
}

await main();
