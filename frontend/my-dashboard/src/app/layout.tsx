import "./globals.css";
import Sidebar from "./components/Sidebar";
import Header from "./components/Header";
import Character from "./components/Character"; //

export const metadata = {
  title: "DevOps Dashboard",
  description: "Frontend for DevOps system",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ko">
      <body className="flex h-screen overflow-hidden bg-gray-900 text-white">
        {/* Sidebar */}
        <Sidebar />

        {/* Main Content Area */}
        <div className="flex flex-col flex-1 overflow-y-auto">
          <Header />
          <main className="flex-1 p-6">{children}</main>
          <Character />
        </div>
      </body>
    </html>
  );
}
