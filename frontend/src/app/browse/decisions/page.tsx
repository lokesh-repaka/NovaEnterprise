"use client";

import React, { useState, useEffect, useMemo } from "react";
import Link from "next/link";
import {
  FileCode,
  Search,
  ArrowUpDown,
  CheckCircle2,
  AlertCircle,
  Loader2,
  X,
  Sparkles,
  AlertTriangle,
  Calendar,
  RefreshCw,
  GitCommit,
} from "lucide-react";
import { apiClient } from "@/api/client";
import type { DecisionResponse } from "@/types/api";

const STATUS_BADGES: Record<string, { bg: string; text: string; border: string }> = {
  accepted: {
    bg: "bg-emerald-950/60",
    text: "text-emerald-300",
    border: "border-emerald-800/60",
  },
  proposed: {
    bg: "bg-blue-950/60",
    text: "text-blue-300",
    border: "border-blue-800/60",
  },
  superseded: {
    bg: "bg-gray-800/60",
    text: "text-gray-300",
    border: "border-gray-700/60",
  },
  rejected: {
    bg: "bg-red-950/60",
    text: "text-red-300",
    border: "border-red-800/60",
  },
};

export default function DecisionsBrowsePage() {
  const [decisions, setDecisions] = useState<DecisionResponse[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [sortBy, setSortBy] = useState<"title" | "status" | "decided_at">("decided_at");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");
  const [selectedDecision, setSelectedDecision] = useState<DecisionResponse | null>(null);

  const fetchDecisions = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await apiClient.decisions.list();
      setDecisions(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load architectural decision records";
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchDecisions();
  }, []);

  const filteredDecisions = useMemo(() => {
    return decisions
      .filter((d) => {
        const matchesStatus = statusFilter === "all" || d.status === statusFilter;
        const q = search.toLowerCase();
        const matchesSearch =
          !q ||
          d.title.toLowerCase().includes(q) ||
          d.id.toLowerCase().includes(q) ||
          (d.context && d.context.toLowerCase().includes(q)) ||
          (d.decision && d.decision.toLowerCase().includes(q)) ||
          (d.consequences && d.consequences.toLowerCase().includes(q));
        return matchesStatus && matchesSearch;
      })
      .sort((a, b) => {
        let cmp = 0;
        if (sortBy === "title") {
          cmp = a.title.localeCompare(b.title);
        } else if (sortBy === "status") {
          cmp = a.status.localeCompare(b.status);
        } else if (sortBy === "decided_at") {
          const aTime = a.decided_at ? new Date(a.decided_at).getTime() : 0;
          const bTime = b.decided_at ? new Date(b.decided_at).getTime() : 0;
          cmp = aTime - bTime;
        }
        return sortOrder === "asc" ? cmp : -cmp;
      });
  }, [decisions, search, statusFilter, sortBy, sortOrder]);

  const toggleSort = (col: "title" | "status" | "decided_at") => {
    if (sortBy === col) {
      setSortOrder((prev) => (prev === "asc" ? "desc" : "asc"));
    } else {
      setSortBy(col);
      setSortOrder("desc");
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-white tracking-tight">
            Architectural Decisions (ADRs)
          </h2>
          <p className="text-xs text-gray-400">
            Inspect formal architecture decisions, context, trade-offs, and incident post-mortem resolutions.
          </p>
        </div>
        <button
          onClick={fetchDecisions}
          disabled={isLoading}
          className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg border border-gray-800 bg-gray-900 hover:bg-gray-800 text-xs text-gray-300 transition-colors w-fit"
        >
          <RefreshCw size={13} className={isLoading ? "animate-spin" : ""} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search
            size={15}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500"
          />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search architectural decisions, context, consequences..."
            className="w-full pl-9 pr-4 py-2 rounded-lg bg-gray-900 border border-gray-800 text-xs text-gray-200 placeholder-gray-500 focus:outline-none focus:border-blue-500 transition-colors"
          />
          {search && (
            <button
              onClick={() => setSearch("")}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300"
            >
              <X size={14} />
            </button>
          )}
        </div>

        <div className="flex items-center space-x-2">
          <span className="text-xs text-gray-400 font-mono">Status:</span>
          <select
            data-testid="status-filter-select"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-3 py-2 rounded-lg bg-gray-900 border border-gray-800 text-xs font-mono text-gray-200 focus:outline-none focus:border-blue-500 cursor-pointer"
          >
            <option value="all">All Statuses</option>
            <option value="accepted">Accepted</option>
            <option value="proposed">Proposed</option>
            <option value="superseded">Superseded</option>
            <option value="rejected">Rejected</option>
          </select>
        </div>
      </div>

      {/* Error Alert */}
      {error && (
        <div className="flex items-center justify-between p-4 rounded-xl bg-red-950/40 border border-red-800 text-red-300 text-xs">
          <div className="flex items-center space-x-2">
            <AlertCircle size={16} className="flex-shrink-0" />
            <span>Failed to load decisions: {error}</span>
          </div>
          <button
            onClick={fetchDecisions}
            className="px-3 py-1 rounded bg-red-900/60 hover:bg-red-800 border border-red-700 text-xs font-medium"
          >
            Retry
          </button>
        </div>
      )}

      {/* Data Table */}
      <div className="rounded-xl border border-gray-800 bg-[#0d121f] overflow-hidden shadow-xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-gray-800 bg-gray-900/80 text-gray-400 font-mono text-[11px] uppercase tracking-wider">
                <th className="py-3 px-4">ADR ID</th>
                <th
                  onClick={() => toggleSort("title")}
                  className="py-3 px-4 cursor-pointer hover:text-gray-200 transition-colors"
                >
                  <div className="flex items-center space-x-1">
                    <span>Decision Title</span>
                    <ArrowUpDown size={12} />
                  </div>
                </th>
                <th
                  onClick={() => toggleSort("status")}
                  className="py-3 px-4 cursor-pointer hover:text-gray-200 transition-colors"
                >
                  <div className="flex items-center space-x-1">
                    <span>Status</span>
                    <ArrowUpDown size={12} />
                  </div>
                </th>
                <th className="py-3 px-4">Incident Link</th>
                <th
                  onClick={() => toggleSort("decided_at")}
                  className="py-3 px-4 cursor-pointer hover:text-gray-200 transition-colors"
                >
                  <div className="flex items-center space-x-1">
                    <span>Decided</span>
                    <ArrowUpDown size={12} />
                  </div>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800/60 font-sans">
              {isLoading ? (
                <tr>
                  <td colSpan={5} className="py-12 text-center text-gray-500">
                    <Loader2 size={24} className="animate-spin mx-auto mb-2 text-blue-500" />
                    <span>Loading architectural decisions...</span>
                  </td>
                </tr>
              ) : filteredDecisions.length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-12 text-center text-gray-500">
                    No architectural decisions match the filter query.
                  </td>
                </tr>
              ) : (
                filteredDecisions.map((decision) => {
                  const statusBadge = STATUS_BADGES[decision.status] || STATUS_BADGES.proposed;
                  const isSelected = selectedDecision?.id === decision.id;

                  return (
                    <tr
                      key={decision.id}
                      data-testid={`decision-row-${decision.id}`}
                      onClick={() => setSelectedDecision(decision)}
                      className={`hover:bg-gray-800/50 cursor-pointer transition-colors ${
                        isSelected ? "bg-blue-950/20" : ""
                      }`}
                    >
                      <td className="py-3 px-4 font-mono text-[11px] text-gray-400">
                        {decision.id}
                      </td>
                      <td className="py-3 px-4 font-medium text-gray-100 max-w-md">
                        <div className="truncate">{decision.title}</div>
                        {decision.decision && (
                          <div className="text-[11px] text-gray-400 truncate mt-0.5">
                            {decision.decision}
                          </div>
                        )}
                      </td>
                      <td className="py-3 px-4">
                        <span
                          className={`px-2 py-0.5 rounded-full text-[10px] font-mono capitalize font-semibold border ${statusBadge.bg} ${statusBadge.text} ${statusBadge.border}`}
                        >
                          {decision.status}
                        </span>
                      </td>
                      <td className="py-3 px-4 font-mono text-[11px] text-blue-400">
                        {decision.incident_id ? (
                          <span className="flex items-center space-x-1 hover:underline">
                            <AlertTriangle size={12} className="text-amber-400" />
                            <span>{decision.incident_id}</span>
                          </span>
                        ) : (
                          <span className="text-gray-500">—</span>
                        )}
                      </td>
                      <td className="py-3 px-4 font-mono text-[11px] text-gray-400">
                        {decision.decided_at
                          ? new Date(decision.decided_at).toLocaleDateString("en-US", {
                              year: "numeric",
                              month: "short",
                              day: "numeric",
                            })
                          : "—"}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Footer Count */}
        <div className="py-3 px-4 border-t border-gray-800 bg-gray-900/60 text-xs text-gray-400 flex items-center justify-between font-mono">
          <span>Showing {filteredDecisions.length} of {decisions.length} ADRs</span>
          <span className="text-gray-500 text-[11px]">Click an ADR to review context, rationale & trade-offs</span>
        </div>
      </div>

      {/* Decision Detail Drawer */}
      {selectedDecision && (
        <div
          data-testid="decision-detail-drawer"
          className="rounded-xl border border-blue-500/30 bg-[#0e1628] p-5 shadow-2xl space-y-4 animate-in fade-in slide-in-from-top-2"
        >
          <div className="flex items-center justify-between border-b border-gray-800 pb-3">
            <div className="flex items-center space-x-2">
              <FileCode className="text-blue-400" size={18} />
              <h3 className="text-sm font-semibold text-white">
                ADR Overview — {selectedDecision.id}
              </h3>
            </div>
            <button
              onClick={() => setSelectedDecision(null)}
              className="p-1 rounded text-gray-400 hover:text-white hover:bg-gray-800"
            >
              <X size={16} />
            </button>
          </div>

          <div className="space-y-4 text-xs">
            <div>
              <span className="text-[11px] text-gray-400 font-mono uppercase">Title</span>
              <p className="text-sm font-semibold text-gray-100">{selectedDecision.title}</p>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              <div>
                <span className="text-[11px] text-gray-400 font-mono">Status</span>
                <p className="capitalize font-semibold text-emerald-400 font-mono">{selectedDecision.status}</p>
              </div>
              <div>
                <span className="text-[11px] text-gray-400 font-mono">Related Incident</span>
                <p className="font-mono text-blue-400">{selectedDecision.incident_id || "None"}</p>
              </div>
              <div>
                <span className="text-[11px] text-gray-400 font-mono">Decided Date</span>
                <p className="font-mono text-gray-300">
                  {selectedDecision.decided_at ? new Date(selectedDecision.decided_at).toLocaleDateString() : "—"}
                </p>
              </div>
            </div>

            {selectedDecision.context && (
              <div className="p-3 rounded-lg bg-gray-900 border border-gray-800 space-y-1">
                <span className="text-[11px] text-blue-400 font-mono uppercase font-semibold">
                  Context & Problem Statement
                </span>
                <p className="text-gray-300 text-xs leading-relaxed">
                  {selectedDecision.context}
                </p>
              </div>
            )}

            {selectedDecision.decision && (
              <div className="p-3 rounded-lg bg-gray-900 border border-gray-800 space-y-1">
                <span className="text-[11px] text-emerald-400 font-mono uppercase font-semibold">
                  Architectural Decision
                </span>
                <p className="text-gray-300 text-xs leading-relaxed">
                  {selectedDecision.decision}
                </p>
              </div>
            )}

            {selectedDecision.consequences && (
              <div className="p-3 rounded-lg bg-gray-900 border border-gray-800 space-y-1">
                <span className="text-[11px] text-purple-400 font-mono uppercase font-semibold">
                  Consequences & Trade-offs
                </span>
                <p className="text-gray-300 text-xs leading-relaxed">
                  {selectedDecision.consequences}
                </p>
              </div>
            )}
          </div>

          <div className="flex items-center justify-end space-x-3 pt-2">
            {selectedDecision.incident_id && (
              <Link
                href="/browse/incidents"
                className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg border border-gray-700 bg-gray-800 hover:bg-gray-700 text-gray-200 text-xs transition-colors"
              >
                <AlertTriangle size={13} className="text-amber-400" />
                <span>View Incident {selectedDecision.incident_id}</span>
              </Link>
            )}
            <Link
              href={`/search?q=${encodeURIComponent(
                `Explain the rationale and consequences of architectural decision ${selectedDecision.id}`
              )}`}
              className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium transition-colors"
            >
              <Sparkles size={13} />
              <span>Analyze ADR in Research</span>
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
