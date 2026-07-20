// `pnpm test:e2e:real-backend`. Orchestrates a genuinely live backend for
// tests/e2e-real-backend: ephemeral Postgres + Redis (distinct ports/names
// from both the developer's persistent docker-compose stack and the
// K10 pytest ephemeral containers, so none of the three ever collide),
// migrated, with a real `uvicorn app.main:app` process, then runs Playwright
// against it with playwright.real-backend.config.ts. Always tears down the
// backend process and containers, success or failure.
import { execFileSync, spawn } from "node:child_process";
import { cpSync, existsSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { resolveBackendDir } from "./backend-dir.mjs";

const root = resolve(import.meta.dirname, "..");
const backendDir = resolveBackendDir();

const PG_CONTAINER = "pet-platform-e2e-postgres";
const REDIS_CONTAINER = "pet-platform-e2e-redis";
const PG_PORT = 55433;
const REDIS_PORT = 56380;
const BACKEND_PORT = 8010;
const DATABASE_URL = `postgresql+asyncpg://pet_platform:pet_platform@127.0.0.1:${PG_PORT}/pet_platform`;
// Real request traffic connects as this separate, unprivileged role
// instead of DATABASE_URL's superuser one (row-level security is
// unconditionally bypassed for superusers in Postgres, with no
// override -- see backend ADR-011's amendment). Migration
// 20260720_0040 creates this role as part of `alembic upgrade head`
// below; it must resolve to the same ephemeral Postgres container the
// rest of this harness uses, not the default placeholder host/port
// Settings.database_app_url falls back to.
const DATABASE_APP_URL = `postgresql+asyncpg://pet_platform_app:pet_platform_app@127.0.0.1:${PG_PORT}/pet_platform`;
const REDIS_URL = `redis://127.0.0.1:${REDIS_PORT}/0`;
const mediaRoot = resolve(root, ".e2e-real-backend-media");
const distDir = ".next-e2e-real-backend";
const distDirAbs = resolve(root, distDir);
// Written every time the backend's dev-console OTP fallback logs a code
// (app/integrations/otp/dev_console.py logs to stderr, never an API
// response), so tests/e2e-real-backend specs can read the code Playwright
// itself has no other way to obtain. Gitignored; last-write-wins is fine
// since e2e-real-backend.mjs runs one test worker at a time.
const otpLogPath = resolve(root, ".e2e-real-backend-otp.json");
const otpLinePattern =
  /OTP dev console fallback: mobile=(\S+) code=(\S+) correlation_id=(\S+)/;

function run(command, args, options = {}) {
  console.log(`+ ${command} ${args.join(" ")}`);
  execFileSync(command, args, { stdio: "inherit", ...options });
}

// execFileSync blocks the Node event loop for its entire duration -- fine
// for docker/alembic, which run before uvicorn exists, but fatal for any
// step that needs to run *while* uvicorn is alive and watchForOtpCodes'
// `data` handlers need to fire: a blocked event loop cannot process the
// child process's piped stdout/stderr, so any log line (like an OTP code)
// written during a synchronous call is invisible until it returns -- by
// which point a polling test has already timed out. Used for `next build`
// and the Playwright run, both of which overlap with the live backend.
function runAsync(command, args, options = {}) {
  console.log(`+ ${command} ${args.join(" ")}`);
  return new Promise((resolvePromise, rejectPromise) => {
    const child = spawn(command, args, { stdio: "inherit", ...options });
    child.on("error", rejectPromise);
    child.on("exit", (code) => {
      if (code === 0) resolvePromise();
      else rejectPromise(new Error(`${command} exited with code ${code}`));
    });
  });
}

function dockerRmForce(name) {
  try {
    execFileSync("docker", ["rm", "-f", name], { stdio: "pipe" });
  } catch {
    // already absent -- fine
  }
}

async function waitForHttp(url, { timeoutMs = 30_000, intervalMs = 500 } = {}) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(url);
      if (response.ok) return;
    } catch {
      // not up yet
    }
    await new Promise((resolveDelay) => setTimeout(resolveDelay, intervalMs));
  }
  throw new Error(`timed out waiting for ${url}`);
}

function watchForOtpCodes(stream, echoTo) {
  let buffer = "";
  stream.on("data", (chunk) => {
    echoTo.write(chunk);
    buffer += chunk.toString();
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      const match = line.match(otpLinePattern);
      if (!match) continue;
      const [, mobile, code, correlationId] = match;
      writeFileSync(
        otpLogPath,
        JSON.stringify({ mobile, code, correlationId, capturedAt: Date.now() }),
      );
    }
  });
}

