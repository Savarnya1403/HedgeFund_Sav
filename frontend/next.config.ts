import type { NextConfig } from "next";

// On Vercel: NEXT_PUBLIC_BACKEND_URL points to Cloudflare Tunnel URL exposing the local FastAPI backend.
// Locally: falls back to http://localhost:8001.
const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8001";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/backend/:path*",
        destination: `${BACKEND_URL}/:path*`,
      },
    ];
  },
};

export default nextConfig;
