import { spawnSync } from "node:child_process";
import path from "node:path";
import process from "node:process";

const root = process.cwd();
const isWindows = process.platform === "win32";

function run(label, command, args, cwd) {
  console.log(`\n[praetor:test] ${label}`);
  const result = spawnSync(command, args, {
    cwd,
    env: process.env,
    stdio: "inherit",
    shell: false,
  });
  if (result.status !== 0) {
    process.exit(result.status ?? 1);
  }
}

function npmCommand(args) {
  if (!isWindows) return { command: "npm", args };
  return {
    command: process.env.ComSpec ?? "cmd.exe",
    args: ["/d", "/s", "/c", "npm", ...args],
  };
}

const python = isWindows ? "python" : "python3";

run("api unit tests", python, ["-m", "pytest"], path.join(root, "apps", "api"));
run("workflow unit tests", python, ["-m", "pytest"], path.join(root, "apps", "workflow"));
run("sandbox unit tests", python, ["-m", "pytest"], path.join(root, "apps", "sandbox"));

const webCwd = path.join(root, "apps", "web");
const webTypecheck = npmCommand(["run", "typecheck"]);
run("web typecheck", webTypecheck.command, webTypecheck.args, webCwd);
const webBuild = npmCommand(["run", "build"]);
run("web production build", webBuild.command, webBuild.args, webCwd);
