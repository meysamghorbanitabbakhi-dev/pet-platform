import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
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
const requiredHead = "20260716_0024";
const requiredOperationCount = 144;

const requiredOperations = [
  ["POST", "/api/v1/auth/otp/request"],
  ["POST", "/api/v1/auth/otp/verify"],
  ["POST", "/api/v1/auth/session/refresh"],
  ["POST", "/api/v1/auth/session/logout"],
  ["GET", "/api/v1/system/policies"],
  ["GET", "/api/v1/me/context"],
  ["GET", "/api/v1/catalog/offers"],
  ["GET", "/api/v1/catalog/offers/{offer_id}"],
  ["GET", "/api/v1/pet-life/households/{household_id}/addresses"],
  ["POST", "/api/v1/checkout/orders"],
  ["POST", "/api/v1/orders/{order_id}/payments/zarinpal"],
  ["GET", "/api/v1/payments/zarinpal/callback"],
  ["GET", "/api/v1/orders/{order_id}"],
  ["GET", "/api/v1/orders/{order_id}/journey"],
  ["PUT", "/api/v1/orders/{order_id}/pet-plan"],
  ["POST", "/api/v1/pet-life/households"],
  ["POST", "/api/v1/pet-life/households/{household_id}/pets"],
  ["POST", "/api/v1/pet-life/households/{household_id}/addresses"],
  ["PATCH", "/api/v1/pet-life/pets/{pet_id}/profile"],
  ["GET", "/api/v1/pet-life/pets/{pet_id}/today"],
  ["GET", "/api/v1/pet-life/pets/{pet_id}/journey-offers"],
  ["GET", "/api/v1/pet-life/inventory/{unit_id}"],
  ["POST", "/api/v1/pet-life/inventory/{unit_id}/open"],
];

const requiredSchemaProperties = {
  AddressBody: [
    "label",
    "recipient_name",
    "recipient_mobile",
    "province",
    "city",
    "address_line",
  ],
  AddressResponse: [
    "id",
    "label",
    "recipient_name",
    "recipient_mobile",
    "province",
    "city",
    "address_line",
  ],
  CheckoutBody: ["household_id", "address_id", "items"],
  CheckoutItemBody: ["offer_id", "quantity"],
  FoodEstimateResponse: ["id", "confidence", "basis"],
  HouseholdBody: ["name"],
  InventoryDetailResponse: [
    "id",
    "label",
    "source",
    "state",
    "household_id",
    "assignments",
    "shares_known",
  ],
  MeContextResponse: [
    "identity",
    "households",
    "pets",
    "onboarding",
    "capabilities",
  ],
  OnboardingRequirementsResponse: [
    "needs_household",
    "needs_pet",
    "needs_address",
  ],
  OpenInventoryBody: ["feeding_context", "remaining", "remaining_grams"],
  OtpRequestBody: ["mobile"],
  OtpRequestResponse: ["challenge_id", "expires_in_seconds"],
  OtpVerifyBody: ["challenge_id", "code"],
  OtpVerifyResponse: ["state"],
  OfferDetailResponse: [
    "id",
    "media",
    "availability",
    "price_irr",
    "supplier_country_code",
    "authenticity",
    "minimum_shelf_life_months_at_delivery",
    "reference_price_reviewed_at",
    "saving_percent",
  ],
  OrderDetailResponse: [
    "id",
    "status",
    "currency",
    "merchandise_total_irr",
    "delivery_address",
    "lines",
    "policies",
  ],
  OrderJourneyResponse: ["order_id", "status", "timeline", "sourced_units"],
  OrderLineResponse: [
    "id",
    "offer_id",
    "quantity",
    "unit_price_irr",
    "line_total_irr",
    "planned_pet_ids",
  ],
  OrderPetPlanBody: ["lines"],
  OrderPetPlanLineBody: ["order_line_id", "pet_ids"],
  OrderPolicyFieldsResponse: ["delivery_commitment_hours"],
  OrderResponse: ["id", "status", "currency", "merchandise_total_irr"],
  PaymentCallbackResponse: ["state", "order_id", "delivery_commitment_at"],
  PaymentRedirectResponse: ["attempt_id", "redirect_url"],
  PaymentRequestBody: ["callback_url"],
  PetBody: ["name", "species"],
  PetProfilePatch: ["birth_date", "birth_date_precision"],
  PolicyResponse: [
    "currency_code",
    "customer_display_currency_code",
    "customer_display_unit",
    "irr_per_customer_display_unit",
    "delivery_commitment_hours",
    "full_payment_only",
    "reserve_now_enabled",
    "care_journey_delivery_enabled",
    "semantic_level_estimation_enabled",
    "sourcing_start_rule",
  ],
  RefreshBody: ["refresh_token"],
  ReorderOptionResponse: ["offer_id", "sku", "available"],
  TokenResponse: ["access_token", "refresh_token", "expires_in_seconds"],
};

