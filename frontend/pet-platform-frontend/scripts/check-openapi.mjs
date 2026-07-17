import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import {
  existsSync,
  mkdtempSync,
  readFileSync,
  readdirSync,
  rmSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

const root = process.cwd();
const openApiPath = resolve(root, "../../backend/openapi.json");
const migrationsPath = resolve(root, "../../backend/migrations/versions");
const generatedPath = resolve(root, "src/generated/openapi.ts");
const requiredHead = "20260716_0023";
const requiredOperationCount = 133;
const requiredPolicyFields = 27;
const requiredSchemas = [
  "JourneyContentResponse",
  "JourneyStepResponse",
  "JourneyAnswerOptionResponse",
  "JourneyCheckInBody",
  "ReorderOptionResponse",
];
const requiredPath = "/api/v1/pet-life/pets/{pet_id}/journey-offers";

function fail(message, details = []) {
  console.error(`CONTRACT BLOCKED: ${message}`);
  for (const detail of details) console.error(`- ${detail}`);
  process.exit(1);
}

if (!existsSync(openApiPath)) fail("backend/openapi.json is missing");
if (!existsSync(generatedPath))
  fail("generated OpenAPI types are missing; run pnpm generate:api");

const raw = readFileSync(openApiPath);
const doc = JSON.parse(raw.toString("utf8"));
const hash = createHash("sha256").update(raw).digest("hex");
const schemas = doc.components?.schemas ?? {};
const paths = doc.paths ?? {};
const operations = Object.entries(paths).flatMap(([path, methods]) =>
  Object.keys(methods)
    .filter((method) =>
      [
        "get",
        "post",
        "put",
        "patch",
        "delete",
        "options",
        "head",
        "trace",
      ].includes(method),
    )
    .map((method) => `${method.toUpperCase()} ${path}`),
);
const policyFields = Object.keys(schemas.PolicyResponse?.properties ?? {});
const missingSchemas = requiredSchemas.filter((name) => !schemas[name]);

const revisions = new Map();
const downRevisions = new Set();
if (existsSync(migrationsPath)) {
  for (const file of readdirSync(migrationsPath).filter((name) =>
    name.endsWith(".py"),
  )) {
    const text = readFileSync(join(migrationsPath, file), "utf8");
    const revision = text.match(/revision:\s*str\s*=\s*"([^"]+)"/)?.[1];
    const downRevision = text.match(
      /down_revision:\s*str\s*\|\s*None\s*=\s*"([^"]+)"/,
    )?.[1];
    if (revision) revisions.set(revision, file);
    if (downRevision) downRevisions.add(downRevision);
  }
}
const heads = [...revisions.keys()]
  .filter((revision) => !downRevisions.has(revision))
  .sort();
const observedHead = heads.at(-1) ?? "unknown";

const differences = [];
if (observedHead < requiredHead)
  differences.push(
    `Alembic head ${observedHead} is older than ${requiredHead}`,
  );
if (operations.length < requiredOperationCount)
  differences.push(
    `operation count ${operations.length} is below ${requiredOperationCount}`,
  );
if (policyFields.length !== requiredPolicyFields)
  differences.push(
    `PolicyResponse has ${policyFields.length} fields, expected ${requiredPolicyFields}`,
  );
if (missingSchemas.length)
  differences.push(`missing schemas: ${missingSchemas.join(", ")}`);
if (!paths[requiredPath]?.get) differences.push(`missing GET ${requiredPath}`);
if (
  !operations.every((op) => op.includes("/api/v1/") || op.includes("/health/"))
) {
  differences.push(
    "one or more protected paths are missing the /api/v1 prefix",
  );
}
if (differences.length) fail("backend OpenAPI is incompatible", differences);

const tempDir = mkdtempSync(join(tmpdir(), "pet-openapi-"));
const tempOut = join(tempDir, "openapi.ts");
try {
  if (process.platform === "win32") {
    execFileSync(
      "cmd.exe",
      [
        "/d",
        "/s",
        "/c",
        `pnpm exec openapi-typescript ${openApiPath} -o ${tempOut}`,
      ],
      {
        cwd: root,
        stdio: "pipe",
      },
    );
  } else {
    execFileSync(
      "pnpm",
      ["exec", "openapi-typescript", openApiPath, "-o", tempOut],
      {
        cwd: root,
        stdio: "pipe",
      },
    );
  }
  const current = readFileSync(generatedPath, "utf8").replace(/\r\n/g, "\n");
  const fresh = readFileSync(tempOut, "utf8").replace(/\r\n/g, "\n");
  if (current !== fresh)
    fail("generated OpenAPI types drifted; run pnpm generate:api");
} finally {
  rmSync(tempDir, { recursive: true, force: true });
}

console.log(
  JSON.stringify(
    {
      status: "compatible",
      alembic_head: observedHead,
      openapi_sha256: hash,
      operation_count: operations.length,
      policy_field_count: policyFields.length,
      required_schemas_present: requiredSchemas,
      journey_offer_path: requiredPath,
    },
    null,
    2,
  ),
);
