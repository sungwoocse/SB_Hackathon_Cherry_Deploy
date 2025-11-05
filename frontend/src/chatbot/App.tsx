"use client";
import { useState, useEffect, useRef } from "react";
import "./chatbot.css";

export default function App() {
  const [messages, setMessages] = useState(() => {
    const stored = localStorage.getItem("chat_history");
    return stored ? JSON.parse(stored) : [];
  });
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const sendMessage = async () => {
    if (!input.trim()) return;

    const userMessage = { sender: "user", text: input };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsTyping(true);

    try {
      const res = await fetch("http://localhost:3001/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: userMessage.text }),
      });

      const data = await res.json();
      setMessages((prev) => [...prev, { sender: "bot", text: data.reply }]);
    } catch {
      setMessages((prev) => [...prev, { sender: "bot", text: "⚠ 서버 연결 실패" }]);
    } finally {
      setIsTyping(false);
    }
  };

  useEffect(() => {
    localStorage.setItem("chat_history", JSON.stringify(messages));
  }, [messages]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  return (
    <div className="chatbot-container">
      <div ref={scrollRef} className="chatbot-messages">
        {messages.map((m, i) => (
          <div key={i} className={`bubble ${m.sender}`}>{m.text}</div>
        ))}
        {isTyping && <p className="typing">입력 중...</p>}
      </div>

      <div className="chatbot-input">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && sendMessage()}
          placeholder="메시지를 입력하세요…"
        />
        <button onClick={sendMessage}>전송</button>
      </div>
    </div>
  );
}
