import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "DevOps Deployment Dashboard",
  description: "Green/Blue Deployment Monitor",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ko">
      <body className="bg-gray-900 text-gray-100 min-h-screen">
        {children}
      </body>
    </html>
  );
}
