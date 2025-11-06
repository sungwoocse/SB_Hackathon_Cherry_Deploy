"use client";
import { useEffect, useState } from "react";
import Lottie from "lottie-react";

export default function Character() {
  const [status, setStatus] = useState<
    "idle" | "deploying" | "success" | "failed" | "rolling_back"
  >("idle");
  const [anim, setAnim] = useState<any | null>(null);

  // 배포 상태 가져오기
  useEffect(() => {
    fetch("/mock/deployStatus.json")
      .then((r) => r.json())
      .then((d) => setStatus(d.status ?? "idle"))
      .catch(() => setStatus("idle"));
  }, []);

  // 상태 변화에 따라 Lottie 파일 변경
  useEffect(() => {
    const path = {
      idle: "/lottie/idle.json",
      deploying: "/lottie/deploying.json",
      success: "/lottie/success.json",
      failed: "/lottie/failed.json",
      rolling_back: "/lottie/rolling_back.json",
    }[status];

    fetch(path)
      .then((r) => r.json())
      .then(setAnim)
      .catch(() => setAnim(null));
  }, [status]);

  if (!anim) return null;

  return (
    <div
      className="fixed bottom-10 left-10 z-40 cursor-pointer select-none"
      title={`현재 상태: ${status}`}
    >
      <Lottie
        animationData={anim}
        loop
        autoplay
        style={{ height: 120, width: 120 }}
      />
    </div>
  );
}
