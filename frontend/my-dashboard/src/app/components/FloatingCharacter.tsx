"use client";

import Image from "next/image";
import { motion, useAnimation } from "framer-motion";
import { useEffect, useMemo } from "react";

interface FloatingCharacterProps {
  progress: number; // 0~100
}

const FloatingCharacter: React.FC<FloatingCharacterProps> = ({ progress }) => {
  const controls = useAnimation();

  const spriteSrc = useMemo(() => "/images/good.png", [progress]);

  useEffect(() => {
    if (typeof window === "undefined") return undefined;
    let running = true;

    const roam = async () => {
      while (running) {
        const vw = window.innerWidth;
        const vh = window.innerHeight;
        const offsetX = vw / 2;
        const offsetY = vh / 2;
        const x = Math.random() * vw - offsetX;
        const y = Math.random() * vh - offsetY;
        const rot = Math.random() * 30 - 15;
        const scale = 0.85 + Math.random() * 0.25;
        await controls.start({
          x,
          y,
          rotate: rot,
          scale,
          transition: {
            duration: 2.5 + Math.random() * 1.2,
            ease: "easeInOut",
          },
        });
      }
    };

    roam();
    return () => {
      running = false;
    };
  }, [controls]);

  return (
    <motion.div
      animate={controls}
      className="absolute inset-0 flex items-center justify-center pointer-events-none select-none"
      style={{ opacity: 0.95 }}
    >
      <Image
        src={spriteSrc}
        alt="Cherry assistant success"
        width={140}
        height={140}
        className="drop-shadow-[0_0_25px_rgba(0,255,255,0.4)] transition-transform duration-500 ease-in-out select-none pointer-events-none"
        priority={false}
        unoptimized
      />
    </motion.div>
  );
};

export default FloatingCharacter;