async function waitForPostgres(timeoutMs = 30_000, intervalMs = 500) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      execFileSync(
        "docker",
        ["exec", PG_CONTAINER, "pg_isready", "-U", "pet_platform"],
        { stdio: "pipe" },
      );
      return;
    } catch {
      await new Promise((resolveDelay) => setTimeout(resolveDelay, intervalMs));
    }
  }
  throw new Error("timed out waiting for postgres readiness");
}

const backendEnv = {
  ...process.env,
  // Otherwise Python detects the piped (non-TTY) stdout/stderr and switches
  // to block buffering, so uvicorn's log lines -- including the OTP code --
  // never reach watchForOtpCodes' `data` handler in time (or at all, until
  // the buffer happens to fill or the process exits).
  PYTHONUNBUFFERED: "1",
  APP_ENV: "development",
  LOG_LEVEL: "INFO",
  DATABASE_URL,
  DATABASE_APP_URL,
  REDIS_URL,
  MEDIA_ROOT: mediaRoot,
  JWT_SECRET: "e2e-real-backend-secret-at-least-32-characters",
  WEBHOOK_SECRET: "e2e-real-backend-secret-at-least-32-characters",
  METRICS_BEARER_TOKEN: "e2e-real-backend-secret-at-least-32-characters",
  MAX_REQUEST_BODY_BYTES: "12000000",
  PET_ASSET_MAX_BYTES: "10485760",
  PET_HEALTH_CONSENT_POLICY_VERSION: "1.0",
  SECURITY_HSTS_ENABLED: "false",
  CURRENCY_CODE: "IRR",
  DELIVERY_COMMITMENT_HOURS: "366",
  LATE_COMPENSATION_BASIS_POINTS: "500",
  WALLET_CREDIT_EXPIRY_MONTHS: "3",
  FULL_PAYMENT_ONLY: "true",
  RESERVE_NOW_ENABLED: "false",
  REFUND_SELF_SERVICE_ENABLED: "false",
  REPLACEMENT_SELF_SERVICE_ENABLED: "false",
  SUBSTITUTION_SELF_SERVICE_ENABLED: "false",
  DELAY_COMPENSATION_CUSTOMER_VISIBLE: "false",
  CARE_JOURNEY_DELIVERY_ENABLED: "true",
  PUSH_NOTIFICATIONS_ENABLED: "false",
  SEMANTIC_LEVEL_ESTIMATION_ENABLED: "true",
  REORDER_SAFETY_BUFFER_DAYS: "3",
  REORDER_SNOOZE_EARLY_BREAK_WORSENING_DAYS: "2",
  STORAGE_BACKEND: "filesystem",
  ZARINPAL_SANDBOX: "true",
  ZARINPAL_MERCHANT_ID: "",
  ZARINPAL_TIMEOUT_SECONDS: "15",
  PAYAMAK_PANEL_USERNAME: "",
  PAYAMAK_PANEL_PASSWORD: "",
  PAYAMAK_PANEL_SENDER_NUMBER: "",
  PAYAMAK_PANEL_TIMEOUT_SECONDS: "15",
  OTP_DEV_CONSOLE_FALLBACK_ENABLED: "1",
  OTP_PEPPER: "e2e-real-backend-secret-at-least-32-characters",
  OTP_TTL_SECONDS: "120",
  OTP_RESEND_COOLDOWN_SECONDS: "60",
  OTP_MAX_ATTEMPTS: "5",
  ACCESS_TOKEN_TTL_SECONDS: "900",
  REFRESH_TOKEN_TTL_SECONDS: "2592000",
  OTP_IP_LIMIT_PER_10_MINUTES: "10",
  OTP_MOBILE_LIMIT_PER_10_MINUTES: "5",
  OTP_DEVICE_LIMIT_PER_10_MINUTES: "5",
  PRICE_INTELLIGENCE_COLLECTION_ENABLED: "false",
  PRICE_INTELLIGENCE_USER_AGENT: "Mozilla/5.0 (compatible; PetPlatformBot/1.0)",
  PRICE_INTELLIGENCE_REQUEST_DELAY_SECONDS: "2",
  PRICE_INTELLIGENCE_TIMEOUT_SECONDS: "15",
  PRICE_INTELLIGENCE_MAX_RETRIES: "3",
  PRICE_INTELLIGENCE_MAX_PAGES: "50",
  PRICE_INTELLIGENCE_MAX_PRODUCTS_PER_RUN: "500",
  PRICE_INTELLIGENCE_MAX_RESPONSE_BYTES: "1000000",
  PRICE_INTELLIGENCE_ROBOTS_REQUIRED: "true",
  PRICE_INTELLIGENCE_TERMS_REQUIRED: "true",
};

