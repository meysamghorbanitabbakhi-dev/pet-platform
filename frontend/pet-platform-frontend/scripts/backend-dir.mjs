import { existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

export function resolveBackendDir() {
  const scriptDir = dirname(fileURLToPath(import.meta.url));
  const frontendDir = resolve(scriptDir, "..");
  const attempted = [
    process.env.BACKEND_DIR && resolve(frontendDir, process.env.BACKEND_DIR),
    resolve(frontendDir, "..", "..", "backend"),
    resolve(frontendDir, "..", "backend"),
  ].filter(Boolean);
  for (const candidate of attempted) {
    if (existsSync(resolve(candidate, "release-contract.json")))
      return candidate;
  }
  throw new Error(
    `Unable to resolve backend directory. Attempted:\n${attempted.map((path) => `- ${path}`).join("\n")}`,
  );
}
