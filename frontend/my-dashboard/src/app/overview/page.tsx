"use client";
import { useEffect, useState } from "react";
import MetricCard from "../components/MetricCard";

type Overview = {
  status?: string;
  pipeline?: string;
  lock?: boolean;
  metrics?: { p95?: number; error_rate?: number };
  comparison?: { before_p95?: number; after_p95?: number; before_err?: number; after_err?: number };
  cost?: string;
  risk?: string;
  updated_at?: string;
};

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") || "";

export default function OverviewPage() {
  const [data, setData] = useState<Overview | null>(null);
  const [busy, setBusy] = useState(false);

  // mock → 나중에 GET {API_BASE}/overview 로 교체
  useEffect(() => {
    fetch("/mock/overview.json").then(r => r.json()).then(setData).catch(console.error);
  }, []);

  const callAction = async (path: string) => {
    try {
      setBusy(true);
      if (!API_BASE) {
        alert(`(mock) ${path} 호출 – .env에 NEXT_PUBLIC_API_BASE_URL 설정 시 실제로 호출합니다.`);
        return;
      }
      const res = await fetch(`${API_BASE}${path}`, { method: "POST" });
      if (!res.ok) throw new Error(`${path} failed: ${res.status}`);
      const j = await res.json().catch(() => ({}));
      alert(`OK: ${path}\n` + JSON.stringify(j));
    } catch (e: any) {
      alert(e?.message || "요청 실패");
    } finally {
      setBusy(false);
    }
  };

  if (!data) return <div className="p-6 text-gray-400">Loading Overview…</div>;

  return (
    <div className="grid grid-cols-3 gap-4 p-6">
      <MetricCard title="현재 운영 상태" value={data.status?.toUpperCase?.() ?? "UNKNOWN"} tone="green" />
      <MetricCard
        title="파이프라인 / 락 상태"
        value={`${data.pipeline ?? "N/A"} / ${data.lock ? "🔒" : "🔓"}`}
        tone="yellow"
      />
      <MetricCard
        title="건강지표"
        value={`p95: ${data.metrics?.p95 ?? "N/A"}ms  |  errRate: ${data.metrics?.error_rate ?? "N/A"}%`}
        tone="blue"
      />

      <MetricCard
        title="직전 배포 전/후 비교"
        value={`p95  ${data.comparison?.before_p95 ?? "?"} → ${data.comparison?.after_p95 ?? "?"} ms
${data.comparison?.before_err ?? "?"}% → ${data.comparison?.after_err ?? "?"}%`}
        tone="purple"
        span={2}
        mono
      />

      <MetricCard title="비용 / 리스크" value={`${data.cost ?? "N/A"}  /  ${(data.risk ?? "N/A").toUpperCase()}`} tone="pink" />

      {/* 빠른 액션 */}
      <div className="col-span-3 bg-gray-900 p-4 rounded-2xl text-center border border-gray-800">
        <h2 className="text-lg font-semibold text-red-300">빠른 액션</h2>
        <div className="space-x-3 mt-3">
          <button
            className={`px-4 py-2 rounded-lg text-white ${busy ? "bg-gray-600" : "bg-red-600 hover:bg-red-700"}`}
            onClick={() => callAction("/api/v1/rollback")}
            disabled={busy}
          >
            🔁 롤백
          </button>
          <button
            className={`px-4 py-2 rounded-lg text-white ${busy ? "bg-gray-600" : "bg-green-600 hover:bg-green-700"}`}
            onClick={() => callAction("/api/v1/deploy")}
            disabled={busy}
          >
            🚀 재배포
          </button>
        </div>
        <p className="text-xs text-gray-500 mt-2">
          마지막 업데이트: {data.updated_at ? new Date(data.updated_at).toLocaleString() : "N/A"}
        </p>
      </div>
    </div>
  );
}