const requiredEnums = {
  "ContextPetSummary.species": ["dog", "cat"],
  "OfferDetailResponse.availability": ["available", "temporarily_unavailable"],
  "OpenInventoryBody.feeding_context": ["exclusive", "mixed", "unknown"],
  "OtpVerifyResponse.state": [
    "verified",
    "invalid",
    "expired",
    "consumed",
    "locked",
    "not_found",
  ],
  "PetSummary.species": ["dog", "cat"],
};

const requiredPatterns = {
  "PetBody.species": "^(dog|cat)$",
};

const requiredConstStates = {
  TodayFoodEstimated: "estimated",
  TodayFoodIncoming: "incoming",
  TodayFoodNone: "none",
  TodayFoodUnavailable: "unavailable",
  TodayFoodUnknownEstimate: "unknown_estimate",
  TodayFoodUnopened: "unopened",
};

const requiredConstProperties = {
  "OfferDetailResponse.authenticity": "supplier_verified",
};

function fail(message, details = []) {
  console.error(`CONTRACT BLOCKED: ${message}`);
  for (const detail of details) console.error(`- ${detail}`);
  process.exit(1);
}

function schemaProperty(schema, property) {
  return schema?.properties?.[property];
}

function enumValues(property) {
  if (!property) return [];
  if (Array.isArray(property.enum)) return property.enum;
  if (Array.isArray(property.anyOf)) {
    return property.anyOf.flatMap((entry) => entry.enum ?? []);
  }
  if (Array.isArray(property.oneOf)) {
    return property.oneOf.flatMap((entry) => entry.enum ?? []);
  }
  return [];
}

function propertyHasConst(property, value) {
  if (!property) return false;
  if (property.const === value) return true;
  return [property, ...(property.anyOf ?? []), ...(property.oneOf ?? [])].some(
    (entry) => entry.const === value,
  );
}

function parseRevision(text) {
  return (
    text.match(/^revision\s*:\s*str\s*=\s*["']([^"']+)["']/m)?.[1] ??
    text.match(/^revision\s*=\s*["']([^"']+)["']/m)?.[1] ??
    null
  );
}

function parseDownRevisions(text) {
  const assignment =
    text.match(/^down_revision\s*:[^=]+=\s*(.+)$/m)?.[1] ??
    text.match(/^down_revision\s*=\s*(.+)$/m)?.[1] ??
    "";
  if (!assignment || assignment.trim().startsWith("None")) return [];
  return [...assignment.matchAll(/["']([^"']+)["']/g)].map((match) => match[1]);
}

function migrationGraph() {
  const revisions = new Map();
  const downRevisionSet = new Set();
  if (!existsSync(migrationsPath)) return { heads: [], revisions };

  for (const file of readdirSync(migrationsPath).filter((name) =>
    name.endsWith(".py"),
  )) {
    const text = readFileSync(join(migrationsPath, file), "utf8");
    const revision = parseRevision(text);
    if (!revision) continue;
    const downRevisions = parseDownRevisions(text);
    revisions.set(revision, { downRevisions, file });
    for (const downRevision of downRevisions) downRevisionSet.add(downRevision);
  }

  const heads = [...revisions.keys()]
    .filter((revision) => !downRevisionSet.has(revision))
    .sort();
  return { heads, revisions };
}

