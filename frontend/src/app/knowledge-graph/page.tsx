import React from "react";
import { Network, Search, Layers, Play } from "lucide-react";

export default function KnowledgeGraphPage() {
  return (
    <div className="space-y-6">
      <div className="flex flex-col space-y-1.5">
        <h2 className="text-2xl font-bold text-white tracking-tight">
          Knowledge Graph Explorer
        </h2>
        <p className="text-xs text-gray-400">
          Traverse enterprise topology (Services, Teams, Customers, Incidents) or run governed read-only Cypher queries.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="md:col-span-1 rounded-xl border border-gray-800 bg-gray-900/60 p-4 space-y-4">
          <h3 className="text-xs font-mono font-semibold text-gray-400 uppercase">
            Graph Entities
          </h3>
          <div className="space-y-1.5 text-xs text-gray-300">
            <div className="p-2 rounded bg-gray-950 border border-gray-800 flex justify-between">
              <span>Services</span>
              <span className="font-mono text-blue-400">8</span>
            </div>
            <div className="p-2 rounded bg-gray-950 border border-gray-800 flex justify-between">
              <span>Teams</span>
              <span className="font-mono text-emerald-400">6</span>
            </div>
            <div className="p-2 rounded bg-gray-950 border border-gray-800 flex justify-between">
              <span>Customers</span>
              <span className="font-mono text-purple-400">10</span>
            </div>
            <div className="p-2 rounded bg-gray-950 border border-gray-800 flex justify-between">
              <span>Incidents</span>
              <span className="font-mono text-amber-400">12</span>
            </div>
          </div>
        </div>

        <div className="md:col-span-3 rounded-xl border border-gray-800 bg-[#090d16] p-6 flex items-center justify-center min-h-[400px]">
          <div className="text-center space-y-2">
            <Network size={36} className="text-blue-500 mx-auto animate-pulse" />
            <h4 className="text-sm font-semibold text-gray-200">
              Interactive Graph Canvas (Phase 13)
            </h4>
            <p className="text-xs text-gray-500 max-w-sm">
              Visual node expansion and graph exploration components mount in Phase 13.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
