import React from "react";
import { FileCode } from "lucide-react";

export default function DecisionsBrowsePage() {
  return (
    <div className="space-y-6">
      <div className="flex flex-col space-y-1.5">
        <h2 className="text-2xl font-bold text-white tracking-tight">
          Architectural Decisions (ADRs)
        </h2>
        <p className="text-xs text-gray-400">
          Inspect technical decisions, alternatives considered, and architectural rationale.
        </p>
      </div>

      <div className="rounded-xl border border-gray-800 bg-gray-900/60 p-6">
        <div className="rounded-lg border border-gray-800 bg-gray-950 p-6 text-center text-xs text-gray-400">
          Decisions (ADR) browse view shell. Full interactive data tables mount in P12-4.
        </div>
      </div>
    </div>
  );
}
