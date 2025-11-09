"use client";

import Image from "next/image";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { motion } from "framer-motion";
import axios from "axios";
import ChatWidget from "./components/ChatWidget";
import FloatingCharacter from "./components/FloatingCharacter";
import { API_BASE_URL, JSON_HEADERS } from "@/lib/api";
import type {
  BlueGreenPlan,
  DeployPreviewResponse,
  DiffSource,
  DiffStats,
  DeployTaskSummary,
  DeployTimelineEntry,
  HealthStatusResponse,
  LoginResponse,
  LogoutResponse,
  MeResponse,
  RiskAssessment,
} from "@/types/deploy";

const CURRENT_TASK_STORAGE_KEY = "cherry.currentTaskId";

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: JSON_HEADERS,
  withCredentials: true,
});

interface DashboardState {
  status?: string;
  timestamp?: string;
}

const PROGRESS_BY_STATUS: Record<string, number> = {
  pending: 12,
  running_clone: 32,
  running_build: 58,
  running_cutover: 78,
  running_observability: 92,
  completed: 100,
  failed: 100,
};

const cardVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: (i: number) => ({ opacity: 1, y: 0, transition: { delay: i * 0.08 } }),
};

type TaskSummaryData = {
  git_commit?: {
    author?: {
      name?: string | null;
      email?: string | null;
    } | null;
  } | null;
  actor?: string | null;
};

type TaskMetadata = {
  actor?: string | null;
  requested_by?: string | null;
  trigger?: string | null;
};

