"use client";

import React, { useState } from "react";
import {
  Terminal,
  Play,
  Clock,
  Sparkles,
  AlertTriangle,
  Layers,
  Database,
  Share2,
} from "lucide-react";
import { apiClient } from "@/api/client";
import { RoleGate } from "@/components/auth/RoleGate";
import { useAuth } from "@/context/AuthContext";
import type { GraphNode, GraphEdge, CypherQueryResponse } from "@/types/api";

export interface CypherTerminalProps {
  onResultsLoaded: (nodes: GraphNode[], edges: GraphEdge[]) => void;
}

const CYPHER_TEMPLATES = [
  {
    id: "impacted-services",
    label: "Incidents impacting services",
    query: "MATCH (s:Service)<-[:AFFECTED]-(i:Incident) RETURN s.name, i.incident_id",
  },
  {
    id: "blast-radius",
    label: "Incident customer blast radius",
    query: "MATCH (i:Incident)-[:IMPACTED]->(c:Customer) RETURN i.incident_id, c.name, c.sla_tier",
  },
  {
    id: "team-ownership",
    label: "Team microservice ownership",
    query: "MATCH (t:Team)-[:OWNS]->(s:Service) RETURN t.name, s.name",
  },
];

export function CypherTerminal({ onResultsLoaded }: CypherTerminalProps) {
  const { canPerform } = useAuth();
  const canExecute = canPerform("cypher");

  const [query, setQuery] = useState(CYPHER_TEMPLATES[0].query);
  const [isExecuting, setIsExecuting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastResponse, setLastResponse] = useState<CypherQueryResponse | null>(null);

  const handleExecute = async () => {
    if (!query.trim() || !canExecute) return;
    try {
      setIsExecuting(true);
      setError(null);
      const res = await apiClient.graph.queryCypher({ query: query.trim() });
      setLastResponse(res);
      if (res.nodes && res.nodes.length > 0) {
        onResultsLoaded(res.nodes, res.edges || []);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to execute Cypher query";
      setError(msg);
      setLastResponse(null);
    } finally {
      setIsExecuting(false);
    }
  };

  return (
    <div
      data-testid="cypher-terminal"
      className="rounded-xl border border-gray-800 bg-[#0a0e17] overflow-hidden space-y-3 p-4"
    >
      {/* Terminal Title Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-gray-800 pb-3">
        <div className="flex items-center space-x-2">
          <Terminal size={16} className="text-emerald-400" />
          <h3 className="text-sm font-semibold text-white tracking-tight">
            Read-Only Cypher Terminal
          </h3>
          <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-emerald-950/60 text-emerald-300 border border-emerald-800/40">
            AST-Guarded
          </span>
        </div>

        {/* Template Selectors */}
        <div className="flex items-center space-x-1.5 overflow-x-auto text-xs font-mono">
          <span className="text-gray-500 text-[11px] shrink-0">Presets:</span>
          {CYPHER_TEMPLATES.map((tmpl) => (
            <button
              key={tmpl.id}
              type="button"
              onClick={() => setQuery(tmpl.query)}
              className="px-2 py-0.5 rounded bg-gray-900 hover:bg-gray-800 text-gray-400 hover:text-white border border-gray-800 text-[11px] transition-colors shrink-0"
            >
              {tmpl.label}
            </button>
          ))}
        </div>
      </div>

      {/* Editor & Execution Button */}
      <div className="space-y-2">
        <div className="relative">
          <textarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            rows={3}
            placeholder="MATCH (s:Service)... RETURN s"
            className="w-full p-3 rounded-lg border border-gray-800 bg-black/60 font-mono text-xs text-emerald-300 focus:outline-none focus:border-blue-500 leading-relaxed resize-y"
          />
        </div>

        <div className="flex items-center justify-between">
          <p className="text-[11px] font-mono text-gray-500">
            Write actions (CREATE, DELETE, SET, MERGE) are forbidden at AST parser level.
          </p>

          <RoleGate
            action="cypher"
            showDisabled
            disabledTooltip="Executing Cypher queries requires Analyst or Admin role"
          >
            <button
              type="button"
              onClick={handleExecute}
              disabled={isExecuting || !query.trim() || !canExecute}
              className="py-1.5 px-4 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-mono text-xs font-medium transition-colors flex items-center space-x-1.5 disabled:opacity-50"
            >
              <Play size={12} className={isExecuting ? "animate-pulse" : ""} />
              <span>{isExecuting ? "Executing..." : "Run Cypher"}</span>
            </button>
          </RoleGate>
        </div>
      </div>

      {/* Error Output */}
      {error && (
        <div className="p-3 rounded-lg border border-rose-800/60 bg-rose-950/30 text-rose-300 flex items-start space-x-2 text-xs font-mono">
          <AlertTriangle size={14} className="text-rose-400 shrink-0 mt-0.5" />
          <span className="break-all">{error}</span>
        </div>
      )}

      {/* Results Projection */}
      {lastResponse && (
        <div className="space-y-2 pt-2 border-t border-gray-800/80">
          <div className="flex items-center justify-between text-xs font-mono">
            <div className="flex items-center space-x-3 text-gray-400">
              <span className="text-white font-semibold">
                {lastResponse.results.length}{" "}
                {lastResponse.results.length === 1 ? "result" : "results"}
              </span>
              <span className="flex items-center space-x-1 text-emerald-400">
                <Clock size={11} />
                <span>{lastResponse.execution_time_ms.toFixed(1)}ms</span>
              </span>
            </div>

            {lastResponse.nodes && lastResponse.nodes.length > 0 && (
              <button
                type="button"
                onClick={() =>
                  onResultsLoaded(lastResponse.nodes, lastResponse.edges || [])
                }
                className="text-xs text-blue-400 hover:text-blue-300 flex items-center space-x-1"
              >
                <Share2 size={12} />
                <span>Render {lastResponse.nodes.length} Nodes in Canvas</span>
              </button>
            )}
          </div>

          {/* Results Table */}
          {lastResponse.results.length > 0 && (
            <div className="rounded-lg border border-gray-800 bg-gray-950 overflow-x-auto max-h-48">
              <table className="w-full text-left text-xs font-mono">
                <thead className="bg-gray-900 text-gray-400 border-b border-gray-800 sticky top-0">
                  <tr>
                    {Object.keys(lastResponse.results[0]).map((col) => (
                      <th key={col} className="p-2 font-semibold">
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800 text-gray-200">
                  {lastResponse.results.map((row, idx) => (
                    <tr key={idx} className="hover:bg-gray-900/40">
                      {Object.values(row).map((val, cIdx) => (
                        <td key={cIdx} className="p-2 whitespace-nowrap">
                          {typeof val === "object" ? JSON.stringify(val) : String(val)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
