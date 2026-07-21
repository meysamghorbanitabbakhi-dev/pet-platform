import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

function filesUnder(path: string): string[] {
  const stat = statSync(path);
  if (stat.isFile()) return [path];
  return readdirSync(path).flatMap((entry) => filesUnder(join(path, entry)));
}

function envExampleKeys(): string[] {
  const text = readFileSync(".env.example", "utf8");
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line && !line.startsWith("#"))
    .map((line) => line.split("=")[0]);
}

describe(".env.example", () => {
  it("documents no key that the application never reads", () => {
    // Found for real: NEXT_PUBLIC_GATE_FIXTURE_MODE was documented here and
    // set in both docker-compose.yml files and the README, but only the
    // non-prefixed GATE_FIXTURE_MODE was ever read anywhere in src/ --
    // setting the documented name had zero effect. This is the same class
    // of bug the backend's .env.example/Settings field-name check guards
    // against, applied to the frontend's ad hoc process.env.X reads.
    const sourceText = filesUnder("src")
      .filter((file) => /\.(ts|tsx)$/.test(file))
      .map((file) => readFileSync(file, "utf8"))
      .join("\n");

    const dead = envExampleKeys().filter(
      (key) => !sourceText.includes(`process.env.${key}`),
    );
    expect(dead).toEqual([]);
  });
});
