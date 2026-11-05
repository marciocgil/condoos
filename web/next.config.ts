import type { NextConfig } from "next";

// The browser only talks to the web origin; /api/* is proxied to the FastAPI service so the
// session cookie stays first-party.
const apiUrl = process.env.API_INTERNAL_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${apiUrl}/:path*` }];
  },
};

export default nextConfig;
