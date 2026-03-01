import type { ReactNode } from "react";
import Link from "next/link";

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ko">
      <body style={{ fontFamily: "sans-serif", margin: 0, padding: "2rem", background: "#f3f4f6" }}>
        <nav style={{ maxWidth: 1100, margin: "0 auto 1rem", display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
          <Link href="/">대시보드</Link>
          <Link href="/templates">템플릿 레지스트리</Link>
          <Link href="/runs/search">실행 검색</Link>
          <Link href="/templates/compare">버전 비교</Link>
        </nav>
        {children}
      </body>
    </html>
  );
}
