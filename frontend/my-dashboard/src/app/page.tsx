"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";

interface DeployData {
  status?: string;
  cost?: number;
  risk?: string;
  timestamp?: string;
}

export default function Home() {
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

  if (loading) {
    return (
      <motion.div
        className="flex min-h-screen items-center justify-center text-gray-400"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
      >
        ⏳ 데이터를 불러오는 중...
      </motion.div>
    );
  }

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

  const cardVariants = {
    hidden: { opacity: 0, y: 20 },
    visible: (i: number) => ({
      opacity: 1,
      y: 0,
      transition: { delay: i * 0.2 },
    }),
  };

  return (
    <motion.div
      className="text-gray-200"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.6 }}
    >
      <motion.h2
        className="text-2xl font-bold mb-4 text-blue-400"
        initial={{ y: -20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ duration: 0.6 }}
      >
        Dashboard Overview
      </motion.h2>

      <motion.p
        className="text-gray-400 mb-6"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.3 }}
      >
        마지막 업데이트:{" "}
        <span className="text-gray-300">
          {data.timestamp
            ? new Date(data.timestamp).toLocaleString()
            : "알 수 없음"}
        </span>
      </motion.p>

      <div className="grid grid-cols-3 gap-4">
        {[
          {
            title: "📦 배포 상태",
            value: data.status?.toUpperCase() ?? "UNKNOWN",
            color: statusColor,
          },
          {
            title: "💰 예상 비용",
            value: data.cost ? `$${data.cost} / hr` : "N/A",
            color: "text-blue-300",
          },
          {
            title: "⚙️ 리스크 수준",
            value: data.risk?.toUpperCase() ?? "N/A",
            color: riskColor,
          },
        ].map((card, i) => (
          <motion.div
            key={card.title}
            className="bg-gray-800 p-5 rounded-lg shadow-md hover:bg-gray-700 transition"
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
    </motion.div>
  );
}