export default function Page() {
  const [state, setState] = useState<DashboardState>({ status: "READY" });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<string>("");

  const [taskId, setTaskId] = useState<string | null>(null);
  const [, setDeploying] = useState(false);
  const [rollbacking, setRollbacking] = useState(false);

  const [previewDetail, setPreviewDetail] = useState<DeployPreviewResponse | null>(null);
  const [healthInfo, setHealthInfo] = useState<HealthStatusResponse | null>(null);
  const [recentTasks, setRecentTasks] = useState<DeployTaskSummary[]>([]);
  const [failureInfo, setFailureInfo] = useState<Record<string, unknown> | null>(null);
  const [currentStages, setCurrentStages] = useState<Record<string, Record<string, unknown>>>({});
  const [taskTimezone, setTaskTimezone] = useState<string>("Asia/Seoul");
  const [heroOverrideStatus, setHeroOverrideStatus] = useState<string | null>(null);
  const heroOverrideTimer = useRef<NodeJS.Timeout | null>(null);
  const heroOverrideStatusRef = useRef<string | null>(null);

  const [preflightOpen, setPreflightOpen] = useState(false);
  const [preflightLoading, setPreflightLoading] = useState(false);
  const [preflightError, setPreflightError] = useState<string | null>(null);
  const [preflightData, setPreflightData] = useState<DeployPreviewResponse | null>(null);
  const [startingDeploy, setStartingDeploy] = useState(false);
  const [chatVisible, setChatVisible] = useState(false);
  const [confirmingRollback, setConfirmingRollback] = useState(false);
  const [loginUserId, setLoginUserId] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [authChecking, setAuthChecking] = useState(true);
  const [loginLoading, setLoginLoading] = useState(false);
  const [loginMessage, setLoginMessage] = useState<string | null>(null);
  const [authUser, setAuthUser] = useState<string | null>(null);

  const blueGreenInfo = useMemo<BlueGreenPlan | null>(() => {
    if (previewDetail?.blue_green_plan) return previewDetail.blue_green_plan;
    if (previewDetail?.task_context?.summary?.blue_green) {
      return previewDetail.task_context.summary.blue_green as BlueGreenPlan;
    }
    return healthInfo?.blue_green ?? null;
  }, [previewDetail, healthInfo]);

  const mergedPreflightWarnings = useMemo(() => {
    if (!preflightData) return [];
    const notes = preflightData.risk_assessment?.notes;
    const noteList = Array.isArray(notes) ? notes : [];
    const diffWarnings = Array.isArray(preflightData.diff_stats?.warnings) ? preflightData.diff_stats?.warnings : [];
    const combined = [...(preflightData.warnings || []), ...diffWarnings, ...noteList].filter(
      (msg): msg is string => typeof msg === "string" && msg.trim().length > 0
    );
    return Array.from(new Set(combined));
  }, [preflightData]);

  const warnings = previewDetail?.warnings ?? [];
  const previewTimeline = previewDetail?.timeline_preview ?? [];
  const liveStages = Object.entries(currentStages || {});
  const llmSummary = previewDetail?.llm_preview?.summary ?? null;
  const riskAssessment: RiskAssessment | null = previewDetail?.risk_assessment ?? null;
  const preflightDiffStats: DiffStats | null = preflightData?.diff_stats ?? null;
  const preflightDiffSource: DiffSource | null = preflightData?.diff_source ?? null;
  const preflightCompareMetadata = preflightData?.compare_metadata ?? null;
  const compareAheadRaw = preflightCompareMetadata?.["ahead_by"];
  const compareBehindRaw = preflightCompareMetadata?.["behind_by"];
  const compareHtmlUrlRaw = preflightCompareMetadata?.["html_url"];
  const comparePermalinkRaw = preflightCompareMetadata?.["permalink_url"];
  const preflightCompareAhead = typeof compareAheadRaw === "number" ? compareAheadRaw : null;
  const preflightCompareBehind = typeof compareBehindRaw === "number" ? compareBehindRaw : null;
  const preflightCompareHtmlUrl = typeof compareHtmlUrlRaw === "string" ? (compareHtmlUrlRaw as string) : null;
  const preflightComparePermalink =
    typeof comparePermalinkRaw === "string" ? (comparePermalinkRaw as string) : null;
  const preflightTimeline = useMemo(() => preflightData?.timeline_preview ?? [], [preflightData]);
  const preflightEstimatedSeconds = useMemo<number | null>(() => {
    if (!preflightTimeline.length) return null;
    let total = 0;
    preflightTimeline.forEach((entry) => {
      const eta = typeof entry.expected_seconds === "number" ? entry.expected_seconds : null;
      const metadata = (entry.metadata || {}) as Record<string, unknown>;
      const metadataEta = typeof metadata["eta_seconds"] === "number" ? (metadata["eta_seconds"] as number) : null;
      const candidate = eta ?? metadataEta;
      if (typeof candidate === "number" && !Number.isNaN(candidate)) {
        total += candidate;
      }
    });
    return total > 0 ? total : null;
  }, [preflightTimeline]);
  const preflightRuntimeMinutes = preflightEstimatedSeconds ? Math.max(1, Math.round(preflightEstimatedSeconds / 60)) : null;
  const preflightCommands = preflightData?.commands ?? [];
  const preflightHighlights = preflightData?.llm_preview?.highlights ?? [];
  const preflightLlmRisks = preflightData?.llm_preview?.risks ?? [];
  const preflightRiskAssessment: RiskAssessment | null = preflightData?.risk_assessment ?? null;
  const preflightBlueGreenPlan = preflightData?.blue_green_plan ?? null;
  const preflightFilesChanged =
    typeof preflightDiffStats?.file_count === "number"
      ? preflightDiffStats.file_count
      : typeof preflightRiskAssessment?.files_changed === "number"
      ? preflightRiskAssessment.files_changed
      : null;
  const preflightAddedCount =
    typeof preflightDiffStats?.added === "number" ? preflightDiffStats.added : null;
  const preflightModifiedCount =
    typeof preflightDiffStats?.modified === "number" ? preflightDiffStats.modified : null;
  const preflightDeletedCount =
    typeof preflightDiffStats?.deleted === "number" ? preflightDiffStats.deleted : null;
  const preflightDowntimeNote =
    typeof preflightRiskAssessment?.downtime === "string" ? preflightRiskAssessment.downtime : null;
  const preflightRollbackNote =
    typeof preflightRiskAssessment?.rollback === "string" ? preflightRiskAssessment.rollback : null;

  const handleAuthError = useCallback(
    (err: unknown, contextMessage?: string) => {
      if (axios.isAxiosError(err) && err.response?.status === 401) {
        setIsLoggedIn(false);
        setAuthUser(null);
        setLoginMessage("세션이 만료되었습니다. 다시 로그인하세요.");
        setLoading(false);
        if (contextMessage) {
          setError(contextMessage);
        }
        return true;
      }
      return false;
    },
    []
  );

  const fetchPreview = useCallback(
    async (task?: string | null) => {
      if (!isLoggedIn) {
        return;
      }
      try {
        const res = await api.get<DeployPreviewResponse>("/api/v1/preview", {
          params: task ? { task_id: task } : undefined,
        });
        setPreviewDetail(res.data);
        setLastUpdate(new Date().toLocaleTimeString());
      } catch (err) {
        if (!handleAuthError(err, "⚠️ 프리뷰 로드 실패")) {
          console.error(err);
          setError("⚠️ 프리뷰 로드 실패");
        }
      } finally {
        setLoading(false);
      }
    },
    [handleAuthError, isLoggedIn]
  );

  const fetchHealth = useCallback(async () => {
    if (!isLoggedIn) return;
    try {
      const res = await api.get<HealthStatusResponse>("/healthz");
      setHealthInfo(res.data);
    } catch (err) {
      if (!handleAuthError(err)) {
        console.error(err);
      }
      setHealthInfo(null);
    }
  }, [handleAuthError, isLoggedIn]);

  const fetchRecent = useCallback(async () => {
    if (!isLoggedIn) return;
    try {
      const res = await api.get<DeployTaskSummary[]>("/api/v1/tasks/recent", {
        params: { limit: 5 },
      });
      setRecentTasks(res.data);
    } catch (err) {
      if (!handleAuthError(err)) {
        console.error(err);
      }
    }
  }, [handleAuthError, isLoggedIn]);

  const checkAuth = async () => {
    setAuthChecking(true);
    let authenticated = false;
    try {
      const res = await api.get<MeResponse>("/api/v1/auth/me");
      authenticated = true;
      setIsLoggedIn(true);
      setAuthUser(res.data.username);
      setLoginMessage(null);
    } catch (err) {
      console.warn("auth check failed", err);
      setIsLoggedIn(false);
      setAuthUser(null);
    } finally {
      setAuthChecking(false);
      if (!authenticated) {
        setLoading(false);
      }
    }
  };

  const handleLoginSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLoginMessage(null);
    setLoginLoading(true);
    try {
      const res = await api.post<LoginResponse>("/api/v1/auth/login", {
        username: loginUserId,
        password: loginPassword,
      });
      setAuthUser(res.data.username);
      setIsLoggedIn(true);
      setLoginUserId("");
      setLoginPassword("");
      setLoginMessage("로그인 성공");
      fetchPreview();
      fetchHealth();
      fetchRecent();
    } catch (err) {
      console.error(err);
      setIsLoggedIn(false);
      setLoginMessage("로그인 실패: ID/PW를 확인하세요.");
    } finally {
      setLoginLoading(false);
    }
  };

  const handleLogout = async () => {
    try {
      await api.post<LogoutResponse>("/api/v1/auth/logout");
    } catch (err) {
      console.error(err);
    } finally {
      setIsLoggedIn(false);
      setAuthUser(null);
      setLoginMessage("로그아웃되었습니다.");
      setTaskId(null);
      persistTaskId(null);
      setLoading(false);
    }
  };

  const persistTaskId = (value: string | null) => {
    if (typeof window === "undefined") return;
    if (value) {
      window.sessionStorage.setItem(CURRENT_TASK_STORAGE_KEY, value);
    } else {
      window.sessionStorage.removeItem(CURRENT_TASK_STORAGE_KEY);
    }
  };

  const releaseHeroOverride = (delayMs = 0) => {
    if (heroOverrideTimer.current) {
      clearTimeout(heroOverrideTimer.current);
      heroOverrideTimer.current = null;
    }
    if (delayMs <= 0) {
      setHeroOverrideStatus(null);
      return;
    }
    heroOverrideTimer.current = setTimeout(() => {
      setHeroOverrideStatus(null);
      heroOverrideTimer.current = null;
    }, delayMs);
  };

  const primeTaskState = (nextStatus: keyof typeof PROGRESS_BY_STATUS = "pending") => {
    releaseHeroOverride();
    setState({ status: nextStatus, timestamp: new Date().toISOString() });
    setCurrentStages({});
    setFailureInfo(null);
    setHeroOverrideStatus(nextStatus);
  };

  const handleOpenPreflight = async () => {
    if (!isLoggedIn) {
      setError("로그인이 필요합니다.");
      return;
    }
    setPreflightOpen(true);
    setPreflightLoading(true);
    setPreflightError(null);
    try {
      const res = await api.get<DeployPreviewResponse>("/api/v1/preview", {
        params: { mode: "preflight" },
      });
      setPreflightData(res.data);
    } catch (err) {
      console.error(err);
      setPreflightError("프리뷰 정보를 불러오지 못했습니다.");
    } finally {
      setPreflightLoading(false);
    }
  };

  const closePreflight = () => {
    if (startingDeploy) return;
    setPreflightOpen(false);
    setPreflightData(null);
    setPreflightError(null);
  };

  const confirmDeploy = async () => {
    if (!isLoggedIn) {
      setError("로그인이 필요합니다.");
      return;
    }
    if (startingDeploy) return;
    setStartingDeploy(true);
    setDeploying(true);
    setError(null);
    setFailureInfo(null);
    primeTaskState("pending");
    try {
      const res = await api.post("/api/v1/deploy", { branch: "deploy" });
      setTaskId(res.data.task_id);
      persistTaskId(res.data.task_id);
      await fetchRecent();
      setPreflightOpen(false);
      setPreflightData(null);
    } catch (err) {
      if (!handleAuthError(err, "배포 요청 실패")) {
        console.error(err);
        setError("배포 요청 실패");
      }
      setDeploying(false);
    } finally {
      setStartingDeploy(false);
    }
  };

  const handleRollback = async () => {
    if (rollbacking) return;
    if (!isLoggedIn) {
      setError("로그인이 필요합니다.");
      return;
    }
    setConfirmingRollback(true);
  };

  const confirmRollback = async () => {
    if (rollbacking) return;
    setRollbacking(true);
    primeTaskState("pending");
    try {
      const res = await api.post("/api/v1/rollback", { branch: "deploy" });
      setTaskId(res.data.task_id);
      persistTaskId(res.data.task_id);
      await fetchRecent();
      setConfirmingRollback(false);
    } catch (err) {
      if (!handleAuthError(err, "롤백 실패")) {
        console.error(err);
        setError("롤백 실패");
      }
    } finally {
      setRollbacking(false);
    }
  };

  useEffect(() => {
    heroOverrideStatusRef.current = heroOverrideStatus;
  }, [heroOverrideStatus]);

  useEffect(() => {
    return () => {
      if (heroOverrideTimer.current) {
        clearTimeout(heroOverrideTimer.current);
      }
    };
  }, []);

  useEffect(() => {
    if (!isLoggedIn) return;
    fetchPreview();
    fetchHealth();
    fetchRecent();
    const previewTimer = setInterval(fetchPreview, 30000);
    const healthTimer = setInterval(fetchHealth, 20000);
    const recentTimer = setInterval(fetchRecent, 45000);
    return () => {
      clearInterval(previewTimer);
      clearInterval(healthTimer);
      clearInterval(recentTimer);
    };
  }, [fetchHealth, fetchPreview, fetchRecent, isLoggedIn]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const saved = window.sessionStorage.getItem(CURRENT_TASK_STORAGE_KEY);
    if (saved) {
      setTaskId(saved);
      setDeploying(true);
    }
  }, []);

  useEffect(() => {
    checkAuth();
  }, []);

  useEffect(() => {
    if (!taskId || !isLoggedIn) return;
    fetchPreview(taskId);
  }, [fetchPreview, isLoggedIn, taskId]);

  useEffect(() => {
    if (!taskId || !isLoggedIn) return;
    const interval = setInterval(async () => {
      try {
        const res = await api.get(`/api/v1/status/${taskId}`);
        const payload = res.data;
        setState({ status: payload.status, timestamp: new Date().toISOString() });
        setCurrentStages(payload.stages || {});
        setFailureInfo(payload.failure_context || null);
        setTaskTimezone(payload.timezone || "Asia/Seoul");
        if (heroOverrideStatusRef.current) {
          releaseHeroOverride(1000);
        }
        setLastUpdate(new Date().toLocaleTimeString());
        if (["completed", "failed"].includes(payload.status)) {
          setDeploying(false);
          setTaskId(null);
          persistTaskId(null);
          releaseHeroOverride();
          fetchRecent();
          fetchPreview();
          clearInterval(interval);
        }
      } catch (err) {
        if (!handleAuthError(err)) {
          console.error(err);
        }
        setDeploying(false);
        setTaskId(null);
        persistTaskId(null);
        releaseHeroOverride();
        clearInterval(interval);
      }
    }, 3000);
    return () => clearInterval(interval);
  }, [fetchPreview, fetchRecent, handleAuthError, isLoggedIn, taskId]);

  const effectiveHeroStatus = heroOverrideStatus || state.status || "pending";
  const heroProgress = PROGRESS_BY_STATUS[effectiveHeroStatus] ?? 8;
  const cardStatusColor =
    effectiveHeroStatus === "completed"
      ? "text-green-400"
      : effectiveHeroStatus === "failed"
      ? "text-red-400"
      : "text-yellow-400";
  const showReloadNotice = Boolean(taskId);

  const formatDateTime = (value?: string | null, timezone = "Asia/Seoul") => {
    if (!value) return "정보 없음";
    const formatter = new Intl.DateTimeFormat("ko-KR", {
      timeZone: timezone,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "numeric",
      minute: "2-digit",
      second: "2-digit",
      hour12: true,
    });
    const badge = timezone === "Asia/Seoul" ? "KST" : timezone;
    return `${formatter.format(new Date(value))} (${badge})`;
  };

  const formatTimeOnly = (value?: string | null, timezone = "Asia/Seoul") => {
    if (!value) return null;
    const formatter = new Intl.DateTimeFormat("ko-KR", {
      timeZone: timezone,
      hour: "numeric",
      minute: "2-digit",
      second: "2-digit",
      hour12: true,
    });
    return formatter.format(new Date(value));
  };

  const formatDurationLabel = (seconds?: number | null) => {
    if (typeof seconds !== "number" || Number.isNaN(seconds)) return null;
    if (seconds >= 60) {
      const minutes = Math.round(seconds / 60);
      return `약 ${minutes}분`;
    }
    return `약 ${Math.max(1, Math.round(seconds))}초`;
  };

  const renderRiskBadge = (risk?: string | null) => {
    if (!risk) return null;
    const normalized = risk.trim().toLowerCase();
    const palette: Record<string, string> = {
      low: "border-green-500/60 text-green-200 bg-green-900/30",
      medium: "border-yellow-500/60 text-yellow-200 bg-yellow-900/30",
      high: "border-red-500/60 text-red-200 bg-red-900/30",
    };
    const tone = palette[normalized] || "border-gray-500/60 text-gray-200 bg-gray-800/60";
    return (
      <span className={`text-[11px] uppercase tracking-wide px-3 py-1 rounded-full border ${tone}`}>
        {normalized.toUpperCase()}
      </span>
    );
  };

  const resolveSlotLabel = (value?: string | null) => {
    if (!value) return null;
    const normalized = value.trim().toLowerCase();
    if (!normalized || normalized === "unknown" || normalized === "n/a") return null;
    return value;
  };

  const resolveActor = (task: DeployTaskSummary) => {
    const directActor = task.actor;
    const summary = task.summary as TaskSummaryData | undefined;
    const metadata = task.metadata as TaskMetadata | undefined;
    const authorName = summary?.git_commit?.author?.name;
    const authorEmail = summary?.git_commit?.author?.email;
    const summaryActor = summary?.actor;
    const metadataActor = metadata?.actor || metadata?.requested_by || metadata?.trigger;
    return directActor || authorName || authorEmail || summaryActor || metadataActor || "기록 없음";
  };

  const formatInfoValue = (value: unknown): string => {
    if (value === null || value === undefined) return "정보 없음";
    if (Array.isArray(value)) {
      return value.map((item) => (typeof item === "string" ? item : JSON.stringify(item))).join(", ");
    }
    if (typeof value === "object") {
      try {
        return JSON.stringify(value, null, 2);
      } catch {
        return String(value);
      }
    }
    return String(value);
  };

  const renderHero = () => {
    if (taskId) {
      const timezoneBadge = taskTimezone === "Asia/Seoul" ? "KST" : taskTimezone;
      const displayStatus = effectiveHeroStatus.replace("running_", "RUNNING ").toUpperCase();
      return (
        <div className="bg-gray-800 rounded-2xl border border-gray-700 p-6 mb-8">
          <div className="flex items-center justify-between flex-wrap gap-3">
            <div>
              <p className="text-sm text-gray-400">현재 배포 Task</p>
              <p className="text-2xl font-semibold text-white">{taskId}</p>
              <p className="text-xs text-gray-500 mt-1">표준시: {timezoneBadge}</p>
            </div>
            <p className={`text-lg font-semibold ${cardStatusColor}`}>
              {displayStatus}
            </p>
          </div>
          <div className="mt-4 h-3 bg-gray-900 rounded-full overflow-hidden">
            <div className="h-full bg-blue-500 transition-all" style={{ width: `${heroProgress}%` }} />
          </div>
          <p className="text-xs text-gray-500 mt-2">
            pending → running_clone → running_build → running_cutover → running_observability → completed
          </p>
          {blueGreenInfo && (
            <div className="mt-4 text-sm text-gray-300 space-y-1">
              {resolveSlotLabel(blueGreenInfo.active_slot) ? (
                <p>
                  Active Slot: <span className="text-white font-semibold">{blueGreenInfo.active_slot}</span>
                </p>
              ) : (
                <p>Active Slot 정보 없음</p>
              )}
              {resolveSlotLabel(blueGreenInfo.next_cutover_target) && <p>Next Target: {blueGreenInfo.next_cutover_target}</p>}
            </div>
          )}
        </div>
      );
    }

    return (
      <div className="bg-gray-800 rounded-2xl border border-gray-700 p-6 mb-8">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <p className="text-sm text-gray-400">Cherry Deploy</p>
            <p className="text-2xl font-semibold text-white">Safe Deployment with a Single Click</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {!isLoggedIn ? (
              <>
                <form className="flex flex-wrap items-center gap-2" onSubmit={handleLoginSubmit}>
                  <input
                    type="text"
                    value={loginUserId}
                    onChange={(event) => setLoginUserId(event.target.value)}
                    placeholder="ID"
                    disabled={loginLoading || authChecking}
                    className="rounded-lg border border-gray-600 bg-gray-900 px-3 py-2 text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-60"
                  />
                  <input
                    type="password"
                    value={loginPassword}
                    onChange={(event) => setLoginPassword(event.target.value)}
                    placeholder="PW"
                    disabled={loginLoading || authChecking}
                    className="rounded-lg border border-gray-600 bg-gray-900 px-3 py-2 text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-60"
                  />
                  <button
                    type="submit"
                    disabled={loginLoading || authChecking}
                    className="px-4 py-2 rounded-lg border border-gray-600 text-sm font-semibold text-gray-200 hover:bg-gray-800 disabled:opacity-60"
                  >
                    {loginLoading ? "..." : "로그인"}
                  </button>
                </form>
                {loginMessage && (
                  <p className="text-xs text-gray-400 min-w-[120px] text-right">{loginMessage}</p>
                )}
              </>
            ) : (
              <div className="flex items-center gap-2 text-sm text-gray-300">
                <span className="font-semibold text-white">{authUser || "로그인됨"}</span>
                <button
                  type="button"
                  onClick={handleLogout}
                  className="px-3 py-2 rounded-lg border border-gray-600 text-xs font-semibold text-gray-200 hover:bg-gray-800"
                  disabled={authChecking}
                >
                  로그아웃
                </button>
                {loginMessage && <p className="text-xs text-gray-400">{loginMessage}</p>}
              </div>
            )}
            <div className="flex gap-2">
              <button
                onClick={handleOpenPreflight}
                disabled={!isLoggedIn}
                className={`px-4 py-2 rounded-lg text-sm font-semibold ${
                  isLoggedIn
                    ? "bg-blue-600 hover:bg-blue-500"
                    : "bg-gray-700 text-gray-400 cursor-not-allowed"
                }`}
              >
                Prepare Deploy
              </button>
              <button
                onClick={handleRollback}
                disabled={rollbacking || !isLoggedIn}
                className={`px-4 py-2 rounded-lg border text-sm font-semibold ${
                  rollbacking || !isLoggedIn
                    ? "border-gray-600 text-gray-400 cursor-not-allowed"
                    : "border-red-500 text-red-300 hover:bg-red-500/10"
                }`}
              >
                {rollbacking ? "Rolling Back..." : "Rollback"}
              </button>
            </div>
          </div>
        </div>

        <p className="mt-4 text-gray-200 whitespace-pre-line">
          {llmSummary || "배포 준비” 버튼을 눌러 최신 변경 요약과 위험 요소를 확인한 뒤 실제 배포를 실행하세요."}
        </p>
        {blueGreenInfo ? (
          <div className="mt-3 text-sm text-gray-400 space-y-1">
            {resolveSlotLabel(blueGreenInfo.active_slot) ? (
              <p>
                Active Slot: <span className="text-white">{blueGreenInfo.active_slot}</span>
              </p>
            ) : (
              <p>Active Slot 정보 없음</p>
            )}
            {resolveSlotLabel(blueGreenInfo.standby_slot) && (
              <p>
                Standby: <span className="text-white">{blueGreenInfo.standby_slot}</span>
              </p>
            )}
          </div>
        ) : (
          <p className="mt-3 text-sm text-gray-500">Blue/Green 메타데이터를 수집하는 중입니다.</p>
        )}
      </div>
    );
  };

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-gray-900 text-gray-400">
        ⏳ 데이터를 불러오는 중입니다...
      </div>
    );
  }

  return (
    <>
      <motion.div
        className="pointer-events-none fixed inset-0 z-[200]"
        initial={{ opacity: 0.95 }}
        animate={{ opacity: chatVisible ? 0 : 0.95 }}
        transition={{ duration: 0.4, ease: "easeOut" }}
      >
        <FloatingCharacter progress={heroProgress} />
      </motion.div>
      <motion.div className="relative text-gray-200 p-6 md:p-8 min-h-screen bg-gray-900" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.6 }}>
      <div className="flex items-center justify-between flex-wrap gap-3 mb-4">
        <motion.h2 className="text-3xl font-bold text-blue-400">Cherry Deploy Dashboard</motion.h2>
        <p className="text-sm text-gray-400">마지막 업데이트: {lastUpdate || "-"}</p>
      </div>

      {error && (
        <div className="mb-4 rounded border border-red-600 bg-red-900/30 px-4 py-3 text-sm text-red-200">{error}</div>
      )}

      {showReloadNotice && (
        <div className="mb-4 rounded border border-yellow-600 bg-yellow-900/30 px-4 py-2 text-sm text-yellow-200">
          dev 서버 재시작 중입니다. 화면이 자동으로 새로고침되어도 배포 작업은 계속 진행됩니다.
        </div>
      )}

      {renderHero()}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <motion.div className="bg-gray-800 p-6 rounded-2xl border border-gray-800" variants={cardVariants} initial="hidden" animate="visible" custom={0}>
          <div className="flex items-center justify-between">
            <p className="text-lg font-semibold">🛠 Preview Timeline</p>
            <button onClick={() => fetchPreview(taskId)} className="text-xs px-2 py-1 bg-gray-700 rounded hover:bg-gray-600">
              새로고침
            </button>
          </div>
          {previewTimeline.length ? (
            <ul className="mt-4 space-y-2 text-sm">
              {previewTimeline.map((entry: DeployTimelineEntry) => {
                const metadata = (entry.metadata || {}) as Record<string, unknown>;
                const plan = metadata["plan"];
                const checks = metadata["checks"];
                const etaSeconds = metadata["eta_seconds"];
                const hasMetadataDetails =
                  Boolean(plan) || Boolean(checks) || typeof etaSeconds === "number";
                return (
                  <li key={entry.stage} className="flex items-start gap-2">
                    <span className={entry.completed ? "text-green-400" : "text-gray-600"}>•</span>
                    <div>
                      <p className="text-gray-100">{entry.label}</p>
                      {entry.expected_seconds && <p className="text-xs text-gray-500">예상 {entry.expected_seconds}s</p>}
                      {hasMetadataDetails && (
                        <div className="mt-1 space-y-1 text-xs text-gray-400">
                          {plan !== undefined && plan !== null && (
                            <p>
                              <span className="text-[10px] uppercase tracking-wide text-gray-500">Plan</span>{" "}
                              {formatInfoValue(plan)}
                            </p>
                          )}
                          {checks !== undefined && checks !== null && (
                            <p>
                              <span className="text-[10px] uppercase tracking-wide text-gray-500">Checks</span>{" "}
                              {formatInfoValue(checks)}
                            </p>
                          )}
                          {typeof etaSeconds === "number" && (
                            <p>
                              <span className="text-[10px] uppercase tracking-wide text-gray-500">ETA</span> 약 {etaSeconds}초
                            </p>
                          )}
                        </div>
                      )}
                    </div>
                  </li>
                );
              })}
            </ul>
          ) : (
            <p className="mt-4 text-sm text-gray-500">프리뷰 데이터를 불러오는 중입니다.</p>
          )}
        </motion.div>

        <motion.div className="bg-gray-800 p-6 rounded-2xl border border-gray-800" variants={cardVariants} initial="hidden" animate="visible" custom={1}>
          <p className="text-lg font-semibold">📡 Live Stages</p>
          {liveStages.length ? (
            <ul className="mt-4 space-y-2 text-sm">
              {liveStages.map(([stage, details]) => {
                const timestamp =
                  details && typeof details.timestamp === "string"
                    ? formatTimeOnly(details.timestamp, taskTimezone)
                    : null;
                return (
                  <li key={stage} className="flex items-start gap-2">
                    <span className="text-blue-400">•</span>
                    <div>
                      <p className="text-gray-100">{stage}</p>
                      {timestamp && <p className="text-xs text-gray-500">{timestamp}</p>}
                    </div>
                  </li>
                );
              })}
            </ul>
          ) : (
            <p className="mt-4 text-sm text-gray-500">진행 중인 Stage 정보가 없습니다.</p>
          )}
          <p className="text-xs text-gray-500 mt-3">Timezone: {taskTimezone === "Asia/Seoul" ? "KST" : taskTimezone}</p>
          {failureInfo && (
            <div className="mt-4 text-xs text-red-200 bg-red-900/20 border border-red-700 rounded p-3 whitespace-pre-wrap">
              {JSON.stringify(failureInfo, null, 2)}
            </div>
          )}
        </motion.div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <motion.div className="bg-gray-800 p-6 rounded-2xl border border-gray-800" variants={cardVariants} initial="hidden" animate="visible" custom={2}>
          <div className="flex items-center justify-between">
            <p className="text-lg font-semibold">💠 Blue / Green 상태</p>
            <button onClick={fetchHealth} className="text-xs px-2 py-1 bg-gray-700 rounded hover:bg-gray-600">
              healthz 갱신
            </button>
          </div>
          {blueGreenInfo ? (
            <div className="mt-4 space-y-2 text-sm">
              {resolveSlotLabel(blueGreenInfo.active_slot) && (
                <p>
                  Active Slot: <span className="text-white font-semibold">{blueGreenInfo.active_slot}</span>
                </p>
              )}
              {resolveSlotLabel(blueGreenInfo.standby_slot) && (
                <p>
                  Standby Slot: <span className="text-white font-semibold">{blueGreenInfo.standby_slot}</span>
                </p>
              )}
              <p>
                마지막 컷오버:{" "}
                {blueGreenInfo.last_cutover_at ? formatDateTime(blueGreenInfo.last_cutover_at, previewDetail?.timezone || "Asia/Seoul") : "기록 없음"}
              </p>
              {resolveSlotLabel(blueGreenInfo.next_cutover_target) && <p>다음 전환 예정: {blueGreenInfo.next_cutover_target}</p>}
            </div>
          ) : (
            <p className="mt-4 text-sm text-gray-500">Blue/Green 메타데이터가 아직 없습니다.</p>
          )}
        </motion.div>

        <motion.div className="bg-gray-800 p-6 rounded-2xl border border-gray-800" variants={cardVariants} initial="hidden" animate="visible" custom={3}>
          <p className="text-lg font-semibold">⚠ Preview Warnings</p>
          {warnings.length ? (
            <ul className="mt-3 list-disc list-inside space-y-1 text-sm text-yellow-200">
              {warnings.map((warn, idx) => (
                <li key={`warn-${idx}`}>{warn}</li>
              ))}
            </ul>
          ) : (
            <p className="mt-3 text-sm text-gray-500">경고 데이터가 없습니다.</p>
          )}
        </motion.div>
      </div>

      <motion.div className="bg-gray-800 p-6 rounded-2xl border border-gray-800 mb-6" variants={cardVariants} initial="hidden" animate="visible" custom={4}>
        <p className="text-lg font-semibold">📉 Risk Assessment</p>
        {riskAssessment ? (
          <ul className="mt-4 space-y-3 text-sm">
            {Object.entries(riskAssessment).map(([key, value]) => (
              <li key={`risk-${key}`}>
                <p className="text-xs uppercase tracking-wide text-gray-500">{key}</p>
                <p className="text-gray-100 whitespace-pre-wrap">{formatInfoValue(value)}</p>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-4 text-sm text-gray-500">위험 정보가 아직 없습니다.</p>
        )}
      </motion.div>

      <motion.div className="bg-gray-800 p-6 rounded-2xl border border-gray-800 mb-6" variants={cardVariants} initial="hidden" animate="visible" custom={5}>
        <div className="flex items-center justify-between mb-3">
          <p className="text-lg font-semibold">📝 Recent Tasks</p>
          <button onClick={fetchRecent} className="text-xs px-2 py-1 bg-gray-700 rounded hover:bg-gray-600">
            새로고침
          </button>
        </div>
        {recentTasks.length ? (
          <ul className="space-y-3 text-sm">
            {recentTasks.map((task) => {
              const timezone = task.timezone || "Asia/Seoul";
              const badge = timezone === "Asia/Seoul" ? "KST" : timezone;
              return (
                <li key={task.task_id} className="rounded border border-gray-700 p-3 bg-gray-900/30">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-white font-semibold">
                      {task.action.toUpperCase()} · {task.branch}
                    </p>
                    <span className="text-[10px] uppercase tracking-wide text-gray-500 border border-gray-600 px-2 py-0.5 rounded-full">
                      {badge}
                    </span>
                  </div>
                  <p className="text-xs text-gray-400">
                    {formatDateTime(task.started_at, timezone)} →{" "}
                    {task.completed_at ? formatDateTime(task.completed_at, timezone) : "진행 중"}
                  </p>
                  <p className="text-xs text-gray-300">status: {task.status} · actor: {resolveActor(task)}</p>
                </li>
              );
            })}
          </ul>
        ) : (
          <p className="text-sm text-gray-500">최근 작업 내역이 없습니다.</p>
        )}
      </motion.div>

      {chatVisible && (
        <ChatWidget
          onClose={() => setChatVisible(false)}
          stages={liveStages}
          stageTimezone={taskTimezone}
          heroStatus={effectiveHeroStatus}
        />
      )}
      {!chatVisible && (
        <button
          type="button"
          onClick={() => setChatVisible(true)}
          className="fixed bottom-6 right-6 z-[9000] bg-blue-600 hover:bg-blue-500 text-white rounded-full shadow-xl w-16 h-16 flex flex-col items-center justify-center gap-1"
          aria-label="챗봇 열기"
        >
          <span className="text-2xl">🤖</span>
          <span className="text-[10px] tracking-tight font-semibold">Chatbot</span>
        </button>
      )}

      {preflightOpen && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-[10000] p-4">
          <div className="w-full max-w-5xl flex flex-col md:flex-row gap-4">
            <div className="bg-gray-900 border border-gray-700 rounded-2xl md:h-[19rem] h-[15rem] p-6 flex flex-col items-center justify-center text-center md:w-64 relative">
              <span
                aria-hidden="true"
                className="md:hidden absolute -bottom-4 left-1/2 -translate-x-1/2 flex flex-col items-center"
              >
                <span className="block w-0 h-0 border-l-[18px] border-r-[18px] border-t-[22px] border-l-transparent border-r-transparent border-t-gray-700" />
                <span className="block w-0 h-0 -mt-4 border-l-[16px] border-r-[16px] border-t-[20px] border-l-transparent border-r-transparent border-t-gray-900" />
              </span>
              <span
                aria-hidden="true"
                className="hidden md:flex absolute top-1/2 -right-6 -translate-y-1/2 flex-col"
              >
                <span className="block w-0 h-0 border-t-[18px] border-b-[18px] border-l-[24px] border-t-transparent border-b-transparent border-l-gray-700" />
                <span className="block w-0 h-0 -mt-6 ml-[2px] border-t-[16px] border-b-[16px] border-l-[22px] border-t-transparent border-b-transparent border-l-gray-900" />
              </span>
              <Image
                src="/images/good.png"
                alt="Cherry assistant success"
                width={200}
                height={200}
                className="w-32 h-32 md:w-40 md:h-40 object-contain drop-shadow-[0_0_24px_rgba(80,255,200,0.35)]"
                priority={false}
                unoptimized
              />
              <p className="mt-4 text-sm text-gray-300">Cherry Assistant Ready</p>
            </div>
            <div className="bg-gray-900 border border-gray-700 rounded-2xl flex-1 md:flex-[1.3] p-6 relative">
              <button
                onClick={closePreflight}
                className="absolute top-3 right-3 text-gray-400 hover:text-white"
                aria-label="close"
                disabled={startingDeploy}
              >
                ✕
              </button>
              <h3 className="text-2xl font-semibold text-white mb-2">배포 사전 브리핑</h3>
              <p className="text-sm text-gray-400 mb-4">변경 요약과 위험 요소를 검토한 뒤 실제 배포를 진행하세요.</p>
              {preflightLoading ? (
                <p className="text-sm text-gray-400">Gemini 프리뷰를 불러오는 중...</p>
              ) : preflightError ? (
                <p className="text-sm text-red-400">{preflightError}</p>
              ) : preflightData ? (
                <div className="space-y-5 max-h-[65vh] overflow-auto pr-1">
                <section className="grid gap-4 md:grid-cols-2">
                  <div className="rounded-2xl border border-gray-800 bg-gray-950/50 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-xs uppercase tracking-wide text-blue-300">Gemini Diff Review</p>
                        <p className="text-lg font-semibold text-white mt-1">변경 요약</p>
                      </div>
                      <div className="flex flex-col items-end gap-2">
                        {renderRiskBadge(preflightRiskAssessment?.risk_level ?? null)}
                        {preflightDiffSource && (
                          <span
                            className={`text-[11px] uppercase tracking-wide px-3 py-1 rounded-full border ${
                              preflightDiffSource === "github_compare"
                                ? "border-purple-500/60 text-purple-200 bg-purple-900/40"
                                : "border-gray-500/60 text-gray-200 bg-gray-900/40"
                            }`}
                          >
                            {preflightDiffSource === "github_compare" ? "GitHub Compare" : "Working Tree"}
                          </span>
                        )}
                      </div>
                    </div>
                    <p className="mt-3 text-sm text-gray-100 whitespace-pre-line leading-relaxed">
                      {preflightData.llm_preview?.summary || "LLM 요약이 없습니다."}
                    </p>
                    {preflightHighlights.length ? (
                      <div className="mt-4 flex flex-wrap gap-2">
                        {preflightHighlights.map((item, idx) => (
                          <span
                            key={`preflight-highlight-${idx}`}
                            className="px-3 py-1 rounded-full border border-blue-500/40 bg-blue-500/10 text-xs text-blue-100"
                          >
                            {item}
                          </span>
                        ))}
                      </div>
                    ) : null}
                    {preflightLlmRisks.length ? (
                      <div className="mt-4">
                        <p className="text-xs uppercase tracking-wide text-yellow-300">Gemini 위험 포인트</p>
                        <ul className="mt-2 list-disc list-inside text-sm text-yellow-100 space-y-1">
                          {preflightLlmRisks.map((item, idx) => (
                            <li key={`preflight-llm-risk-${idx}`}>{item}</li>
                          ))}
                        </ul>
                      </div>
                    ) : null}
                    {preflightCompareMetadata && (preflightCompareAhead !== null || preflightCompareBehind !== null || preflightCompareHtmlUrl || preflightComparePermalink) && (
                      <div className="mt-4 text-xs text-gray-400 space-y-1 border border-gray-800 rounded-lg p-3 bg-gray-950/30">
                        <p className="text-[11px] uppercase tracking-wide text-gray-500">GitHub Compare 메타</p>
                        {preflightCompareAhead !== null && <p>Ahead by: <span className="text-gray-100 font-semibold">{preflightCompareAhead}</span></p>}
                        {preflightCompareBehind !== null && <p>Behind by: <span className="text-gray-100 font-semibold">{preflightCompareBehind}</span></p>}
                        {preflightCompareHtmlUrl && (
                          <p>
                            <a href={preflightCompareHtmlUrl} target="_blank" rel="noreferrer" className="text-blue-300 underline">
                              GitHub Compare 보기
                            </a>
                          </p>
                        )}
                        {!preflightCompareHtmlUrl && preflightComparePermalink && (
                          <p>
                            <a href={preflightComparePermalink} target="_blank" rel="noreferrer" className="text-blue-300 underline">
                              Permalink으로 열기
                            </a>
                          </p>
                        )}
                      </div>
                    )}
                  </div>
                  <div className="rounded-2xl border border-gray-800 bg-gray-950/40 p-4">
                    <p className="text-xs uppercase tracking-wide text-gray-500">배포 준비 지표</p>
                    <div className="mt-3 grid grid-cols-2 gap-4 text-sm">
                      <div>
                        <p className="text-[11px] uppercase tracking-wide text-gray-500">변경 파일</p>
                        <p className="text-2xl font-semibold text-white">{preflightFilesChanged ?? "-"}</p>
                        <p className="text-[11px] text-gray-500 mt-1">git diff 기준</p>
                      </div>
                      <div>
                        <p className="text-[11px] uppercase tracking-wide text-gray-500">예상 소요</p>
                        <p className="text-2xl font-semibold text-white">
                          {preflightRuntimeMinutes !== null ? `약 ${preflightRuntimeMinutes}분` : "정보 없음"}
                        </p>
                        <p className="text-[11px] text-gray-500 mt-1">stage 추정치</p>
                      </div>
                      <div>
                        <p className="text-[11px] uppercase tracking-wide text-gray-500">예상 다운타임</p>
                        <p className="text-sm font-semibold text-white leading-snug">
                          {preflightDowntimeNote || "Blue/Green 기반 최소화"}
                        </p>
                        <p className="text-[11px] text-gray-500 mt-1">LLM 추정</p>
                      </div>
                      <div>
                        <p className="text-[11px] uppercase tracking-wide text-gray-500">롤백 경로</p>
                        <p className="text-sm font-semibold text-white leading-snug">
                          {preflightRollbackNote || "심볼릭 링크 스왑 준비됨"}
                        </p>
                        <p className="text-[11px] text-gray-500 mt-1">즉시 전환 가능</p>
                      </div>
                    </div>
                    <div className="mt-4 text-xs text-gray-400 space-y-1">
                      <p>
                        브랜치: <span className="text-gray-100 font-semibold">{preflightData.current_branch}</span>
                      </p>
                      <p className="break-all">
                        Repo: <span className="text-gray-100">{preflightData.target_repo}</span>
                      </p>
                      {preflightData.frontend_project_path && (
                        <p className="break-all">
                          Build Path: <span className="text-gray-100">{preflightData.frontend_project_path}</span>
                        </p>
                      )}
                      {preflightData.frontend_output_path && (
                        <p className="break-all">
                          Export Path: <span className="text-gray-100">{preflightData.frontend_output_path}</span>
                        </p>
                      )}
                    </div>
                    {preflightDiffStats && (
                      <div className="mt-4 border-t border-gray-800 pt-4">
                        <p className="text-xs uppercase tracking-wide text-gray-500">Git diff 통계</p>
                        <div className="mt-3 grid grid-cols-3 gap-3 text-sm">
                          <div>
                            <p className="text-[11px] uppercase tracking-wide text-gray-500">추가</p>
                            <p className="text-xl font-semibold text-green-300">{preflightAddedCount ?? 0}</p>
                          </div>
                          <div>
                            <p className="text-[11px] uppercase tracking-wide text-gray-500">수정</p>
                            <p className="text-xl font-semibold text-yellow-200">{preflightModifiedCount ?? 0}</p>
                          </div>
                          <div>
                            <p className="text-[11px] uppercase tracking-wide text-gray-500">삭제</p>
                            <p className="text-xl font-semibold text-red-300">{preflightDeletedCount ?? 0}</p>
                          </div>
                        </div>
                        <div className="mt-3 flex flex-wrap gap-2 text-[11px]">
                          {[
                            { label: "Lockfile", active: Boolean(preflightDiffStats.lockfile_changed) },
                            { label: "Config", active: Boolean(preflightDiffStats.config_changed) },
                            { label: "Env", active: Boolean(preflightDiffStats.env_changed) },
                            { label: "Secrets", active: Boolean(preflightDiffStats.sensitive_changed) },
                            { label: "Tests", active: Boolean(preflightDiffStats.test_files_changed) },
                          ]
                            .filter((item) => item.active)
                            .map((item) => (
                              <span key={`diff-flag-${item.label}`} className="px-2 py-1 rounded-full border border-blue-500/50 text-blue-100 bg-blue-500/10">
                                {item.label} 변경
                              </span>
                            ))}
                          {!Boolean(
                            preflightDiffStats.lockfile_changed ||
                              preflightDiffStats.config_changed ||
                              preflightDiffStats.env_changed ||
                              preflightDiffStats.sensitive_changed ||
                              preflightDiffStats.test_files_changed
                          ) && <span className="text-gray-500">특별 플래그 없음</span>}
                        </div>
                      </div>
                    )}
                  </div>
                </section>
                <section className="grid gap-4 md:grid-cols-2">
                  <div className="rounded-2xl border border-gray-800 bg-gray-950/40 p-4">
                    <p className="text-xs uppercase tracking-wide text-gray-500">예상 Stage Timeline</p>
                    {preflightTimeline.length ? (
                      <ul className="mt-3 space-y-3">
                        {preflightTimeline.map((entry, idx) => {
                          const metadata = (entry.metadata || {}) as Record<string, unknown>;
                          const checksRaw = metadata.checks;
                          const checks = Array.isArray(checksRaw)
                            ? (checksRaw.filter((check): check is string => typeof check === "string") as string[])
                            : [];
                          const etaFromMeta = typeof metadata.eta_seconds === "number" ? metadata.eta_seconds : undefined;
                          const etaLabel = formatDurationLabel(entry.expected_seconds ?? etaFromMeta);
                          const plan = typeof metadata.plan === "string" ? metadata.plan : null;
                          const statusTone =
                            entry.status === "completed"
                              ? "border-green-500/60 text-green-200"
                              : entry.status === "upcoming"
                              ? "border-blue-500/60 text-blue-200"
                              : "border-gray-600 text-gray-300";
                          return (
                            <li key={`preflight-stage-${entry.stage}`} className="flex gap-3">
                              <div className={`flex h-8 w-8 items-center justify-center rounded-full border ${statusTone}`}>
                                {idx + 1}
                              </div>
                              <div className="flex-1">
                                <div className="flex items-center gap-2">
                                  <p className="text-sm font-semibold text-white">{entry.label}</p>
                                  {etaLabel && <span className="text-xs text-gray-400">{etaLabel}</span>}
                                </div>
                                <p className="text-[11px] uppercase tracking-wide text-gray-500">
                                  {entry.stage.replace(/_/g, " ").toUpperCase()}
                                </p>
                                {plan && <p className="text-xs text-gray-300 mt-1">{plan}</p>}
                                {checks.length ? (
                                  <ul className="mt-1 space-y-0.5 text-xs text-gray-400">
                                    {checks.map((check, checkIdx) => (
                                      <li
                                        key={`preflight-stage-${entry.stage}-check-${checkIdx}`}
                                        className="flex items-start gap-1"
                                      >
                                        <span className="text-blue-400 mt-0.5">▹</span>
                                        <span>{check}</span>
                                      </li>
                                    ))}
                                  </ul>
                                ) : null}
                              </div>
                            </li>
                          );
                        })}
                      </ul>
                    ) : (
                      <p className="mt-3 text-sm text-gray-500">예상 타임라인을 가져오지 못했습니다.</p>
                    )}
                  </div>
                  <div className="rounded-2xl border border-gray-800 bg-gray-950/40 p-4">
                    <p className="text-xs uppercase tracking-wide text-gray-500">실행 명령 시퀀스</p>
                    {preflightCommands.length ? (
                      <ol className="mt-3 space-y-2 text-xs text-gray-100">
                        {preflightCommands.map((cmd, idx) => (
                          <li
                            key={`preflight-cmd-${idx}`}
                            className="rounded border border-gray-800 bg-gray-900/40 p-3 flex items-start gap-3"
                          >
                            <span className="text-[10px] text-gray-500 pt-0.5">#{idx + 1}</span>
                            <code className="text-[13px] leading-relaxed break-all">{cmd}</code>
                          </li>
                        ))}
                      </ol>
                    ) : (
                      <p className="mt-3 text-sm text-gray-500">명령 플랜이 없습니다.</p>
                    )}
                  </div>
                </section>
                <section className="grid gap-4 md:grid-cols-2">
                  <div className="rounded-2xl border border-gray-800 bg-gray-950/40 p-4">
                    <p className="text-xs uppercase tracking-wide text-gray-500">자동 경고 & 체커</p>
                    {mergedPreflightWarnings.length ? (
                      <ul className="mt-3 space-y-2">
                        {mergedPreflightWarnings.map((warn, idx) => (
                          <li
                            key={`preflight-warning-${idx}`}
                            className="rounded border border-yellow-700 bg-yellow-900/25 px-3 py-2 text-sm text-yellow-100"
                          >
                            {warn}
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="mt-3 text-sm text-gray-500">경고 데이터가 없습니다.</p>
                    )}
                  </div>
                  <div className="rounded-2xl border border-gray-800 bg-gray-950/40 p-4">
                    <p className="text-xs uppercase tracking-wide text-gray-500">Blue/Green 준비 상태</p>
                    {preflightBlueGreenPlan ? (
                      <dl className="mt-3 space-y-2 text-sm text-gray-200">
                        {resolveSlotLabel(preflightBlueGreenPlan.active_slot) && (
                          <div>
                            <dt className="text-xs uppercase tracking-wide text-gray-500">현재 서비스</dt>
                            <dd className="text-white font-semibold">{preflightBlueGreenPlan.active_slot}</dd>
                          </div>
                        )}
                        {resolveSlotLabel(preflightBlueGreenPlan.standby_slot) && (
                          <div>
                            <dt className="text-xs uppercase tracking-wide text-gray-500">대기 슬롯</dt>
                            <dd>{preflightBlueGreenPlan.standby_slot}</dd>
                          </div>
                        )}
                        {resolveSlotLabel(preflightBlueGreenPlan.next_cutover_target) && (
                          <div>
                            <dt className="text-xs uppercase tracking-wide text-gray-500">다음 컷오버</dt>
                            <dd>{preflightBlueGreenPlan.next_cutover_target}</dd>
                          </div>
                        )}
                        <div>
                          <dt className="text-xs uppercase tracking-wide text-gray-500">마지막 컷오버</dt>
                          <dd>
                            {preflightBlueGreenPlan.last_cutover_at
                              ? formatDateTime(preflightBlueGreenPlan.last_cutover_at, preflightData.timezone || "Asia/Seoul")
                              : "기록 없음"}
                          </dd>
                        </div>
                      </dl>
                    ) : (
                      <p className="mt-3 text-sm text-gray-500">Blue/Green 계획 정보가 없습니다.</p>
                    )}
                  </div>
                </section>
                <section className="rounded border border-yellow-700 bg-yellow-900/30 p-4 text-sm text-yellow-100">
                  실제 배포 버튼을 누르면 dev 서버를 재기동하므로 화면이 잠시 리셋될 수 있습니다. 창을 닫아도 작업은 계속됩니다.
                </section>
              </div>
            ) : (
              <p className="text-sm text-gray-500">프리뷰 데이터를 가져오지 못했습니다.</p>
            )}
            <div className="mt-6 flex justify-end gap-3">
              <button onClick={closePreflight} disabled={startingDeploy} className="px-4 py-2 rounded border border-gray-600 text-gray-200 hover:bg-gray-800">
                취소
              </button>
              <button
                onClick={confirmDeploy}
                disabled={preflightLoading || startingDeploy}
                className={`px-4 py-2 rounded text-white font-semibold ${
                  preflightLoading || startingDeploy ? "bg-blue-900 cursor-not-allowed" : "bg-blue-600 hover:bg-blue-500"
                }`}
              >
                {startingDeploy ? "배포 시작 중..." : "실제 배포"}
              </button>
            </div>
            </div>
          </div>
        </div>
      )}

      {confirmingRollback && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-[10000] p-4">
          <div className="bg-gray-900 border border-red-700 rounded-2xl w-full max-w-md p-6 relative">
            <button
              onClick={() => setConfirmingRollback(false)}
              className="absolute top-3 right-3 text-gray-400 hover:text-white"
              aria-label="close rollback modal"
              disabled={rollbacking}
            >
              ✕
            </button>
            <h3 className="text-2xl font-semibold text-red-300 mb-2">롤백 확인</h3>
            <p className="text-sm text-gray-300">
              현재 배포 상태를 이전 성공 버전으로 되돌립니다. 작업 중에는 dev 서버가 재시작될 수 있으며,
              변경 사항이 사라집니다. 계속 진행하시겠습니까?
            </p>
            <div className="mt-6 flex justify-end gap-3">
              <button
                onClick={() => setConfirmingRollback(false)}
                disabled={rollbacking}
                className="px-4 py-2 rounded border border-gray-600 text-gray-200 hover:bg-gray-800"
              >
                취소
              </button>
              <button
                onClick={confirmRollback}
                disabled={rollbacking}
                className={`px-4 py-2 rounded text-white font-semibold ${
                  rollbacking ? "bg-red-900 cursor-not-allowed" : "bg-red-600 hover:bg-red-500"
                }`}
              >
                {rollbacking ? "롤백 중..." : "롤백 실행"}
              </button>
            </div>
          </div>
        </div>
      )}
      </motion.div>
    </>
  );
}
