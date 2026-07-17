import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  outputFileTracingRoot: __dirname,
  poweredByHeader: false,
  turbopack: {
    root: __dirname,
  },
};

export default nextConfig;
