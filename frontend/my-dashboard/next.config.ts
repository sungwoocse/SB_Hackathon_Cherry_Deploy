import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export",
  turbopack: {
    // 상위 리포지토리의 lockfile을 루트로 잘못 추론하는 것을 방지
    root: __dirname,
  },
};

export default nextConfig;
