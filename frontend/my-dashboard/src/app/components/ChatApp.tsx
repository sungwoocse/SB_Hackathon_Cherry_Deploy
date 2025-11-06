"use client";
import { useState, useEffect, useRef } from "react";
import "./ChatStyles.css";

interface Message {
  sender: "user" | "bot";
  text: string;
}

export default function ChatApp() {
  const [messages, setMessages] = useState<Message[]>(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem("chatMessages");
      return saved ? JSON.parse(saved) : [];
    }
    return [];
  });
  const [input, setInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    localStorage.setItem("chatMessages", JSON.stringify(messages));
  }, [messages]);

  const sendMessage = async () => {
    if (!input.trim()) return;
    const userMsg = { sender: "user" as const, text: input };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: input }),
      });
      const data = await res.json();

      let i = 0;
      const botMsg = { sender: "bot" as const, text: "" };
      const text = data.reply || "응답을 가져올 수 없어요 😢";

      const interval = setInterval(() => {
        if (i < text.length) {
          botMsg.text += text[i];
          setMessages((prev) => [
            ...prev.slice(0, -1),
            { ...botMsg },
          ]);
          i++;
        } else {
          clearInterval(interval);
        }
      }, 30);
      setMessages((prev) => [...prev, botMsg]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { sender: "bot", text: "⚠️ 서버 응답 실패" },
      ]);
    }
  };

  return (
    <div className="chatbot-container">
      <div className="chatbot-header">Cherry Assistant 🍒</div>
      <div className="chatbot-messages">
        {messages.map((msg, idx) => (
          <div
            key={idx}
            className={`p-2 rounded-lg max-w-[80%] ${
              msg.sender === "user"
                ? "self-end bg-blue-600 text-white"
                : "self-start bg-gray-700 text-gray-100"
            }`}
          >
            {msg.text}
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>
      <div className="chatbot-input">
        <input
          type="text"
          placeholder="메시지를 입력하세요..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && sendMessage()}
        />
        <button onClick={sendMessage}>전송</button>
      </div>
    </div>
  );
}
