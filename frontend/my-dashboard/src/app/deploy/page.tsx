"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Lottie, { type LottieComponentProps } from "lottie-react";
import { API_BASE_URL, JSON_HEADERS } from "@/lib/api";
import type { DeployStatusEnum, DeployStatusResponse } from "@/types/deploy";

type VisualStatus = "idle" | DeployStatusEnum;

const STATUS_PROGRESS: Record<DeployStatusEnum, number> = {
  pending: 10,
  running_clone: 35,
  running_build: 65,
  running_cutover: 85,
  running_observability: 92,
  completed: 100,
  failed: 100,
};

type LottieData = LottieComponentProps["animationData"];

export default function DeployPage() {
  const [taskId, setTaskId] = useState<string | null>(null);
  const [status, setStatus] = useState<VisualStatus>("idle");
  const [taskDetail, setTaskDetail] = useState<DeployStatusResponse | null>(null);
  const [animationData, setAnimationData] = useState<LottieData | null>(null);
  const [isLoadingAnim, setIsLoadingAnim] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<number | null>(null);

  const animPath = useMemo(() => {
    const map: Record<VisualStatus, string> = {
      idle: "/lottie/idle.json",
      pending: "/lottie/deploying.json",
      running_clone: "/lottie/deploying.json",
      running_build: "/lottie/deploying.json",
      running_cutover: "/lottie/deploying.json",
      running_observability: "/lottie/deploying.json",
      completed: "/lottie/success.json",
      failed: "/lottie/failed.json",
    };
    return map[status];
  }, [status]);

  useEffect(() => {
    let aborted = false;
    setIsLoadingAnim(true);
    fetch(animPath)
      .then((r) => r.json())
      .then((json) => {
        if (!aborted) setAnimationData(json as LottieData);
      })
      .finally(() => {
        if (!aborted) setIsLoadingAnim(false);
      });
    return () => {
      aborted = true;
    };
  }, [animPath]);

  const clearPoll = () => {
    if (pollRef.current) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  const fetchStatus = async (id: string) => {
    const res = await fetch(`${API_BASE_URL}/api/v1/status/${id}`);
    if (!res.ok) {
      throw new Error("status fetch failed");
    }
    const payload: DeployStatusResponse = await res.json();
    setTaskDetail(payload);
    setStatus(payload.status);
    if (payload.status === "completed" || payload.status === "failed") {
      clearPoll();
    }
  };

  const startDeploy = async () => {
    clearPoll();
    setError(null);
    setTaskDetail(null);
    setStatus("pending");
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/deploy`, {
        method: "POST",
        headers: JSON_HEADERS,
        body: JSON.stringify({ branch: "deploy" }),
      });
      if (!res.ok) {
        throw new Error("deploy request failed");
      }
      const payload = await res.json();
      setTaskId(payload.task_id);
      setStatus(payload.status as DeployStatusEnum);
      fetchStatus(payload.task_id);
      pollRef.current = window.setInterval(() => {
        fetchStatus(payload.task_id).catch((err) => {
          console.error(err);
          setError("상태 조회 실패");
          clearPoll();
        });
      }, 3000);
    } catch (err) {
      console.error(err);
      setError("배포 요청 실패");
      setStatus("idle");
    }
  };

  useEffect(() => {
    return () => {
      clearPoll();
    };
  }, []);

  const progressWidth =
    status === "idle" ? 0 : STATUS_PROGRESS[status as DeployStatusEnum] ?? 0;

  return (
    <div className="p-8 max-w-3xl mx-auto text-gray-100">
      <h1 className="text-2xl font-bold text-blue-400">배포 진행</h1>
      <p className="text-sm text-gray-400 mt-1">
        FastAPI `/api/v1/deploy` → `/api/v1/status/(task_id)` 실데이터를 사용합니다.
      </p>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <button
          className="px-5 py-2 rounded-lg text-white bg-blue-600 hover:bg-blue-700 disabled:bg-blue-900 disabled:cursor-not-allowed"
          onClick={startDeploy}
          disabled={status !== "idle" && status !== "completed" && status !== "failed"}
        >
          🚀 배포 시작
        </button>
        {taskId && (
          <span className="text-sm text-gray-400">
            task_id: <span className="font-mono text-gray-200">{taskId}</span>
          </span>
        )}
        {error && <span className="text-sm text-red-400">{error}</span>}
      </div>

      <div className="mt-8 bg-gray-900 rounded-2xl p-6 border border-gray-800">
        <p className="text-gray-300">
          현재 상태:{" "}
          <b className="text-white">
            {status === "idle" ? "대기 중" : status.replace("running_", "running ").toUpperCase()}
          </b>
        </p>
        <div className="mt-4 h-[220px] flex items-center justify-center">
          {isLoadingAnim || !animationData ? (
            <span className="text-gray-500 text-sm">애니메이션 불러오는 중…</span>
          ) : (
            <Lottie animationData={animationData} loop autoplay style={{ height: 200, width: 200 }} />
          )}
        </div>
        <div className="mt-4">
          <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
            <div
              className="h-2 bg-blue-500 transition-all"
              style={{ width: `${progressWidth}%` }}
            />
          </div>
          <p className="text-xs text-gray-500 mt-2">
            pending → running_clone → running_build → running_cutover → running_observability → completed
          </p>
        </div>
      </div>

      {taskDetail && (
        <div className="mt-6 grid gap-4">
          <div className="bg-gray-900 rounded-2xl border border-gray-800 p-4">
            <p className="text-sm text-gray-400">타임스탬프</p>
            <p className="text-base text-gray-100">
              시작: {new Date(taskDetail.started_at).toLocaleString("ko-KR")}
            </p>
            <p className="text-base text-gray-100">
              완료:{" "}
              {taskDetail.completed_at
                ? new Date(taskDetail.completed_at).toLocaleString("ko-KR")
                : "진행 중"}
            </p>
          </div>
          <div className="bg-gray-900 rounded-2xl border border-gray-800 p-4">
            <p className="text-sm text-gray-400 mb-2">현재 Stage 메타데이터</p>
            {Object.entries(taskDetail.stages || {}).length ? (
              <ul className="text-xs font-mono space-y-1 text-gray-300">
                {Object.entries(taskDetail.stages).map(([stage, info]) => {
                  const timestamp =
                    info && typeof info.timestamp === "string"
                      ? new Date(info.timestamp).toLocaleTimeString("ko-KR", { timeZone: "Asia/Seoul" })
                      : "-";
                  return (
                    <li key={stage} className="flex justify-between gap-4">
                      <span>{stage}</span>
                      <span className="text-gray-400">{timestamp}</span>
                    </li>
                  );
                })}
              </ul>
            ) : (
              <p className="text-gray-500 text-sm">스테이지 정보 없음</p>
            )}
            {taskDetail.failure_context && (
              <div className="mt-3 text-red-300 text-xs whitespace-pre-wrap bg-red-900/20 p-3 rounded">
                {JSON.stringify(taskDetail.failure_context, null, 2)}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
