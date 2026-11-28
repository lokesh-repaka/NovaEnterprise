import React from "react";
import { Users } from "lucide-react";

export default function CustomersBrowsePage() {
  return (
    <div className="space-y-6">
      <div className="flex flex-col space-y-1.5">
        <h2 className="text-2xl font-bold text-white tracking-tight">
          Customer Directory
        </h2>
        <p className="text-xs text-gray-400">
          Browse enterprise accounts, SLA tiers, and incident blast radii.
        </p>
      </div>

      <div className="rounded-xl border border-gray-800 bg-gray-900/60 p-6">
        <div className="rounded-lg border border-gray-800 bg-gray-950 p-6 text-center text-xs text-gray-400">
          Customer records view shell. Full interactive data tables mount in P12-4.
        </div>
      </div>
    </div>
  );
}
