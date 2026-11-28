import React from "react";
import Link from "next/link";
import { ArrowLeft, Clock, Activity, CheckCircle2 } from "lucide-react";

export default function ResearchSessionPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  return (
    <div className="space-y-6">
      <div className="flex items-center space-x-3">
        <Link
          href="/search"
          className="p-1.5 rounded-lg border border-gray-800 bg-gray-900 text-gray-400 hover:text-white hover:bg-gray-800 transition-colors"
        >
          <ArrowLeft size={16} />
        </Link>
        <div>
          <h2 className="text-xl font-bold text-white tracking-tight">
            Research Session Tracer
          </h2>
          <p className="text-xs text-gray-400 font-mono">
            Session ID: active-session-view
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <div className="rounded-xl border border-gray-800 bg-gray-900/60 p-5 space-y-3">
            <h3 className="text-xs font-mono font-semibold uppercase text-gray-400">
              Synthesized Research Report
            </h3>
            <p className="text-xs text-gray-300 leading-relaxed">
              Workflow active. The database state will automatically refresh every 2 seconds.
            </p>
          </div>
        </div>

        <div className="space-y-6">
          <div className="rounded-xl border border-gray-800 bg-gray-900/60 p-5 space-y-3">
            <h3 className="text-xs font-mono font-semibold uppercase text-gray-400">
              13-Node Graph Telemetry
            </h3>
            <div className="flex items-center space-x-2 text-xs text-emerald-400 font-mono">
              <Activity size={14} className="animate-spin" />
              <span>Polling /api/v1/research/...</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
