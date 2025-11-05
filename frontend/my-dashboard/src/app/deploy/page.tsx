"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Lottie from "lottie-react";

type DeployStatus =
  | "idle" | "deploy_started" | "running_clone" | "running_build"
  | "running_health_check" | "completed" | "failed" | "rolling_back";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") || "http://localhost:8000";
const USE_MOCK = true; // 백엔드 붙이면 false

export default function DeployPage() {
  const [taskId, setTaskId] = useState<string | null>(null);
  const [status, setStatus] = useState<DeployStatus>("idle");
  const [animationData, setAnimationData] = useState<any | null>(null);
  const [isLoadingAnim, setIsLoadingAnim] = useState(false);
  const pollRef = useRef<number | null>(null);
  const mockRef = useRef<number | null>(null);

  const animPath = useMemo(() => {
    const map: Record<DeployStatus, string> = {
      idle: "/lottie/idle.json",
      deploy_started: "/lottie/deploying.json",
      running_clone: "/lottie/deploying.json",
      running_build: "/lottie/deploying.json",
      running_health_check: "/lottie/deploying.json",
      rolling_back: "/lottie/rolling_back.json",
      completed: "/lottie/success.json",
      failed: "/lottie/failed.json",
    };
    return map[status];
  }, [status]);

  useEffect(() => {
    let aborted = false;
    setIsLoadingAnim(true);
    fetch(animPath).then(r => r.json())
      .then(json => !aborted && setAnimationData(json))
      .finally(() => !aborted && setIsLoadingAnim(false));
    return () => { aborted = true; };
  }, [animPath]);

  const clearTimers = () => {
    if (pollRef.current) { window.clearInterval(pollRef.current); pollRef.current = null; }
    if (mockRef.current) { window.clearTimeout(mockRef.current); mockRef.current = null; }
  };

  const startDeploy = async () => {
    clearTimers();
    setStatus("idle"); setTaskId(null);

    if (USE_MOCK) {
      setTaskId("mock-1234");
      setStatus("deploy_started");
      const seq: DeployStatus[] = ["running_clone","running_build","running_health_check","completed"];
      let i = 0;
      const tick = () => {
        setStatus(seq[i]); i++;
        if (i < seq.length) mockRef.current = window.setTimeout(tick, 2500);
      };
      mockRef.current = window.setTimeout(tick, 1800);
      return;
    }

    const res = await fetch(`${API_BASE}/api/v1/deploy`, { method: "POST" });
    const j = await res.json();
    setTaskId(j.task_id);
    setStatus("deploy_started");

    pollRef.current = window.setInterval(async () => {
      const r = await fetch(`${API_BASE}/api/v1/status/${j.task_id}`);
      const s = (await r.json()).status as DeployStatus;
      setStatus(s);
      if (s === "completed" || s === "failed") clearTimers();
    }, 3000);
  };

  return (
    <div className="p-8 max-w-3xl mx-auto">
      <h1 className="text-2xl font-bold text-blue-400">배포 진행</h1>

      <div className="mt-4 flex items-center gap-3">
        <button className="px-5 py-2 rounded-lg text-white bg-blue-600 hover:bg-blue-700"
                onClick={startDeploy}>
          🚀 배포 시작
        </button>
        {taskId && <span className="text-sm text-gray-400">task_id: {taskId}</span>}
      </div>

      <div className="mt-8 bg-gray-900 rounded-2xl p-6 border border-gray-800">
        <p className="text-gray-300">현재 상태: <b className="text-white">{status}</b></p>
        <div className="mt-4 h-[220px] flex items-center justify-center">
          {isLoadingAnim || !animationData
            ? <span className="text-gray-500 text-sm">애니메이션 불러오는 중…</span>
            : <Lottie animationData={animationData} loop autoplay style={{ height: 200, width: 200 }} />
          }
        </div>
        <div className="mt-4">
          <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
            <div className="h-2 bg-blue-500 transition-all"
                 style={{ width:
                   status==="idle"? "0%"
                   : status==="deploy_started"? "10%"
                   : status==="running_clone"? "35%"
                   : status==="running_build"? "65%"
                   : status==="running_health_check"? "85%"
                   : "100%"}}/>
          </div>
        </div>
      </div>
    </div>
  );
}
