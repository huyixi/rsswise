import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "RSSWise",
  description: "AI RSS Reader"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>
        <header className="border-b bg-white">
          <nav className="mx-auto flex max-w-5xl gap-4 px-4 py-3">
            <Link href="/articles" className="font-semibold">
              RSSWise
            </Link>
            <Link href="/articles">文章</Link>
            <Link href="/feeds">Feed</Link>
          </nav>
        </header>
        <main className="mx-auto max-w-5xl px-4 py-6">{children}</main>
      </body>
    </html>
  );
}
