"use client";
import { useState } from "react";
import ChatApp from "../src/app/components/ChatApp";

/**
 * Legacy floating chat launcher preserved for future reference.
 */
export default function LegacyChatPopup() {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        style={{
          position: "fixed",
          bottom: 20,
          right: 20,
          width: 56,
          height: 56,
          borderRadius: "50%",
          background: "var(--blue)",
          color: "white",
          border: "none",
          cursor: "pointer",
          fontSize: 22,
          boxShadow: "0 10px 24px rgba(0,0,0,.35)",
          zIndex: 9999,
        }}
        title="챗봇 열기 (Legacy)"
      >
        💬
      </button>
      {open && (
        <div
          style={{
            position: "fixed",
            bottom: 88,
            right: 20,
            width: 320,
            height: 440,
            background: "var(--panel)",
            border: `1px solid var(--border)`,
            borderRadius: 12,
            boxShadow: "0 12px 32px rgba(0,0,0,.5)",
            zIndex: 10000,
            display: "flex",
            flexDirection: "column",
            overflow: "hidden",
            animation: "fadeIn .18s ease-out",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "10px 12px",
              background: "var(--panel-2)",
              borderBottom: `1px solid var(--border)`,
              fontWeight: 600,
              fontSize: 14,
            }}
          >
            일단만들어 챗봇
            <button
              onClick={() => setOpen(false)}
              aria-label="닫기"
              style={{
                background: "transparent",
                border: "none",
                color: "var(--text)",
                fontSize: 18,
                cursor: "pointer",
              }}
            >
              ×
            </button>
          </div>
          <div style={{ flex: 1, overflow: "hidden" }}>
            <ChatApp />
          </div>
        </div>
      )}
    </>
  );
}
