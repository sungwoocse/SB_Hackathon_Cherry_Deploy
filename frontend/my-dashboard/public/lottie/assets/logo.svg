import { useState } from "react";
import App from "../App";

/**
 * 오른쪽 아래 플로팅 버튼 → 팝업 형태로 챗봇을 띄웁니다.
 * 다른 레이아웃의 영향을 받지 않도록 fixed 포지션만 사용합니다.
 */
export default function ChatWidget() {
  const [open, setOpen] = useState(false);

  return (
    <>
      {/* 플로팅 버튼 */}
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
          zIndex: 9999
        }}
        title="챗봇 열기"
      >
        💬
      </button>

      {/* 팝업 */}
      {open && (
        <div
          style={{
            position: "fixed",
            bottom: 88,      // 버튼 위로 살짝
            right: 20,
            width: 320,      // 요청하신 '작은' 사이즈
            height: 440,
            background: "var(--panel)",
            border: `1px solid var(--border)`,
            borderRadius: 12,
            boxShadow: "0 12px 32px rgba(0,0,0,.5)",
            zIndex: 10000,
            display: "flex",
            flexDirection: "column",
            overflow: "hidden",
            animation: "fadeIn .18s ease-out"
          }}
        >
          {/* 헤더 */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "10px 12px",
              background: "var(--panel-2)",
              borderBottom: `1px solid var(--border)`,
              fontWeight: 600,
              fontSize: 14
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
                cursor: "pointer"
              }}
            >
              ×
            </button>
          </div>

          {/* 본문 (채팅 앱) */}
          <div style={{ flex: 1, overflow: "hidden" }}>
            <App />
          </div>
        </div>
      )}
    </>
  );
}
