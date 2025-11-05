"use client";
import { useState } from "react";
import App from "../chatbot/App";

export default function ChatWidget() {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="fixed bottom-6 right-6 w-14 h-14 rounded-full bg-blue-600 hover:bg-blue-700 shadow-lg text-2xl text-white flex justify-center items-center z-[9999]"
      >
        💬
      </button>

      {open && (
        <div className="fixed bottom-24 right-6 w-80 h-[500px] bg-gray-900 border border-gray-700 text-white rounded-xl shadow-xl flex flex-col overflow-hidden z-[10000]">
          <div className="flex justify-between items-center px-4 py-2 bg-blue-600 text-sm font-semibold">
            일단만들어 챗봇
            <button onClick={() => setOpen(false)}>×</button>
          </div>

          <App />
        </div>
      )}
    </>
  );
}
