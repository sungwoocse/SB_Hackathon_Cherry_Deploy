import React from "react";
import ReactDOM from "react-dom/client";
import ChatWidget from "./components/ChatWidget.jsx";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    {/* 메인 페이지 콘텐츠가 따로 있다면 그대로 두고, 챗봇은 항상 화면 오른쪽 아래에 뜹니다. */}
    <ChatWidget />
  </React.StrictMode>
);
