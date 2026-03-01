import type { ReactNode } from "react";
import Link from "next/link";
import { Space_Grotesk } from "next/font/google";

const spaceGrotesk = Space_Grotesk({
  subsets: ["latin"],
  weight: ["400", "500", "700"],
});

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ko">
      <body
        className={spaceGrotesk.className}
        style={{
          margin: 0,
          minHeight: "100vh",
          padding: "1.5rem",
          background:
            "radial-gradient(circle at 0% 0%, #fde68a 0, rgba(253,230,138,0) 30%), radial-gradient(circle at 100% 10%, #99f6e4 0, rgba(153,246,228,0) 25%), linear-gradient(180deg, #f8fafc 0%, #eef2ff 100%)",
          color: "#0f172a",
        }}
      >
        <nav
          style={{
            maxWidth: 1200,
            margin: "0 auto 1rem",
            display: "flex",
            gap: "0.5rem",
            flexWrap: "wrap",
            background: "rgba(255,255,255,0.72)",
            border: "1px solid rgba(15,23,42,0.08)",
            boxShadow: "0 10px 30px rgba(15,23,42,0.08)",
            backdropFilter: "blur(8px)",
            borderRadius: 16,
            padding: "0.5rem",
          }}
        >
          <Link href="/" style={{ padding: "0.45rem 0.75rem", borderRadius: 10, textDecoration: "none", color: "#0f172a" }}>
            대시보드
          </Link>
          <Link
            href="/projects/overview"
            style={{ padding: "0.45rem 0.75rem", borderRadius: 10, textDecoration: "none", color: "#0f172a" }}
          >
            프로젝트 보드
          </Link>
          <Link
            href="/templates"
            style={{ padding: "0.45rem 0.75rem", borderRadius: 10, textDecoration: "none", color: "#0f172a" }}
          >
            템플릿 레지스트리
          </Link>
          <Link
            href="/runs/search"
            style={{ padding: "0.45rem 0.75rem", borderRadius: 10, textDecoration: "none", color: "#0f172a" }}
          >
            실행 검색
          </Link>
          <Link
            href="/templates/compare"
            style={{ padding: "0.45rem 0.75rem", borderRadius: 10, textDecoration: "none", color: "#0f172a" }}
          >
            버전 비교
          </Link>
          <Link
            href="/schedules"
            style={{ padding: "0.45rem 0.75rem", borderRadius: 10, textDecoration: "none", color: "#0f172a" }}
          >
            스케줄
          </Link>
          <Link
            href="/policies"
            style={{ padding: "0.45rem 0.75rem", borderRadius: 10, textDecoration: "none", color: "#0f172a" }}
          >
            정책
          </Link>
          <Link
            href="/agents"
            style={{ padding: "0.45rem 0.75rem", borderRadius: 10, textDecoration: "none", color: "#0f172a" }}
          >
            에이전트
          </Link>
        </nav>
        {children}
      </body>
    </html>
  );
}
