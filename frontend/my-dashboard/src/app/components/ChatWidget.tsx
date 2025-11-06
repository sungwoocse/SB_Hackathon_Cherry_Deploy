"use client";
import { useEffect, useRef, useState } from "react";
import Character from "./Character";

export default function ChatWidget() {
  const [status, setStatus] = useState<"idle" | "talking" | "success" | "failed">("idle");
  const [messages, setMessages] = useState<{ sender: "user" | "bot"; text: string }[]>([
    { sender: "bot", text: "안녕하세요! 무엇을 도와드릴까요?" },
  ]);
  const [input, setInput] = useState("");
  const [open, setOpen] = useState(true); // 팝업 토글
  const endRef = useRef<HTMLDivElement | null>(null);

  // ✅ 새 메시지마다 하단으로 스크롤
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, open]);

  const handleSend = () => {
    const text = input.trim();
    if (!text) return;

    // 사용자 메시지
    setMessages((prev) => [...prev, { sender: "user", text }]);
    setInput("");
    setStatus("talking");

    // 데모 응답 (Gemini 연동 전 임시)
    setTimeout(() => {
      setMessages((prev) => [
        ...prev,
        { sender: "bot", text: "Gemini 연결 준비 완료 상태입니다." },
      ]);
      setStatus("success");
      setTimeout(() => setStatus("idle"), 1200);
    }, 900);
  };

  return (
    <>
      {/* ✅ 캐릭터 (왼쪽 하단 고정, 상태 유지) */}
      <Character status={status} />

      {/* ✅ 우측 하단 챗봇 팝업 (디자인 복원) */}
      <div className="fixed bottom-6 right-6 z-[9999] pointer-events-auto select-none">
        {open ? (
          <div className="w-80 h-100 rounded-xl shadow-2xl border border-[#2c3d55] overflow-hidden animate-fade-in">
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-2 bg-[#223145] text-blue-200 border-b border-[#2c3d55]">
              <div className="font-semibold flex items-center gap-2">
                <span className="text-lg">🤖</span>
                <span>Chatbot</span>
              </div>
              <button
                onClick={() => setOpen(false)}
                className="text-gray-300 hover:text-white transition"
                aria-label="닫기"
              >
                ✕
              </button>
            </div>
{/* Body */}
<div className="h-[calc(24rem-2.5rem-3.25rem)] bg-[#1e2a3a] text-white p-3 overflow-y-auto space-y-2">
  {messages.map((m, i) => (
    <div
      key={i}
      className={`flex ${m.sender === "user" ? "justify-end" : "justify-start"} w-full`}
    >
      <div
        className={`px-3 py-2 text-sm rounded-2xl leading-5 shadow-sm break-words 
          ${m.sender === "user"
            ? "bg-[#2563eb] text-white"
            : "bg-[#2b3b52] text-gray-200"}
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
  <div ref={endRef} />
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
                className="px-3 py-2 text-sm rounded-md bg-blue-600 hover:bg-blue-700 text-white transition shadow"
              >
                전송
              </button>
            </div>
          </div>
        ) : (
          // 토글 버튼 (닫힌 상태)
          <button
            onClick={() => setOpen(true)}
            className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-full shadow-lg transition"
          >
            💬 Chat
          </button>
        )}
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
