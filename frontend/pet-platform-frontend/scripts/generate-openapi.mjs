import { execFileSync } from "node:child_process";
import { resolve } from "node:path";
import { resolveBackendDir } from "./backend-dir.mjs";

const backendDir = resolveBackendDir();
const args = ["exec", "openapi-typescript", resolve(backendDir, "openapi.json"), "-o", "src/generated/openapi.ts"];
execFileSync(process.platform === "win32" ? "pnpm.cmd" : "pnpm", args, {
  cwd: resolve(import.meta.dirname, ".."),
  stdio: "inherit",
});
