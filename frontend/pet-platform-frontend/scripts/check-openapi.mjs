import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { resolveBackendDir } from "./backend-dir.mjs";

const root = resolve(import.meta.dirname, "..");
const backendDir = resolveBackendDir();
const manifest = JSON.parse(readFileSync(resolve(backendDir, "release-contract.json"), "utf8"));
const openApiPath = resolve(backendDir, "openapi.json");
const raw = readFileSync(openApiPath);
const doc = JSON.parse(raw);
const schemas = doc.components?.schemas ?? {};
const paths = doc.paths ?? {};
const methods = new Set(["get", "post", "put", "patch", "delete", "options", "head", "trace"]);
const operations = new Set(Object.entries(paths).flatMap(([path, item]) =>
  Object.keys(item).filter((method) => methods.has(method)).map((method) => `${method.toUpperCase()} ${path}`)));
const differences = [];
const contract = manifest.openapi;
const actual = {
  sha256: createHash("sha256").update(raw).digest("hex"),
  path_count: Object.keys(paths).length,
  operation_count: operations.size,
  schema_count: Object.keys(schemas).length,
};
for (const [name, value] of Object.entries(actual)) {
  if (contract[name] !== value) differences.push(`${name} expected ${contract[name]} actual ${value}`);
}
for (const [method, path] of contract.required_operations) {
  if (!operations.has(`${method} ${path}`)) differences.push(`missing ${method} ${path}`);
}
for (const [name, properties] of Object.entries(contract.required_schema_properties)) {
  if (!schemas[name]) differences.push(`missing schema ${name}`);
  else for (const property of properties) if (!schemas[name].properties?.[property]) differences.push(`${name} missing ${property}`);
}
const property = (qualified) => {
  const [schema, name] = qualified.split(".");
  return schemas[schema]?.properties?.[name];
};
const variants = (value) => [value, ...(value?.anyOf ?? []), ...(value?.oneOf ?? [])].filter(Boolean);
for (const [qualified, expected] of Object.entries(contract.required_enums)) {
  const values = variants(property(qualified)).flatMap((entry) => entry.enum ?? []);
  for (const value of expected) if (!values.includes(value)) differences.push(`${qualified} enum missing ${value}`);
}
for (const [qualified, expected] of Object.entries(contract.required_patterns)) {
  if (property(qualified)?.pattern !== expected) differences.push(`${qualified} pattern mismatch`);
}
for (const [qualified, expected] of Object.entries(contract.required_constants)) {
  if (!variants(property(qualified)).some((entry) => entry.const === expected)) differences.push(`${qualified} constant mismatch`);
}
if (differences.length) {
  console.error("CONTRACT BLOCKED: backend OpenAPI is incompatible");
  differences.forEach((difference) => console.error(`- ${difference}`));
  process.exit(1);
}

const generatedPath = resolve(root, "src/generated/openapi.ts");
const tempDir = mkdtempSync(join(tmpdir(), "pet-openapi-"));
const tempOut = join(tempDir, "openapi.ts");
try {
  execFileSync(process.platform === "win32" ? "pnpm.cmd" : "pnpm",
    ["exec", "openapi-typescript", openApiPath, "-o", tempOut], { cwd: root, stdio: "pipe" });
  const current = readFileSync(generatedPath, "utf8").replace(/\r\n/g, "\n");
  const fresh = readFileSync(tempOut, "utf8").replace(/\r\n/g, "\n");
  if (current !== fresh) throw new Error("generated OpenAPI types drifted; run pnpm generate:api");
} finally {
  rmSync(tempDir, { recursive: true, force: true });
}
console.log(JSON.stringify({ status: "compatible", alembic_heads: manifest.alembic.heads, ...actual }, null, 2));
