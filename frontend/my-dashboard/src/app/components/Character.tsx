"use client";
import Image from "next/image";
import { motion } from "framer-motion";

interface CharacterProps {
  status: "idle" | "talking" | "success" | "failed";
}

export default function Character({ status }: CharacterProps) {
  const getImage = () => {
    switch (status) {
      case "talking":
        return "/images/talking.png";
      case "success":
        return "/images/success.png";
      case "failed":
        return "/images/failed.png";
      default:
        return "/images/idle.png";
    }
  };

  return (
    <motion.div
      className="fixed bottom-10 left-10 z-[100]" // 낮은 z-index
      animate={{
        y: [0, -6, 0],
        scale: status === "talking" ? [1, 1.05, 1] : 1,
        rotate: status === "success" ? [0, 5, -5, 0] : 0,
      }}
      transition={{
        duration: status === "talking" ? 0.5 : 2,
        repeat: Infinity,
        ease: "easeInOut",
      }}
    >
      <Image
        src={getImage()}
        alt={status}
        width={120}
        height={120}
        className="select-none pointer-events-none"
      />
    </motion.div>
  );
}
