import type { NextConfig } from "next";

// The browser only talks to the web origin; /api/* is proxied to the FastAPI service so the
// session cookie stays first-party.
const apiUrl = process.env.API_INTERNAL_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  // A chat turn (agent + tools) can take longer than the default 30 s proxy timeout.
  experimental: { proxyTimeout: 120_000 },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${apiUrl}/:path*` }];
  },
};

export default nextConfig;
