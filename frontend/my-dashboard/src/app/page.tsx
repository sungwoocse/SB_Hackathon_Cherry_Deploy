"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import Lottie from "lottie-react";
import deployingAnim from "../../public/lottie/deploying.json";
import successAnim from "../../public/lottie/success.json";
import failedAnim from "../../public/lottie/failed.json";
import ChatWidget from "./components/ChatWidget";

interface DeployData {
  status?: string;
  cost?: number;
  risk?: string;
  timestamp?: string;
}

export default function Page() {
  const [data, setData] = useState<DeployData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/mock/deployStatus.json")
      .then((res) => res.json())
      .then((data) => {
        setData(data);
        setLoading(false);
      })
      .catch((err) => {
        console.error("데이터 로드 실패:", err);
        setLoading(false);
      });
  }, []);

  // 로딩 상태
  if (loading) {
    return (
      <motion.div
        className="flex min-h-screen items-center justify-center text-gray-400"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
      >
        ⏳ 데이터를 불러오는 중입니다...
      </motion.div>
    );
  }

  // 데이터 없음
  if (!data) {
    return (
      <motion.div
        className="flex min-h-screen items-center justify-center text-red-400"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
      >
        ❌ 데이터를 불러오지 못했습니다.
      </motion.div>
    );
  }

  // 상태별 색상
  const statusColor =
    data.status === "success"
      ? "text-green-400"
      : data.status === "failed"
      ? "text-red-400"
      : "text-yellow-400";

  const riskColor =
    data.risk === "low"
      ? "text-green-400"
      : data.risk === "high"
      ? "text-red-400"
      : "text-yellow-400";

  // 카드 애니메이션 옵션
  const cardVariants = {
    hidden: { opacity: 0, y: 20 },
    visible: (i: number) => ({
      opacity: 1,
      y: 0,
      transition: { delay: i * 0.2 },
    }),
  };

  // Lottie 상태 매핑
  const getAnimation = () => {
    switch (data.status) {
      case "success":
        return successAnim;
      case "failed":
        return failedAnim;
      default:
        return deployingAnim;
    }
  };

  return (
    <motion.div
      className="text-gray-200 p-8 min-h-screen bg-gray-900"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.6 }}
    >
      {/* 페이지 헤더 */}
      <motion.h2
        className="text-3xl font-bold mb-4 text-blue-400"
        initial={{ y: -20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ duration: 0.6 }}
      >
        Dashboard Overview
      </motion.h2>

      {/* 최근 업데이트 */}
      <motion.p
        className="text-gray-400 mb-8"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.3 }}
      >
        마지막 업데이트:{" "}
        <span className="text-gray-300">
          {data.timestamp
            ? new Date(data.timestamp).toLocaleString()
            : "N/A"}
        </span>
      </motion.p>

      {/* Lottie 배포 상태 */}
      <div className="flex items-center justify-center mb-8">
        <Lottie
          animationData={getAnimation()}
          loop
          style={{ height: 180, width: 180 }}
        />
      </div>

      {/* 주요 지표 카드 */}
      <div className="grid grid-cols-3 gap-6">
        {[
          {
            title: "📦 배포 상태",
            value: data.status?.toUpperCase() || "N/A",
            color: statusColor,
          },
          {
            title: "💰 예상 비용",
            value: data.cost ? `$${data.cost} / hr` : "N/A",
            color: "text-blue-300",
          },
          {
            title: "⚙️ 리스크 수준",
            value: data.risk?.toUpperCase() || "N/A",
            color: riskColor,
          },
        ].map((card, i) => (
          <motion.div
            key={card.title}
            className="bg-gray-800 p-6 rounded-lg shadow-lg hover:bg-gray-700 transition"
            variants={cardVariants}
            initial="hidden"
            animate="visible"
            custom={i}
          >
            <p className="text-lg font-semibold">{card.title}</p>
            <p className={`mt-2 text-xl font-bold ${card.color}`}>
              {card.value}
            </p>
          </motion.div>
        ))}
      </div>

      {/* 👇 챗봇 위젯 */}
      <ChatWidget />
    </motion.div>
  );
}
