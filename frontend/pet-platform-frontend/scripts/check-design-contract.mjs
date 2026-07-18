import { createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import vm from "node:vm";

const root = resolve(import.meta.dirname, "..");
const contractDir = resolve(root, "..", "frontend-coding-contract");
const manifestPath = resolve(contractDir, "canonical-manifest.sha256");
const manifestLines = readFileSync(manifestPath, "utf8").trim().split("\n").filter(Boolean);

const differences = [];

for (const line of manifestLines) {
  const match = line.match(/^([0-9a-f]{64})\s+\*?(.+)$/);
  if (!match) {
    differences.push(`unparseable canonical-manifest.sha256 line: ${line}`);
    continue;
  }
  const [, expectedHash, relativePath] = match;
  const filePath = resolve(contractDir, relativePath);
  if (!existsSync(filePath)) {
    differences.push(`missing canonical file: ${relativePath}`);
    continue;
  }
  const actualHash = createHash("sha256").update(readFileSync(filePath)).digest("hex");
  if (actualHash !== expectedHash) {
    differences.push(`checksum mismatch: ${relativePath}`);
  }
}

const screenDataPath = resolve(contractDir, "design-pages/gate5.2c-screen-data.v3.1.js");
const sandbox = { window: {} };
vm.createContext(sandbox);
vm.runInContext(readFileSync(screenDataPath, "utf8"), sandbox, { filename: screenDataPath });
const screens = sandbox.window.GATE52C_SCREENS ?? [];
const journeys = sandbox.window.GATE52C_JOURNEYS ?? [];
const screenIds = new Set(screens.map((screen) => screen.id));
const journeyIds = new Set(journeys.map((journey) => journey.id));

if (screens.length !== screenIds.size) {
  differences.push(
    `duplicate state ids in gate5.2c-screen-data.v3.1.js: ${screens.length} entries, ${screenIds.size} unique`,
  );
}
if (screenIds.size !== 152) {
  differences.push(`expected exactly 152 unique state ids, found ${screenIds.size}`);
}
if (journeys.length !== journeyIds.size) {
  differences.push(
    `duplicate journey ids in gate5.2c-screen-data.v3.1.js: ${journeys.length} entries, ${journeyIds.size} unique`,
  );
}
if (journeyIds.size !== 11) {
  differences.push(`expected exactly 11 unique journey ids, found ${journeyIds.size}`);
}

if (differences.length) {
  console.error("DESIGN CONTRACT BLOCKED");
  differences.forEach((difference) => console.error(`- ${difference}`));
  process.exit(1);
}

console.log(
  JSON.stringify(
    {
      status: "ok",
      canonical_files: manifestLines.length,
      states: screenIds.size,
      journeys: journeyIds.size,
    },
    null,
    2,
  ),
);
