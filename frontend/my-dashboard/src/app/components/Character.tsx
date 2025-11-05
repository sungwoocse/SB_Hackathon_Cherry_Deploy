"use client";
import { useEffect, useState } from "react";
import Lottie from "lottie-react";

export default function Character() {
  const [status, setStatus] = useState<"idle"|"deploying"|"success"|"failed"|"rolling_back">("idle");
  const [anim, setAnim] = useState<any | null>(null);

  useEffect(() => {
    fetch("/mock/deployStatus.json").then(r=>r.json()).then(d => setStatus((d.status ?? "idle")));
  }, []);

  useEffect(() => {
    const path = {
      idle:"/lottie/idle.json",
      deploying:"/lottie/deploying.json",
      success:"/lottie/success.json",
      failed:"/lottie/failed.json",
      rolling_back:"/lottie/rolling_back.json",
    }[status];
    fetch(path).then(r=>r.json()).then(setAnim);
  }, [status]);

  if (!anim) return null;

  return (
    <div className="fixed bottom-10 right-10 z-50 cursor-pointer select-none">
      <Lottie animationData={anim} loop autoplay style={{ height: 120, width: 120 }} />
    </div>
  );
}
