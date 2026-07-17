import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

function filesUnder(path: string): string[] {
  const stat = statSync(path);
  if (stat.isFile()) return [path];
  return readdirSync(path).flatMap((entry) => filesUnder(join(path, entry)));
}

describe("production fixture and token boundary", () => {
  it("keeps fixtures out of application routes, components and browser API client", () => {
    const productionFiles = [
      ...filesUnder("src/app"),
      ...filesUnder("src/components"),
      ...filesUnder("src/features"),
      "src/lib/api/client.ts",
      "src/lib/api/server.ts",
      "src/lib/session.ts",
    ].filter(
      (file) =>
        /\.(ts|tsx)$/.test(file) &&
        !file.endsWith(".test.ts") &&
        !file.endsWith(".test.tsx"),
    );

    for (const file of productionFiles) {
      const text = readFileSync(file, "utf8");
      expect(text, file).not.toMatch(/gate-fixtures|policyFixture|ids\./);
      expect(text, file).not.toMatch(
        /setAccessToken|getAccessToken|authHeaders/,
      );
      expect(text, file).not.toMatch(/localStorage\.setItem\([^)]*token/i);
    }
  });
});
