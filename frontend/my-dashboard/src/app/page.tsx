"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import ChatWidget from "./components/ChatWidget";

interface DeployData {
  status?: string;
  cost?: number;
  risk?: string;
  timestamp?: string;
  greenBlue?: {
    active: "green" | "blue";
    blueVersion?: string;
    greenVersion?: string;
  };
  health?: {
    healthy: number; // %
    unhealthy: number; // %
  };
  traffic?: {
    green: number;
    blue: number;
  };
  rollbackLog?: {
    lastRollback?: string;
    reason?: string;
  };
}

export default function Page() {
  const [data, setData] = useState<DeployData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<string>("");

  const fetchData = async () => {
    try {
      const res = await fetch("/mock/deployStatus.json");
      if (!res.ok) throw new Error("서버 응답 오류");
      const result = await res.json();
      setData(result);
      setError(null);
      setLastUpdate(new Date().toLocaleTimeString());
    } catch (err) {
      console.error("데이터 로드 실패:", err);
      setError("데이터를 불러오지 못했습니다. 3초 후 재시도 중...");
    } finally {
      setLoading(false);
    }
  };

  // 3초마다 갱신
  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 3000);
    return () => clearInterval(interval);
  }, []);

  // 색상 구분
  const statusColor =
    data?.status === "success"
      ? "text-green-400"
      : data?.status === "failed"
      ? "text-red-400"
      : "text-yellow-400";

  const riskColor =
    data?.risk === "low"
      ? "text-green-400"
      : data?.risk === "high"
      ? "text-red-400"
      : "text-yellow-400";

  // 카드 애니메이션 옵션
  const cardVariants = {
    hidden: { opacity: 0, y: 20 },
    visible: (i: number) => ({
      opacity: 1,
      y: 0,
      transition: { delay: i * 0.15 },
    }),
  };

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center text-gray-400">
        ⏳ 데이터를 불러오는 중입니다...
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-screen items-center justify-center text-red-400">
        ❌ {error}
      </div>
    );
  }

  return (
    <motion.div
      className="text-gray-200 p-8 min-h-screen bg-gray-900"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.6 }}
    >
      {/* 상단 타이틀 */}
      <motion.h2
        className="text-3xl font-bold mb-4 text-blue-400"
        initial={{ y: -20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
      >
        Dashboard Overview
      </motion.h2>

      <motion.p
        className="text-gray-400 mb-8"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.3 }}
      >
        마지막 업데이트: <span className="text-gray-300">{lastUpdate}</span>
      </motion.p>

      {/* 주요 카드 섹션 */}
      <div className="grid grid-cols-3 gap-6 mb-6">
        {/* 배포 상태 */}
        <motion.div
          className="bg-gray-800 p-6 rounded-lg shadow-lg"
          variants={cardVariants}
          initial="hidden"
          animate="visible"
          custom={0}
        >
          <p className="text-lg font-semibold">📦 배포 상태</p>
          <p className={`mt-2 text-xl font-bold ${statusColor}`}>
            {data?.status?.toUpperCase() || "N/A"}
          </p>
        </motion.div>

        {/* 예상 비용 */}
        <motion.div
          className="bg-gray-800 p-6 rounded-lg shadow-lg"
          variants={cardVariants}
          initial="hidden"
          animate="visible"
          custom={1}
        >
          <p className="text-lg font-semibold">💰 예상 비용</p>
          <p className="mt-2 text-xl text-blue-300 font-bold">
            {data?.cost ? `$${data.cost} / hr` : "N/A"}
          </p>
        </motion.div>

        {/* 리스크 수준 */}
        <motion.div
          className="bg-gray-800 p-6 rounded-lg shadow-lg"
          variants={cardVariants}
          initial="hidden"
          animate="visible"
          custom={2}
        >
          <p className="text-lg font-semibold">⚙️ 리스크 수준</p>
          <p className={`mt-2 text-xl font-bold ${riskColor}`}>
            {data?.risk?.toUpperCase() || "N/A"}
          </p>
        </motion.div>
      </div>

      {/* Green/Blue 상태 카드 */}
      <div className="grid grid-cols-2 gap-6 mb-6">
        <motion.div
          className="bg-gray-800 p-6 rounded-lg shadow-lg"
          variants={cardVariants}
          initial="hidden"
          animate="visible"
          custom={3}
        >
          <p className="text-lg font-semibold">🟢 Green / 🔵 Blue 배포 상태</p>
          <p className="mt-2 text-xl font-bold">
            Active:{" "}
            <span
              className={
                data?.greenBlue?.active === "green"
                  ? "text-green-400"
                  : "text-blue-400"
              }
            >
              {data?.greenBlue?.active?.toUpperCase()}
            </span>
          </p>
          <p className="text-sm text-gray-400 mt-1">
            Green: {data?.greenBlue?.greenVersion || "N/A"} / Blue:{" "}
            {data?.greenBlue?.blueVersion || "N/A"}
          </p>
        </motion.div>

        {/* Rollback 로그 */}
        <motion.div
          className="bg-gray-800 p-6 rounded-lg shadow-lg"
          variants={cardVariants}
          initial="hidden"
          animate="visible"
          custom={4}
        >
          <p className="text-lg font-semibold">⏪ 최근 Rollback</p>
          <p className="mt-2 text-md text-gray-300">
            {data?.rollbackLog?.lastRollback
              ? `At ${data.rollbackLog.lastRollback}`
              : "No recent rollback"}
          </p>
          {data?.rollbackLog?.reason && (
            <p className="text-sm text-gray-500">
              Reason: {data.rollbackLog.reason}
            </p>
          )}
        </motion.div>
      </div>

      {/* Health Check / Traffic 섹션 */}
      <div className="grid grid-cols-2 gap-6 mb-8">
        {/* Health Check */}
        <motion.div
          className="bg-gray-800 p-6 rounded-lg shadow-lg"
          variants={cardVariants}
          initial="hidden"
          animate="visible"
          custom={5}
        >
          <p className="text-lg font-semibold">❤️ Health Check</p>
          <p className="text-sm text-gray-400 mt-2">
            Healthy: {data?.health?.healthy ?? 0}% / Unhealthy:{" "}
            {data?.health?.unhealthy ?? 0}%
          </p>
          <div className="w-full bg-gray-700 h-2 rounded-full mt-2">
            <div
              className="bg-green-500 h-2 rounded-full"
              style={{ width: `${data?.health?.healthy || 0}%` }}
            ></div>
          </div>
        </motion.div>

        {/* Traffic Split */}
        <motion.div
          className="bg-gray-800 p-6 rounded-lg shadow-lg"
          variants={cardVariants}
          initial="hidden"
          animate="visible"
          custom={6}
        >
          <p className="text-lg font-semibold">📊 Traffic 분배</p>
          <div className="w-full bg-gray-700 h-2 rounded-full mt-3 flex">
            <div
              className="bg-green-500 h-2 rounded-l-full"
              style={{ width: `${data?.traffic?.green || 0}%` }}
            ></div>
            <div
              className="bg-blue-500 h-2 rounded-r-full"
              style={{ width: `${data?.traffic?.blue || 0}%` }}
            ></div>
          </div>
          <p className="mt-2 text-sm text-gray-400">
            Green {data?.traffic?.green ?? 0}% / Blue {data?.traffic?.blue ?? 0}%
          </p>
        </motion.div>
      </div>

      {/* 챗봇 위젯 */}
      <ChatWidget />
    </motion.div>
  );
}