let backendProcess = null;
let exitCode = 0;

try {
  dockerRmForce(PG_CONTAINER);
  dockerRmForce(REDIS_CONTAINER);

  run("docker", [
    "run",
    "-d",
    "--name",
    PG_CONTAINER,
    "-p",
    `${PG_PORT}:5432`,
    "-e",
    "POSTGRES_USER=pet_platform",
    "-e",
    "POSTGRES_PASSWORD=pet_platform",
    "-e",
    "POSTGRES_DB=pet_platform",
    "postgres:17-alpine",
  ]);
  run("docker", [
    "run",
    "-d",
    "--name",
    REDIS_CONTAINER,
    "-p",
    `${REDIS_PORT}:6379`,
    "redis:7-alpine",
  ]);

  await waitForPostgres();

  mkdirSync(mediaRoot, { recursive: true });

  run("python", ["-m", "alembic", "upgrade", "head"], {
    cwd: backendDir,
    env: backendEnv,
  });

  console.log(`+ starting uvicorn on 127.0.0.1:${BACKEND_PORT}`);
  rmSync(otpLogPath, { force: true });
  backendProcess = spawn(
    "python",
    [
      "-m",
      "uvicorn",
      "app.main:app",
      "--host",
      "127.0.0.1",
      "--port",
      String(BACKEND_PORT),
    ],
    { cwd: backendDir, env: backendEnv, stdio: ["ignore", "pipe", "pipe"] },
  );
  // Piped, not "inherit": the dev-console OTP fallback logs the code to
  // stderr (logging.basicConfig's default StreamHandler target) and never
  // returns it in any API response, so this is the only way
  // tests/e2e-real-backend specs can complete an OTP-gated flow. Still
  // echoed to this process's own stdout/stderr so `pnpm test:e2e:real-backend`
  // output is unchanged for a human watching it run.
  watchForOtpCodes(backendProcess.stdout, process.stdout);
  watchForOtpCodes(backendProcess.stderr, process.stderr);
  backendProcess.on("exit", (code) => {
    if (code !== null && code !== 0 && exitCode === 0) {
      console.error(`uvicorn exited early with code ${code}`);
    }
  });

  await waitForHttp(`http://127.0.0.1:${BACKEND_PORT}/health/ready`);
  console.log("+ backend ready");

  // A production build, isolated via NEXT_DIST_DIR so it never touches (or
  // collides with) a developer's own running `pnpm dev` and its .next/dev
  // lock. `output: standalone` does not copy static assets or public/ into
  // the standalone bundle by design (see Next's own docs) -- staged here so
  // playwright.real-backend.config.ts can start server.js directly.
  if (existsSync(distDirAbs))
    rmSync(distDirAbs, { recursive: true, force: true });
  await runAsync("pnpm", ["exec", "next", "build"], {
    cwd: root,
    env: { ...process.env, NEXT_DIST_DIR: distDir },
    shell: process.platform === "win32",
  });
  const standaloneDir = resolve(distDirAbs, "standalone");
  cpSync(
    resolve(distDirAbs, "static"),
    resolve(standaloneDir, distDir, "static"),
    {
      recursive: true,
    },
  );
  if (existsSync(resolve(root, "public"))) {
    cpSync(resolve(root, "public"), resolve(standaloneDir, "public"), {
      recursive: true,
    });
  }

  await runAsync(
    "pnpm",
    [
      "exec",
      "playwright",
      "test",
      "--config=playwright.real-backend.config.ts",
    ],
    {
      cwd: root,
      env: {
        ...process.env,
        E2E_BACKEND_PORT: String(BACKEND_PORT),
        NEXT_DIST_DIR: distDir,
      },
      shell: process.platform === "win32",
    },
  );
} catch (error) {
  exitCode = 1;
  console.error(error instanceof Error ? error.message : error);
} finally {
  if (backendProcess && !backendProcess.killed) {
    backendProcess.kill();
  }
  dockerRmForce(PG_CONTAINER);
  dockerRmForce(REDIS_CONTAINER);
}

process.exit(exitCode);
