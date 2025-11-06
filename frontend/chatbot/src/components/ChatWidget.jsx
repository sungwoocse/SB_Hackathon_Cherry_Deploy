import { useState } from "react";
import App from "../App";

/**
 * 오른쪽 아래 플로팅 버튼 → 팝업 형태로 챗봇을 띄웁니다.
 * 모달은 ChatWidget에서 관리하며 전체 화면 기준으로 표시됩니다.
 */
export default function ChatWidget() {
  const [open, setOpen] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [modalText, setModalText] = useState("");

  // App.jsx로부터 모달 표시 요청 받기
  const handleShowModal = (text) => {
    setModalText(text);
    setShowModal(true);
  };

  return (
    <>
      {/* 💬 플로팅 버튼 */}
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
        title="챗봇 열기"
      >
        💬
      </button>

      {/* 📦 팝업 */}
      {open && (
        <div
          style={{
            position: "fixed",
            bottom: 88, // 버튼 위
            right: 20,
            width: 320, // 요청하신 작은 크기
            height: 630,
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

          {/* 본문 (App.jsx 호출) */}
          <div style={{ flex: 1, overflow: "hidden" }}>
            <App onShowModal={handleShowModal} />
          </div>
        </div>
      )}

      {/* ✅ 모달 (ChatWidget에서 렌더링) */}
      {showModal && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: "rgba(0,0,0,0.55)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 20000,
          }}
          onClick={() => setShowModal(false)} // 배경 클릭 시 닫기
        >
          <div
            style={{
              background: "var(--panel-2)",
              color: "var(--text)",
              padding: "24px 28px",
              borderRadius: 12,
              maxWidth: "90%",
              maxHeight: "80%",
              overflowY: "auto",
              whiteSpace: "pre-wrap",
              boxShadow: "0 0 20px rgba(0,0,0,0.5)",
            }}
            onClick={(e) => e.stopPropagation()} // 내부 클릭 시 닫히지 않음
          >
            {modalText}
          </div>
        </div>
      )}
    </>
  );
}
