import { execFileSync } from "node:child_process";

// Seeds catalog data directly into the ephemeral Postgres container
// scripts/e2e-real-backend.mjs starts (see its PG_CONTAINER/PG_PORT) via
// `docker exec ... psql`, not a Node Postgres client library -- this repo
// has no such dependency, and shelling out to the same `docker` binary the
// harness itself already uses avoids adding one just for E2E seeding.
// A freshly migrated database has no catalog offers (see
// shop-discovery.spec.ts), so any journey past shop discovery needs this.
// Real end-to-end still holds: every subsequent step in a test still goes
// through the actual API/UI, this only substitutes for the operator
// console screens this repo does not have a customer-observable UI for
// (supplier/product/offer authoring).
const PG_CONTAINER = "pet-platform-e2e-postgres";

function psql(sql: string): string {
  // -q suppresses psql's own "INSERT 0 1" command-tag line -- without it,
  // that line lands on stdout right alongside a RETURNING clause's actual
  // result, and got silently concatenated into what callers here treat as
  // "the returned id."
  return execFileSync(
    "docker",
    [
      "exec",
      PG_CONTAINER,
      "psql",
      "-q",
      "-U",
      "pet_platform",
      "-d",
      "pet_platform",
      "-tA",
      "-c",
      sql,
    ],
    { encoding: "utf8" },
  ).trim();
}

export interface SeededOffer {
  offerId: string;
  productId: string;
  title: string;
  priceIrr: number;
}

// sourcing_route='individual' deliberately -- avoids also having to seed
// default_batch_threshold_quantity (required for 'aggregated' as of the
// gap-closure program's Workstream 6 fix) for a fixture whose only job is
// to exist as a purchasable offer, not to exercise batch pooling.
export function seedFullPaymentOffer(priceIrr = 1_250_000): SeededOffer {
  const token = Math.random().toString(36).slice(2, 10);
  const title = `غذای گربه پرمیوم ${token}`;
  const supplierId = psql(
    `INSERT INTO catalog_suppliers (id, internal_name, country_code, active, created_at, updated_at) ` +
      `VALUES (gen_random_uuid(), 'e2e-supplier-${token}', 'IR', true, now(), now()) RETURNING id`,
  );
  const productId = psql(
    `INSERT INTO catalog_products (id, name_fa, status, created_at, updated_at) ` +
      `VALUES (gen_random_uuid(), '${title}', 'active', now(), now()) RETURNING id`,
  );
  const offerId = psql(
    `INSERT INTO catalog_offers (` +
      `id, product_id, supplier_id, sku, title_fa, unit_label_fa, price_irr, status, ` +
      `stock_posture, sourcing_capacity_status, sourcing_route, mode, ` +
      `minimum_shelf_life_months, created_at, updated_at` +
      `) VALUES (` +
      `gen_random_uuid(), '${productId}', '${supplierId}', 'E2E-${token}', '${title}', 'بسته', ` +
      `${priceIrr}, 'active', 'sourced_after_payment', 'open', 'individual', 'full_payment', ` +
      `6, now(), now()` +
      `) RETURNING id`,
  );
  return { offerId, productId, title, priceIrr };
}

// This harness's ephemeral Postgres and its data are shared across every
// spec file in one `pnpm test:e2e:real-backend` run (there is no
// per-test-file database reset) -- shop-discovery.spec.ts specifically
// asserts the catalog is empty, so a seeded offer left `status='active'`
// would break it if that spec happens to run afterward. Retiring rather
// than deleting: an order may have already been placed against this
// offer by the time cleanup runs, and orders_order_lines.offer_id has no
// ON DELETE behavior defined for that FK.
export function retireOffer(offerId: string): void {
  psql(`UPDATE catalog_offers SET status = 'retired' WHERE id = '${offerId}'`);
}

// There is no self-service operator signup: OTP verification always
// creates identity_type='customer' for a mobile it has not seen before
// (app/modules/identity/otp.py's _get_or_create_customer_identity uses
// ON CONFLICT DO NOTHING on mobile_e164 -- an existing row, of any type,
// is left as-is and simply returned). Pre-seeding an operator row here
// and then logging in through the ordinary OTP UI is therefore a real
// exercise of that exact code path, not a bypass of it: the same
// request/verify flow a customer uses is what authenticates this
// operator, it just resolves to a pre-existing row instead of creating
// a new one.
export function seedOperatorIdentity(mobileE164: string): void {
  psql(
    `INSERT INTO identity_auth_identities (id, identity_type, mobile_e164, status, created_at) ` +
      `VALUES (gen_random_uuid(), 'operator', '${mobileE164}', 'active', now())`,
  );
}
