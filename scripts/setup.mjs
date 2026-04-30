import { spawnSync } from "node:child_process";
import process from "node:process";

const isWindows = process.platform === "win32";
const python = isWindows ? "python" : "python3";

const commands = [
  {
    label: "web dependencies",
    display: "npm install --prefix apps/web",
    command: "npm",
    args: ["install", "--prefix", "apps/web"],
  },
  {
    label: "api package and dev dependencies",
    display: 'python -m pip install -e "apps/api[dev]"',
    command: python,
    args: ["-m", "pip", "install", "-e", "apps/api[dev]"],
  },
  {
    label: "workflow package",
    display: "python -m pip install -e apps/workflow",
    command: python,
    args: ["-m", "pip", "install", "-e", "apps/workflow"],
  },
];

function commandFor(command, args) {
  if (!isWindows || command !== "npm") return { command, args };
  return {
    command: process.env.ComSpec ?? "cmd.exe",
    args: ["/d", "/s", "/c", command, ...args],
  };
}

for (const step of commands) {
  console.log(`\n[praetor:setup] ${step.label}`);
  console.log(`[praetor:setup] ${step.display}`);

  const runnable = commandFor(step.command, step.args);
  const result = spawnSync(runnable.command, runnable.args, {
    cwd: process.cwd(),
    env: process.env,
    stdio: "inherit",
    shell: false,
  });

  if (result.status !== 0) {
    process.exit(result.status ?? 1);
  }
}
