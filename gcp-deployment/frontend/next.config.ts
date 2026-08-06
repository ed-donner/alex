import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  output: 'standalone',  // Changed from 'export' for Cloud Run
  images: {
    unoptimized: true
  },
  // Disable automatic trailing slash redirect for API routes
  trailingSlash: false,
};

export default nextConfig;
