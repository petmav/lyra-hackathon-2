import { spawn } from "node:child_process";
import process from "node:process";
import path from "node:path";

const mode = process.argv[2] ?? "demo";
const target = process.argv[3] ?? "all";

if (["--help", "-h", "help"].includes(mode)) {
  console.log(`
Praetor runtime scripts

Usage:
  npm run demo              Start API + web in demo mode (in-memory data)
  npm run prod              Start API + web in production mode (Postgres data backend)
  npm run demo:api          Start only the API in demo mode
  npm run prod:api          Start only the API in production mode
  npm run demo:web          Start only the web app in dev mode
  npm run prod:web          Start only the built web app

Environment:
  PRAETOR_API_RELOAD=1      Enable Uvicorn reload for API scripts
  NEXT_DIST_DIR=.next-alt   Override Next build/start output directory
`);
  process.exit(0);
}

if (!["demo", "production"].includes(mode)) {
  console.error(`Unknown mode "${mode}". Use "demo" or "production".`);
  process.exit(1);
}

if (!["all", "api", "web"].includes(target)) {
  console.error(`Unknown target "${target}". Use "all", "api", or "web".`);
  process.exit(1);
}

const isWindows = process.platform === "win32";
const pythonBin = isWindows ? "python" : "python3";
const root = process.cwd();

const sharedEnv = {
  ...process.env,
  PRAETOR_DATA_MODE: mode,
  PRAETOR_SEED_DEMO_DATA: process.env.PRAETOR_SEED_DEMO_DATA ?? (mode === "demo" ? "1" : "0"),
  NEXT_PUBLIC_PRAETOR_DATA_MODE: mode,
  NEXT_PUBLIC_DATA_SOURCE: process.env.NEXT_PUBLIC_DATA_SOURCE ?? (mode === "demo" ? "hybrid" : "api"),
  NEXT_PUBLIC_API_BASE: process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000",
  NEXT_PUBLIC_DEV_BEARER: process.env.NEXT_PUBLIC_DEV_BEARER ?? "dev",
  NEXT_PUBLIC_API_TOKEN: process.env.NEXT_PUBLIC_API_TOKEN ?? process.env.NEXT_PUBLIC_DEV_BEARER ?? "dev",
};

const children = [];

function start(label, command, args, cwd, env = sharedEnv) {
  console.log(`[praetor:${mode}] starting ${label}: ${command} ${args.join(" ")}`);
  const child = spawn(command, args, {
    cwd,
    env,
    stdio: "inherit",
    shell: false,
  });
  child.on("exit", (code, signal) => {
    if (shuttingDown) return;
    console.log(`[praetor:${mode}] ${label} exited with ${signal ?? code}`);
    shutdown(code ?? 1);
  });
  children.push(child);
}

function npmCommand(args) {
  if (!isWindows) return { command: "npm", args };
  return {
    command: process.env.ComSpec ?? "cmd.exe",
    args: ["/d", "/s", "/c", "npm", ...args],
  };
}

let shuttingDown = false;

function shutdown(code = 0) {
  shuttingDown = true;
  for (const child of children) {
    if (!child.killed) child.kill();
  }
  process.exit(code);
}

process.on("SIGINT", () => shutdown(0));
process.on("SIGTERM", () => shutdown(0));

if (target === "all" || target === "api") {
  const apiArgs = [
    "-m",
    "praetor_api.run_server",
  ];
  start("api", pythonBin, apiArgs, path.join(root, "apps", "api"));
}

if (target === "all" || target === "web") {
  const script = mode === "demo" ? "dev" : "start";
  const webCommand = npmCommand(["run", script]);
  start("web", webCommand.command, webCommand.args, path.join(root, "apps", "web"), {
    ...sharedEnv,
    NEXT_DIST_DIR: process.env.NEXT_DIST_DIR ?? ".next",
  });
}
