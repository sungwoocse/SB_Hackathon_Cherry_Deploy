import ChatWidget from "../src/components/ChatWidget";

export default function RootLayout({ children }) {
  return (
    <html lang="ko">
      <body>
        {children}
        <ChatWidget /> {/* ✅ 오른쪽 아래 항상 표시 */}
      </body>
    </html>
  );
}
