// frontend/my-dashboard/app/layout.tsx
export const metadata = {
  title: "DevOps Deploy Dashboard",
  description: "Green/Blue Deployment Monitor",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body
        style={{
          margin: 0,
          fontFamily: "system-ui, sans-serif",
          backgroundColor: "#0d1117",
          color: "white",
        }}
      >
        {children}
      </body>
    </html>
  );
}
