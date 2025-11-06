import { useEffect, useRef, useState } from "react";

export default function App({ onShowModal }) {
  const [messages, setMessages] = useState(() => {
    try {
      const stored = localStorage.getItem("chat_history");
      return stored ? JSON.parse(stored) : [];
    } catch {
      return [];
    }
  });
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const listRef = useRef(null);

  useEffect(() => {
    listRef.current?.scrollTo({
      top: listRef.current.scrollHeight,
      behavior: "smooth",
    });
    try {
      localStorage.setItem("chat_history", JSON.stringify(messages));
    } catch {}
  }, [messages]);

  const sendMessage = async () => {
    const text = input.trim();
    if (!text) return;

    const userMsg = { sender: "user", text };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setIsTyping(true);

    try {
      const res = await fetch("https://delight.13-125-116-92.nip.io/api/v1/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text }),
      });
      const data = await res.json();
      const full = String(data?.reply ?? "");

      setMessages((prev) => [...prev, { sender: "bot", text: "" }]);
      for (let i = 0; i < full.length; i++) {
        const slice = full.slice(0, i + 1);
        setMessages((prev) => {
          const copy = prev.slice();
          copy[copy.length - 1] = { sender: "bot", text: slice };
          return copy;
        });
        await new Promise((r) => setTimeout(r, 12));
      }
    } catch (e) {
      setMessages((prev) => [
        ...prev,
        { sender: "bot", text: "⚠ 서버 연결에 실패했습니다." },
      ]);
    } finally {
      setIsTyping(false);
    }
  };

  return (
    <div
      style={{
        height: "100%",
        display: "flex",
        flexDirection: "column",
        background: "var(--panel)",
        color: "var(--text)",
      }}
    >
      {/* 메시지 리스트 */}
      <div
        ref={listRef}
        className="scroll"
        style={{
          flex: 1,
          overflowY: "auto",
          padding: 12,
          gap: 8,
          display: "flex",
          flexDirection: "column",
        }}
      >
        {messages.map((m, idx) => (
          <div
            key={idx}
            style={{
              display: "flex",
              justifyContent: m.sender === "user" ? "flex-end" : "flex-start",
              animation: "fadeIn .18s ease-out",
            }}
          >
            <div
              style={{
                maxWidth: "78%",
                padding: "8px 12px",
                borderRadius: 12,
                background:
                  m.sender === "user" ? "var(--blue)" : "var(--panel-2)",
                color: m.sender === "user" ? "#fff" : "var(--text)",
                boxShadow: "0 2px 8px rgba(0,0,0,.25)",
                whiteSpace: "pre-wrap",
                wordBreak: "break-word",
                fontSize: 13.5,
                lineHeight: 1.35,
                cursor: m.sender === "bot" ? "pointer" : "default",
              }}
              onClick={() => {
                if (m.sender === "bot" && m.text.length > 80) {
                  onShowModal?.(m.text); // ✅ 부모(ChatWidget)에게 표시 요청
                }
              }}
            >
              {m.text}
            </div>
          </div>
        ))}

        {isTyping && (
          <div
            style={{ color: "var(--muted)", fontStyle: "italic", fontSize: 12 }}
          >
            입력 중…
          </div>
        )}
      </div>

      {/* 입력창 */}
      <div
        style={{
          display: "flex",
          gap: 8,
          borderTop: `1px solid var(--border)`,
          padding: 10,
          background: "rgba(17,24,39,0.8)",
          backdropFilter: "blur(4px)",
        }}
      >
        <input
          placeholder="메시지를 입력하세요…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") sendMessage();
          }}
          style={{
            flex: 1,
            padding: "10px 12px",
            background: "var(--panel-2)",
            color: "var(--text)",
            border: `1px solid var(--border)`,
            borderRadius: 8,
            outline: "none",
          }}
        />
        <button
          onClick={sendMessage}
          style={{
            padding: "10px 14px",
            background: "var(--blue)",
            color: "#fff",
            border: "none",
            borderRadius: 8,
            cursor: "pointer",
          }}
        >
          전송
        </button>
      </div>
    </div>
  );
}
