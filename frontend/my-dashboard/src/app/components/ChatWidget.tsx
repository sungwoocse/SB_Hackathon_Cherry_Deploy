"use client";
import Image from "next/image";
import { useEffect, useMemo, useRef, useState } from "react";
import { API_BASE_URL, JSON_HEADERS } from "@/lib/api";

interface ChatWidgetProps {
  onClose?: () => void;
  stages?: Array<[string, Record<string, unknown>]>;
  stageTimezone?: string;
  heroStatus?: string;
}

const STAGE_DISPLAY_SEQUENCE = [
  "running_clone",
  "running_build",
  "running_cutover",
  "running_observability",
  "running_post_checks",
  "completed",
  "failed",
] as const;
const STAGE_WINDOW_SIZE = 2;
const GAUGE_DURATION_MS = 60000; // 60초
const GAUGE_TICK_MS = 1000;

type StageName = (typeof STAGE_DISPLAY_SEQUENCE)[number] | string;

export default function ChatWidget({
  onClose,
  stages = [],
  stageTimezone = "Asia/Seoul",
  heroStatus = "pending",
}: ChatWidgetProps) {
  const POPUP_WIDTH_REM = 40; // 더 작은 폭으로 조정
  const POPUP_HEIGHT_REM = 22; // 높이도 약간 축소
  const IDEATION_WIDTH_REM = POPUP_WIDTH_REM; // 동일 폭으로 왼쪽 확장
  const PANEL_MIN_WIDTH_REM = 18;
  const PANEL_GAP_REM = 1; // gap-4 == 1rem
  const HEADER_HEIGHT_REM = 3; // 1.2x 높이 확보
  const [messages, setMessages] = useState<{ sender: "user" | "bot"; text: string }[]>([
    { sender: "bot", text: "안녕하세요! 무엇을 도와드릴까요?" },
  ]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const primaryEndRef = useRef<HTMLDivElement | null>(null);
  const [gaugeStartTimestamp, setGaugeStartTimestamp] = useState<number>(() => Date.now());
  const [gaugePercentRemaining, setGaugePercentRemaining] = useState<number>(100);
  const [gaugeActive, setGaugeActive] = useState<boolean>(false);
  const [lastStageUpdate, setLastStageUpdate] = useState<number | null>(null);
  const hasStageDataRef = useRef<boolean>(false);
  const responsivePanelWidth = (maxRem: number) =>
    `clamp(${PANEL_MIN_WIDTH_REM}rem, calc(50vw - ${PANEL_GAP_REM / 2}rem), ${maxRem}rem)`;
  const happyAudioRef = useRef<HTMLAudioElement | null>(null);
  const sadAudioRef = useRef<HTMLAudioElement | null>(null);
  const hasPlayedHappyRef = useRef<boolean>(false);
  const hasPlayedSadRef = useRef<boolean>(false);
  const orderedStages = useMemo(() => {
    const sequenceSet = new Set<string>(STAGE_DISPLAY_SEQUENCE);
    const stageMap = new Map<string, Record<string, unknown>>();
    stages.forEach(([name, details]) => {
      stageMap.set(name, details || {});
    });
    const ordered: Array<[StageName, Record<string, unknown>]> = [];
    STAGE_DISPLAY_SEQUENCE.forEach((stage) => {
      if (stageMap.has(stage)) {
        ordered.push([stage, stageMap.get(stage)!]);
      }
    });
    stages.forEach(([stage, details]) => {
      if (!sequenceSet.has(stage)) {
        ordered.push([stage as StageName, details || {}]);
      }
    });
    return ordered;
  }, [stages]);

  const formatStageLabel = (stage: StageName) => stage.replace(/_/g, " ");

  const resolveStageTimestamp = (details: Record<string, unknown>) => {
    const value = details?.["timestamp"];
    return typeof value === "string" ? value : null;
  };

  const formatStageTime = (value: unknown) => {
    if (typeof value !== "string" || !value) return null;
    try {
      const formatter = new Intl.DateTimeFormat("ko-KR", {
        timeZone: stageTimezone,
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      });
      return formatter.format(new Date(value));
    } catch {
      return null;
    }
  };
  const resolveStageStatus = (details: Record<string, unknown>) => {
    const status = details?.["status"];
    if (typeof status === "string" && status.trim()) return status;
    const completed = details?.["completed"];
    if (completed === true) return "completed";
    return "pending";
  };

  const resolveStageNote = (details: Record<string, unknown>) => {
    const note = details?.["message"] ?? details?.["note"] ?? details?.["summary"];
    return typeof note === "string" && note.trim().length ? note : null;
  };

  const resolveStageHasProgress = (details: Record<string, unknown>) => {
    if (resolveStageTimestamp(details)) return true;
    const status = resolveStageStatus(details);
    if (status && status !== "pending") return true;
    return Boolean(resolveStageNote(details));
  };

  const latestStageIndex = orderedStages.reduce((acc, entry, idx) => {
    if (resolveStageHasProgress(entry[1])) return idx;
    return acc;
  }, -1);
  const progressedCount = orderedStages.reduce((count, entry) => {
    return count + (resolveStageHasProgress(entry[1]) ? 1 : 0);
  }, 0);

  const computeWindowStart = () => {
    if (!orderedStages.length) return 0;
    const baseIndex = latestStageIndex >= 0 ? latestStageIndex : 0;
    const tentative = Math.floor(baseIndex / STAGE_WINDOW_SIZE) * STAGE_WINDOW_SIZE;
    const maxStart = Math.max(0, orderedStages.length - STAGE_WINDOW_SIZE);
    return Math.min(tentative, maxStart);
  };

  const stageWindowStart = computeWindowStart();
  const visibleStages = orderedStages.slice(stageWindowStart, stageWindowStart + STAGE_WINDOW_SIZE);

  const hasStageData = orderedStages.length > 0;
  const stageCompleted =
    orderedStages.length > 0 &&
    orderedStages.every(([stage, details]) => {
      const status = resolveStageStatus(details);
      return status === "completed" || status === "failed";
    });
  const heroCompleted = heroStatus === "completed" || heroStatus === "failed";
  const deploySucceeded = heroStatus === "completed";
  const deployFailed = heroStatus === "failed";

  useEffect(() => {
    console.log("[ChatWidget] heroStatus update:", heroStatus, {
      deploySucceeded,
      deployFailed,
    });
  }, [heroStatus, deploySucceeded, deployFailed]);

  useEffect(() => {
    if (!happyAudioRef.current) {
      happyAudioRef.current = new Audio("/audios/happy.mp3");
      happyAudioRef.current.preload = "auto";
      console.log("[ChatWidget] happy audio initialized");
    }
    if (!sadAudioRef.current) {
      sadAudioRef.current = new Audio("/audios/sad.mp3");
      sadAudioRef.current.preload = "auto";
      console.log("[ChatWidget] sad audio initialized");
    }
  }, []);

  useEffect(() => {
    if (!deploySucceeded) {
      hasPlayedHappyRef.current = false;
      return;
    }
    if (hasPlayedHappyRef.current) return;
    hasPlayedHappyRef.current = true;
    const audio = happyAudioRef.current;
    if (!audio) return;
    console.log("[ChatWidget] Playing happy audio due to deploy success");
    audio.currentTime = 0;
    audio.play().catch((err) => {
      console.warn("[ChatWidget] Happy audio playback blocked", err);
    });
  }, [deploySucceeded]);

  useEffect(() => {
    if (!deployFailed) {
      hasPlayedSadRef.current = false;
      return;
    }
    if (hasPlayedSadRef.current) return;
    hasPlayedSadRef.current = true;
    const audio = sadAudioRef.current;
    if (!audio) return;
    console.log("[ChatWidget] Playing sad audio due to deploy failure");
    audio.currentTime = 0;
    audio.play().catch((err) => {
      console.warn("[ChatWidget] Sad audio playback blocked", err);
    });
  }, [deployFailed]);

  useEffect(() => {
    if (hasStageData) {
      setLastStageUpdate(Date.now());
    }
  }, [hasStageData, stages]);

  useEffect(() => {
    if (stageCompleted || heroCompleted) {
      hasStageDataRef.current = false;
      setGaugeActive(false);
      setGaugePercentRemaining(0);
      return;
    }
    if (!hasStageData) {
      hasStageDataRef.current = false;
      setGaugeActive(false);
      setGaugePercentRemaining(100);
      return;
    }
    if (!hasStageDataRef.current) {
      hasStageDataRef.current = true;
      setGaugeActive(true);
      setGaugeStartTimestamp(Date.now());
      setGaugePercentRemaining(100);
    }
  }, [hasStageData, stageCompleted, heroCompleted]);

  useEffect(() => {
    if (!gaugeActive) return;
    const interval = setInterval(() => {
      const now = Date.now();
      const elapsed = now - gaugeStartTimestamp;
      const ratio = Math.min(1, elapsed / GAUGE_DURATION_MS);
      setGaugePercentRemaining(Math.max(0, 100 - ratio * 100));

      if (lastStageUpdate && now - lastStageUpdate > GAUGE_DURATION_MS) {
        setGaugeActive(false);
        setGaugePercentRemaining(0);
      }
    }, GAUGE_TICK_MS);
    return () => clearInterval(interval);
  }, [gaugeActive, gaugeStartTimestamp, lastStageUpdate]);

  const stageTimezoneLabel = stageTimezone === "Asia/Seoul" ? "KST" : stageTimezone;

  // ✅ 새 메시지마다 하단으로 스크롤
  useEffect(() => {
    primaryEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async () => {
    const text = input.trim();
    if (!text || sending) return;

    // 사용자 메시지
    setMessages((prev) => [...prev, { sender: "user", text }]);
    setInput("");
    setSending(true);

    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/chat`, {
        method: "POST",
        headers: JSON_HEADERS,
        body: JSON.stringify({ message: text }),
      });
      if (!res.ok) {
        throw new Error("불러오기 실패");
      }
      const data = await res.json();
      const reply = data.reply || "응답이 비어있어요.";

      let i = 0;
      const botMsg = { sender: "bot" as const, text: "" };
      setMessages((prev) => [...prev, botMsg]);
      const interval = setInterval(() => {
        if (i < reply.length) {
          botMsg.text += reply[i];
          setMessages((prev) => [...prev.slice(0, -1), { ...botMsg }]);
          i++;
        } else {
          clearInterval(interval);
        }
      }, 25);
    } catch (err) {
      console.error(err);
      setMessages((prev) => [
        ...prev,
        { sender: "bot", text: "⚠️ 서버 연결에 실패했습니다." },
      ]);
    } finally {
      setSending(false);
    }
  };

  const handleClose = () => {
    onClose?.();
  };

  const ideationPanelStyle = {
    width: responsivePanelWidth(IDEATION_WIDTH_REM),
    height: `${POPUP_HEIGHT_REM}rem`,
  };
  const chatbotPanelStyle = {
    width: responsivePanelWidth(POPUP_WIDTH_REM),
    height: `${POPUP_HEIGHT_REM}rem`,
  };

  return (
    <>
      {/* ✅ 우측 하단 챗봇 팝업 + 좌측 아이디에이션 확장 */}
      <div className="fixed bottom-6 left-4 right-4 z-[9999] pointer-events-auto select-none flex justify-end gap-4 overflow-x-auto">
        {/* Ideation side panel */}
        <div
          className="rounded-xl shadow-2xl border border-[#2c3d55] overflow-hidden animate-fade-in origin-bottom-right flex flex-col bg-[#0f1826]"
          style={ideationPanelStyle}
        >
          <div className="relative bg-[#17243a] border-b border-[#2c3d55] p-5 overflow-hidden flex flex-col justify-end min-h-[13rem]">
            <div className="absolute top-8 left-1/2 translate-x-8 -translate-y-1/2 w-1/4 min-w-[140px] max-w-[220px]">
              <div className="bg-[#0d1423]/80 border border-[#24334d] rounded-xl px-4 py-2 shadow-lg">
                <div className="h-1.5 bg-[#0b1120] rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-blue-400 via-blue-500 to-blue-300 transition-all"
                    style={{ width: `${gaugePercentRemaining}%` }}
                  />
                </div>
              </div>
            </div>
            <div
              className={`absolute top-4 right-4 flex items-center gap-2 transition-opacity duration-500 ${
                deploySucceeded ? "opacity-0" : "opacity-100"
              }`}
            >
              <span className="text-xs uppercase tracking-[0.2em] text-red-200">error</span>
              <Image
                src="/images/bad.png"
                alt="Cherry assistant warning"
                width={160}
                height={160}
                className="select-none pointer-events-none"
                priority={false}
                unoptimized
              />
            </div>
            <div
              className={`absolute bottom-4 left-4 flex items-center gap-2 transition-opacity duration-500 ${
                deployFailed ? "opacity-0" : "opacity-100"
              }`}
            >
              <Image
                src="/images/good.png"
                alt="Cherry assistant success"
                width={140}
                height={140}
                className="select-none pointer-events-none"
                priority={false}
                unoptimized
              />
              <span className="text-xs uppercase tracking-[0.2em] text-emerald-200">cherry</span>
            </div>
            <div className="relative z-10 pr-28" />
          </div>
          <div className="flex-1 bg-[#101a2b] text-white p-4 overflow-y-auto">
            <div className="flex items-center justify-between">
              <p className="text-xs uppercase tracking-[0.2em] text-gray-400">📡 Live Stages</p>
              <p className="text-[10px] text-gray-500">Timezone: {stageTimezoneLabel}</p>
            </div>
            {visibleStages.length ? (
              <ol className="mt-3 space-y-2 text-[12px] leading-tight">
                {visibleStages.map(([stageName, details], idx) => {
                  const timestamp = formatStageTime(resolveStageTimestamp(details));
                  const status = resolveStageStatus(details);
                  const note = resolveStageNote(details);
                  const isCompleted = status === "completed";
                  const isActive = !isCompleted && Boolean(timestamp);
                  const globalIndex = stageWindowStart + idx;
                  return (
                    <li
                      key={`stage-${stageName}`}
                      className="flex items-start gap-2 rounded-lg border border-[#1c2940] bg-[#0c1524]/60 p-2"
                    >
                      <div
                        className={`mt-0.5 flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-semibold ${
                          isCompleted
                            ? "bg-green-500/20 text-green-200"
                            : isActive
                            ? "bg-blue-500/20 text-blue-200"
                            : "bg-gray-600/30 text-gray-400"
                        }`}
                      >
                        {globalIndex + 1}
                      </div>
                      <div className="flex-1 space-y-0.5">
                        <div className="flex items-center justify-between gap-3">
                          <div>
                            <p className="text-[12px] font-semibold capitalize text-blue-50">
                              {formatStageLabel(stageName)}
                            </p>
                            <p className="text-[10px] uppercase tracking-wide text-gray-500">{status}</p>
                          </div>
                          {timestamp ? (
                            <p className="text-[10px] text-blue-200">{timestamp}</p>
                          ) : (
                            <p className="text-[10px] text-gray-500">대기 중</p>
                          )}
                        </div>
                        {note && <p className="text-[10px] text-gray-300 leading-tight">{note}</p>}
                      </div>
                    </li>
                  );
                })}
              </ol>
            ) : (
              <p className="mt-6 text-sm text-gray-400">Stage 데이터가 없습니다.</p>
            )}
          </div>
        </div>

        {/* 기존 챗봇 영역 */}
        <div
          className="rounded-xl shadow-2xl border border-[#2c3d55] overflow-hidden animate-fade-in origin-bottom-right flex flex-col"
          style={chatbotPanelStyle}
        >
          {/* Header */}
          <div
            className="flex items-center justify-between px-4 bg-[#223145] text-blue-200 border-b border-[#2c3d55]"
            style={{ height: `${HEADER_HEIGHT_REM}rem` }}
          >
            <div className="font-semibold flex items-center gap-2">
              <span className="text-lg">🤖</span>
              <span>Chatbot</span>
            </div>
            <button
              onClick={handleClose}
              className="text-gray-300 hover:text-white transition"
              aria-label="닫기"
            >
              ✕
            </button>
          </div>
          {/* Body */}
          <div className="flex-1 bg-[#1e2a3a] text-white p-3 overflow-y-auto space-y-2">
            {messages.map((m, i) => (
              <div
                key={i}
                className={`flex ${m.sender === "user" ? "justify-end" : "justify-start"} w-full`}
              >
                <div
                  className={`px-3 py-2 text-sm rounded-2xl leading-5 shadow-sm break-words 
          ${m.sender === "user" ? "bg-[#2563eb] text-white" : "bg-[#2b3b52] text-gray-200"}
        `}
                  style={{
                    width: "fit-content",
                    maxWidth: "75%",
                    wordBreak: "break-word",
                  }}
                >
                  {m.text}
                </div>
              </div>
            ))}
            <div ref={primaryEndRef} />
          </div>

          {/* Input */}
          <div className="bg-[#1b2736] border-t border-[#2c3d55] p-3 flex items-center gap-2">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSend()}
              placeholder="메시지를 입력하세요..."
              className="flex-1 bg-[#111a26] text-sm text-gray-100 px-3 py-2 rounded-md outline-none ring-0 focus:ring-1 focus:ring-blue-400 placeholder:text-gray-400"
            />
            <button
              onClick={handleSend}
              disabled={sending}
              className={`px-3 py-2 text-sm rounded-md text-white transition shadow ${
                sending ? "bg-blue-900 cursor-not-allowed" : "bg-blue-600 hover:bg-blue-700"
              }`}
            >
              {sending ? "전송 중..." : "전송"}
            </button>
          </div>
        </div>
      </div>

      {/* fade-in 애니메이션 */}
      <style jsx>{`
        @keyframes fade-in {
          from {
            opacity: 0;
            transform: translateY(8px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
        .animate-fade-in {
          animation: fade-in 0.25s ease-out;
        }
      `}</style>
    </>
  );
}
