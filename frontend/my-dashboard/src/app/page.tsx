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

  const gbColor =
    data.greenBlue?.active === "green"
      ? "text-green-400"
      : "text-blue-400";

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
      className="text-gray-200 p-8 min-h-screen bg-gray-900"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.6 }}
    >
      <motion.h2
        className="text-3xl font-bold mb-4 text-blue-400"
        initial={{ y: -20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ duration: 0.6 }}
      >
        Dashboard Overview
      </motion.h2>

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

      <div className="grid grid-cols-4 gap-6">
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
          {
            title: "🟢 Green/Blue 상태",
            value: `${data.greenBlue?.active?.toUpperCase() || "N/A"} 
                    (${data.greenBlue?.greenVersion || ""} / ${data.greenBlue?.blueVersion || ""})`,
            color: gbColor,
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

      <ChatWidget />
    </motion.div>
  );
}
