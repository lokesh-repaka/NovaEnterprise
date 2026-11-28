import type { Metadata } from "next";
import "./globals.css";
import { Sidebar } from "@/components/navigation/Sidebar";
import { Header } from "@/components/navigation/Header";

export const metadata: Metadata = {
  title: "NovaEnterprise — Intelligence & Decision Console",
  description:
    "Enterprise Knowledge & Decision Intelligence Platform combining Vector RAG, Graph RAG, SQL, and LangGraph multi-agent workflows.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-[#0b0f19] text-gray-100 antialiased flex flex-row overflow-hidden">
        {/* Persistent Collapsible Sidebar */}
        <Sidebar />

        {/* Content Viewport */}
        <div className="flex-1 flex flex-col min-w-0 h-screen overflow-hidden">
          <Header />
          <main className="flex-1 overflow-y-auto p-6 bg-[#0b0f19]">
            <div className="max-w-7xl mx-auto">{children}</div>
          </main>
        </div>
      </body>
    </html>
  );
}
