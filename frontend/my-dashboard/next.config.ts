import type { NextConfig } from "next";

const nextConfig = {
  experimental: {
    turbo: false, // ✅ Turbopack 완전 비활성화
  },
};

export default nextConfig;
