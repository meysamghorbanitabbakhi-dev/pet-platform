// `pnpm check:bff-coverage`. Answers a question Phase 1's release-contract
// work explicitly deferred (see the "Explicitly NOT doing in this phase"
// note in design-state-implementation-matrix.md's history): does every
// customer-facing backend operation the release contract cares about
// actually get called by the frontend, and does every BFF route genuinely
// forward to the real backend rather than silently stubbing a response?
//
// This is a different axis from check-openapi.mjs, which verifies the
// frontend's *type knowledge* of the backend spec is current. This script
// verifies the frontend's *wiring* -- that routes and calls are real, not
// just type-correct.
import { readFileSync, readdirSync } from "node:fs";
import { join, relative, resolve } from "node:path";
import { resolveBackendDir } from "./backend-dir.mjs";

const root = resolve(import.meta.dirname, "..");
const backendDir = resolveBackendDir();
const manifest = JSON.parse(
  readFileSync(resolve(backendDir, "release-contract.json"), "utf8"),
);
const openApiDoc = JSON.parse(
  readFileSync(resolve(backendDir, "openapi.json"), "utf8"),
);
const openApiPaths = openApiDoc.paths ?? {};

const differences = [];

// ---- 1. Every (method, path) backend.ts actually calls must be a real,
// currently-existing operation. backend.ts is the single choke point for
// every backend call the frontend makes (verified: every call site uses a
// literal path string, no dynamic path construction). ----
const backendTsPath = resolve(root, "src/lib/api/backend.ts");
const backendTsSource = readFileSync(backendTsPath, "utf8");
const callPattern = /backendClient\.(GET|POST|PUT|PATCH|DELETE)\(\s*"([^"]+)"/g;
const calledOperations = new Set();
for (const match of backendTsSource.matchAll(callPattern)) {
  const [, method, path] = match;
  calledOperations.add(`${method} ${path}`);
}
if (calledOperations.size === 0) {
  differences.push(
    "found zero backendClient.<METHOD>(...) calls in backend.ts -- the extraction pattern itself may be broken",
  );
}
for (const operation of calledOperations) {
  const [method, path] = operation.split(" ");
  if (!openApiPaths[path]?.[method.toLowerCase()]) {
    differences.push(
      `backend.ts calls ${operation}, which does not exist in the current backend/openapi.json`,
    );
  }
}

// ---- 2. Every release-contract-required operation (the curated set of
// customer-critical operations) must be reachable from at least one
// backend.ts call -- proving it is actually wired up for customer use, not
// merely present server-side. ----
for (const [method, path] of manifest.openapi.required_operations) {
  if (!calledOperations.has(`${method} ${path}`)) {
    differences.push(
      `required operation ${method} ${path} is never called by backend.ts (present in the backend but unreachable from the frontend)`,
    );
  }
}

// ---- 3. Every BFF route file must genuinely forward to the backend --
// catches a route that exists but was never wired to a real call (e.g. a
// stub returning hardcoded data). ----
function collectRouteFiles(dir) {
  const entries = readdirSync(dir, { withFileTypes: true });
  return entries.flatMap((entry) => {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) return collectRouteFiles(full);
    if (entry.name === "route.ts") return [full];
    return [];
  });
}
const bffDir = resolve(root, "src/app/api/bff");
const routeFiles = collectRouteFiles(bffDir);
const backendCallPattern = /\w+Backend\(|backendClient\./;
for (const file of routeFiles) {
  const source = readFileSync(file, "utf8");
  if (!backendCallPattern.test(source)) {
    differences.push(
      `BFF route ${relative(root, file)} never calls a *Backend() function or backendClient directly`,
    );
  }
}

if (differences.length) {
  console.error("BFF-TO-OPENAPI CONTRACT COVERAGE BLOCKED");
  differences.forEach((difference) => console.error(`- ${difference}`));
  process.exit(1);
}

console.log(
  JSON.stringify(
    {
      status: "ok",
      backend_operations_called: calledOperations.size,
      required_operations_covered: manifest.openapi.required_operations.length,
      bff_routes_checked: routeFiles.length,
    },
    null,
    2,
  ),
);