function reachesRequiredHead(revisions, start, target, visited = new Set()) {
  if (start === target) return true;
  if (visited.has(start)) return false;
  visited.add(start);
  const node = revisions.get(start);
  if (!node) return false;
  return node.downRevisions.some((downRevision) =>
    reachesRequiredHead(revisions, downRevision, target, visited),
  );
}

if (!existsSync(openApiPath)) fail("backend/openapi.json is missing");
if (!existsSync(generatedPath)) {
  fail("generated OpenAPI types are missing; run pnpm generate:api");
}

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

const differences = [];
const { heads, revisions } = migrationGraph();
if (!revisions.has(requiredHead)) {
  differences.push(`required Alembic revision ${requiredHead} is missing`);
}
if (
  revisions.has(requiredHead) &&
  !heads.some((head) => reachesRequiredHead(revisions, head, requiredHead))
) {
  differences.push(
    `migration heads ${heads.join(", ") || "unknown"} do not descend from ${requiredHead}`,
  );
}
if (operations.length < requiredOperationCount) {
  differences.push(
    `operation count ${operations.length} is below ${requiredOperationCount}`,
  );
}

for (const [method, path] of requiredOperations) {
  if (!paths[path]?.[method.toLowerCase()]) {
    differences.push(`missing ${method} ${path}`);
  }
}

for (const [schemaName, properties] of Object.entries(
  requiredSchemaProperties,
)) {
  const schema = schemas[schemaName];
  if (!schema) {
    differences.push(`missing schema ${schemaName}`);
    continue;
  }
  for (const property of properties) {
    if (!schemaProperty(schema, property)) {
      differences.push(`schema ${schemaName} missing property ${property}`);
    }
  }
}

for (const [qualifiedProperty, expectedValues] of Object.entries(
  requiredEnums,
)) {
  const [schemaName, propertyName] = qualifiedProperty.split(".");
  const actualValues = enumValues(
    schemaProperty(schemas[schemaName], propertyName),
  );
  for (const expectedValue of expectedValues) {
    if (!actualValues.includes(expectedValue)) {
      differences.push(
        `${qualifiedProperty} enum missing value ${expectedValue}`,
      );
    }
  }
}

for (const [qualifiedProperty, expectedPattern] of Object.entries(
  requiredPatterns,
)) {
  const [schemaName, propertyName] = qualifiedProperty.split(".");
  const property = schemaProperty(schemas[schemaName], propertyName);
  if (property?.pattern !== expectedPattern) {
    differences.push(`${qualifiedProperty} pattern must be ${expectedPattern}`);
  }
}

for (const [schemaName, expectedState] of Object.entries(requiredConstStates)) {
  if (
    !propertyHasConst(
      schemaProperty(schemas[schemaName], "state"),
      expectedState,
    )
  ) {
    differences.push(`${schemaName}.state const must be ${expectedState}`);
  }
}

for (const [qualifiedProperty, expectedValue] of Object.entries(
  requiredConstProperties,
)) {
  const [schemaName, propertyName] = qualifiedProperty.split(".");
  if (
    !propertyHasConst(
      schemaProperty(schemas[schemaName], propertyName),
      expectedValue,
    )
  ) {
    differences.push(`${qualifiedProperty} const must be ${expectedValue}`);
  }
}

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
  if (current !== fresh) {
    fail("generated OpenAPI types drifted; run pnpm generate:api");
  }
} finally {
  rmSync(tempDir, { recursive: true, force: true });
}

console.log(
  JSON.stringify(
    {
      status: "compatible",
      alembic_heads: heads,
      required_alembic_head: requiredHead,
      openapi_sha256: hash,
      operation_count: operations.length,
      policy_field_count: Object.keys(schemas.PolicyResponse?.properties ?? {})
        .length,
      required_operations: requiredOperations.map(
        ([method, path]) => `${method} ${path}`,
      ),
      schema_property_checks: Object.keys(requiredSchemaProperties),
    },
    null,
    2,
  ),
);
