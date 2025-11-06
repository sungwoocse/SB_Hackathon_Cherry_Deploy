"use client";
import React, { useState, useRef, useEffect } from "react";

export default function ChatWidget() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([
    { sender: "bot", text: "안녕하세요! 무엇을 도와드릴까요?" },
  ]);
  const [input, setInput] = useState("");
  const chatEndRef = useRef<HTMLDivElement | null>(null); // ✅ 타입 지정으로 scrollIntoView 빨간줄 제거

  // 메시지 변경 시 스크롤 하단 이동
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // 메시지 전송
  const sendMessage = () => {
    if (!input.trim()) return;

    const newMessage = { sender: "user", text: input.trim() };
    setMessages((prev) => [...prev, newMessage]);
    setInput("");

    setTimeout(() => {
      setMessages((prev) => [
        ...prev,
        { sender: "bot", text: "좋은 질문이에요! 잠시만요... 🤖" },
      ]);
    }, 500);
  };

  // Enter 키로 전송
  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") sendMessage();
  };

  return (
    <>
      {/* 💬 Floating Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="fixed bottom-6 right-6 w-14 h-14 rounded-full bg-blue-500 text-white text-3xl shadow-lg hover:bg-blue-600 transition-all duration-300 flex items-center justify-center z-50"
      >
        💬
      </button>

      {/* 💬 Chat Window */}
      {isOpen && (
        <div className="fixed bottom-24 right-6 w-80 bg-[#1e293b] text-white rounded-xl shadow-2xl border border-gray-700 overflow-hidden z-40 animate-fade-in">
          {/* Header */}
          <div className="flex items-center justify-between p-4 bg-[#0f172a] border-b border-gray-700">
            <h3 className="text-lg font-semibold text-blue-400">🤖 Chatbot</h3>
            <button
              onClick={() => setIsOpen(false)}
              className="text-gray-400 hover:text-gray-200"
            >
              ✕
            </button>
          </div>

          {/* Messages */}
          <div className="p-4 h-64 overflow-y-auto text-sm leading-relaxed space-y-3">
            {messages.map((msg, idx) => (
              <div
                key={idx}
                className={`flex ${
                  msg.sender === "user" ? "justify-end" : "justify-start"
                }`}
              >
                <div
                  className={`px-3 py-2 rounded-lg max-w-[75%] ${
                    msg.sender === "user"
                      ? "bg-blue-500 text-white"
                      : "bg-gray-700 text-gray-200"
                  }`}
                >
                  {msg.text}
                </div>
              </div>
            ))}
            <div ref={chatEndRef} />
          </div>

          {/* Input */}
          <div className="p-3 border-t border-gray-700 flex">
            <input
              type="text"
              value={input}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                setInput(e.target.value)
              } // ✅ e 타입 명시로 빨간줄 제거
              onKeyDown={handleKeyDown}
              placeholder="메시지를 입력하세요..."
              className="flex-1 p-2 rounded-md bg-gray-800 text-gray-200 text-sm focus:outline-none"
            />
            <button
              onClick={sendMessage}
              className="ml-2 px-4 bg-blue-500 hover:bg-blue-600 text-white rounded-md text-sm"
            >
              전송
            </button>
          </div>
        </div>
      )}
    </>
  );
}
