import React from "react";
import Link from "next/link";
import { Search, Sparkles, HelpCircle } from "lucide-react";

export default function SearchPage() {
  return (
    <div className="space-y-6">
      <div className="flex flex-col space-y-1.5">
        <h2 className="text-2xl font-bold text-white tracking-tight">
          Research Intelligence Interface
        </h2>
        <p className="text-xs text-gray-400">
          Enter a high-level enterprise inquiry. The LangGraph engine will decompose the question across
          Vector RAG, SQL, and Graph stores, enforcing strict claim and citation verification.
        </p>
      </div>

      <div className="rounded-xl border border-gray-800 bg-gray-900/80 p-6 shadow-lg space-y-4">
        <div className="relative">
          <textarea
            rows={3}
            placeholder="e.g. Which customers were impacted by the Payments API last quarter, what incidents occurred, which teams own those services, and what decisions were taken to prevent recurrence?"
            className="w-full rounded-lg border border-gray-700 bg-gray-950 p-4 text-xs font-mono text-gray-200 placeholder-gray-500 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>

        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2 text-[11px] text-gray-400 font-mono">
            <Sparkles size={14} className="text-blue-400" />
            <span>Canonical Question Template Available</span>
          </div>

          <button
            type="button"
            className="inline-flex items-center space-x-2 rounded-lg bg-blue-600 px-4 py-2 text-xs font-semibold text-white shadow-md hover:bg-blue-500 transition-colors"
          >
            <Search size={14} />
            <span>Launch Research (202 Accepted)</span>
          </button>
        </div>
      </div>
    </div>
  );
}
