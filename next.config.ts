import path from "path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Prefer this project over parent monorepo lockfiles
  outputFileTracingRoot: path.join(__dirname),
  // Proxy API calls to the FastAPI backend during local dev
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://127.0.0.1:8000/api/:path*",
      },
    ];
  },
};

export default nextConfig;
