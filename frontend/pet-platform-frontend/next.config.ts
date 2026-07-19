import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  outputFileTracingRoot: __dirname,
  poweredByHeader: false,
  // Overridable so an isolated e2e build (scripts/e2e-real-backend.mjs) never
  // collides with a developer's own running `next dev` -- Next 16 locks
  // dev-server state per project directory (.next/dev/lock), not per port,
  // so a second dev/build process against the default .next would conflict.
  distDir: process.env.NEXT_DIST_DIR || ".next",
  turbopack: {
    root: __dirname,
  },
};

export default nextConfig;
