"use client";

import React, { useState, useEffect, useMemo } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  Search,
  ArrowUpDown,
  Clock,
  CheckCircle2,
  AlertCircle,
  Loader2,
  X,
  Sparkles,
  Server,
  FileCode,
  RefreshCw,
} from "lucide-react";
import { apiClient } from "@/api/client";
import type { IncidentResponse } from "@/types/api";

const SEVERITY_BADGES: Record<string, { bg: string; text: string; border: string }> = {
  SEV1: {
    bg: "bg-red-950/60",
    text: "text-red-300",
    border: "border-red-800/60",
  },
  SEV2: {
    bg: "bg-orange-950/60",
    text: "text-orange-300",
    border: "border-orange-800/60",
  },
  SEV3: {
    bg: "bg-amber-950/60",
    text: "text-amber-300",
    border: "border-amber-800/60",
  },
  SEV4: {
    bg: "bg-blue-950/60",
    text: "text-blue-300",
    border: "border-blue-800/60",
  },
};

const STATUS_BADGES: Record<string, { bg: string; text: string; border: string }> = {
  investigating: {
    bg: "bg-yellow-950/60",
    text: "text-yellow-300",
    border: "border-yellow-800/60",
  },
  mitigated: {
    bg: "bg-blue-950/60",
    text: "text-blue-300",
    border: "border-blue-800/60",
  },
  resolved: {
    bg: "bg-emerald-950/60",
    text: "text-emerald-300",
    border: "border-emerald-800/60",
  },
};

export default function IncidentsBrowsePage() {
  const [incidents, setIncidents] = useState<IncidentResponse[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState<string>("");
  const [severityFilter, setSeverityFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [sortBy, setSortBy] = useState<"occurred_at" | "severity" | "status">("occurred_at");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");
  const [selectedIncident, setSelectedIncident] = useState<IncidentResponse | null>(null);

  const fetchIncidents = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await apiClient.incidents.list();
      setIncidents(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load incident records";
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchIncidents();
  }, []);

  const filteredIncidents = useMemo(() => {
    return incidents
      .filter((inc) => {
        const matchesSev = severityFilter === "all" || inc.severity === severityFilter;
        const matchesStatus = statusFilter === "all" || inc.status === statusFilter;
        const q = search.toLowerCase();
        const matchesSearch =
          !q ||
          inc.title.toLowerCase().includes(q) ||
          inc.id.toLowerCase().includes(q) ||
          (inc.impacted_service_id && inc.impacted_service_id.toLowerCase().includes(q)) ||
          (inc.root_cause && inc.root_cause.toLowerCase().includes(q));
        return matchesSev && matchesStatus && matchesSearch;
      })
      .sort((a, b) => {
        let cmp = 0;
        if (sortBy === "occurred_at") {
          const aTime = a.occurred_at ? new Date(a.occurred_at).getTime() : 0;
          const bTime = b.occurred_at ? new Date(b.occurred_at).getTime() : 0;
          cmp = aTime - bTime;
        } else if (sortBy === "severity") {
          cmp = a.severity.localeCompare(b.severity);
        } else if (sortBy === "status") {
          cmp = a.status.localeCompare(b.status);
        }
        return sortOrder === "asc" ? cmp : -cmp;
      });
  }, [incidents, search, severityFilter, statusFilter, sortBy, sortOrder]);

  const toggleSort = (col: "occurred_at" | "severity" | "status") => {
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
            Incident Records
          </h2>
          <p className="text-xs text-gray-400">
            Audit operational incidents, severities (SEV1-SEV4), impacted microservices, and root causes.
          </p>
        </div>
        <button
          onClick={fetchIncidents}
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
            placeholder="Search incidents by title, ID, service, or root cause..."
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

        <div className="flex items-center space-x-3">
          <div className="flex items-center space-x-1.5">
            <span className="text-xs text-gray-400 font-mono">Severity:</span>
            <select
              data-testid="severity-filter-select"
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value)}
              className="px-2.5 py-2 rounded-lg bg-gray-900 border border-gray-800 text-xs font-mono text-gray-200 focus:outline-none focus:border-blue-500 cursor-pointer"
            >
              <option value="all">All Severities</option>
              <option value="SEV1">SEV1</option>
              <option value="SEV2">SEV2</option>
              <option value="SEV3">SEV3</option>
              <option value="SEV4">SEV4</option>
            </select>
          </div>

          <div className="flex items-center space-x-1.5">
            <span className="text-xs text-gray-400 font-mono">Status:</span>
            <select
              data-testid="status-filter-select"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="px-2.5 py-2 rounded-lg bg-gray-900 border border-gray-800 text-xs font-mono text-gray-200 focus:outline-none focus:border-blue-500 cursor-pointer"
            >
              <option value="all">All Statuses</option>
              <option value="investigating">Investigating</option>
              <option value="mitigated">Mitigated</option>
              <option value="resolved">Resolved</option>
            </select>
          </div>
        </div>
      </div>

      {/* Error Alert */}
      {error && (
        <div className="flex items-center justify-between p-4 rounded-xl bg-red-950/40 border border-red-800 text-red-300 text-xs">
          <div className="flex items-center space-x-2">
            <AlertCircle size={16} className="flex-shrink-0" />
            <span>Failed to load incident records: {error}</span>
          </div>
          <button
            onClick={fetchIncidents}
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
                <th className="py-3 px-4">Incident ID</th>
                <th className="py-3 px-4">Title & Summary</th>
                <th
                  onClick={() => toggleSort("severity")}
                  className="py-3 px-4 cursor-pointer hover:text-gray-200 transition-colors"
                >
                  <div className="flex items-center space-x-1">
                    <span>Severity</span>
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
                <th className="py-3 px-4">Impacted Service</th>
                <th
                  onClick={() => toggleSort("occurred_at")}
                  className="py-3 px-4 cursor-pointer hover:text-gray-200 transition-colors"
                >
                  <div className="flex items-center space-x-1">
                    <span>Occurred</span>
                    <ArrowUpDown size={12} />
                  </div>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800/60 font-sans">
              {isLoading ? (
                <tr>
                  <td colSpan={6} className="py-12 text-center text-gray-500">
                    <Loader2 size={24} className="animate-spin mx-auto mb-2 text-blue-500" />
                    <span>Loading operational incidents...</span>
                  </td>
                </tr>
              ) : filteredIncidents.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-12 text-center text-gray-500">
                    No incidents match the active filter criteria.
                  </td>
                </tr>
              ) : (
                filteredIncidents.map((incident) => {
                  const sevBadge = SEVERITY_BADGES[incident.severity] || SEVERITY_BADGES.SEV4;
                  const statusBadge = STATUS_BADGES[incident.status] || STATUS_BADGES.resolved;
                  const isSelected = selectedIncident?.id === incident.id;

                  return (
                    <tr
                      key={incident.id}
                      data-testid={`incident-row-${incident.id}`}
                      onClick={() => setSelectedIncident(incident)}
                      className={`hover:bg-gray-800/50 cursor-pointer transition-colors ${
                        isSelected ? "bg-blue-950/20" : ""
                      }`}
                    >
                      <td className="py-3 px-4 font-mono text-[11px] text-gray-400">
                        {incident.id}
                      </td>
                      <td className="py-3 px-4 font-medium text-gray-100 max-w-md">
                        <div className="truncate">{incident.title}</div>
                        {incident.root_cause && (
                          <div className="text-[11px] text-gray-400 truncate mt-0.5">
                            Cause: {incident.root_cause}
                          </div>
                        )}
                      </td>
                      <td className="py-3 px-4">
                        <span
                          className={`px-2 py-0.5 rounded-full text-[10px] font-mono uppercase font-bold border ${sevBadge.bg} ${sevBadge.text} ${sevBadge.border}`}
                        >
                          {incident.severity}
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        <span
                          className={`px-2 py-0.5 rounded-full text-[10px] font-mono capitalize font-medium border ${statusBadge.bg} ${statusBadge.text} ${statusBadge.border}`}
                        >
                          {incident.status}
                        </span>
                      </td>
                      <td className="py-3 px-4 font-mono text-[11px] text-gray-300">
                        {incident.impacted_service_id || "—"}
                      </td>
                      <td className="py-3 px-4 font-mono text-[11px] text-gray-400">
                        {incident.occurred_at
                          ? new Date(incident.occurred_at).toLocaleDateString("en-US", {
                              month: "short",
                              day: "numeric",
                              hour: "2-digit",
                              minute: "2-digit",
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
          <span>Showing {filteredIncidents.length} of {incidents.length} incidents</span>
          <span className="text-gray-500 text-[11px]">Click an incident to inspect root cause & ADR resolution</span>
        </div>
      </div>

      {/* Incident Detail Drawer */}
      {selectedIncident && (
        <div
          data-testid="incident-detail-drawer"
          className="rounded-xl border border-blue-500/30 bg-[#0e1628] p-5 shadow-2xl space-y-4 animate-in fade-in slide-in-from-top-2"
        >
          <div className="flex items-center justify-between border-b border-gray-800 pb-3">
            <div className="flex items-center space-x-2">
              <AlertTriangle className="text-amber-400" size={18} />
              <h3 className="text-sm font-semibold text-white">
                Incident Post-Mortem — {selectedIncident.id}
              </h3>
            </div>
            <button
              onClick={() => setSelectedIncident(null)}
              className="p-1 rounded text-gray-400 hover:text-white hover:bg-gray-800"
            >
              <X size={16} />
            </button>
          </div>

          <div className="space-y-3 text-xs">
            <div>
              <span className="text-[11px] text-gray-400 font-mono uppercase">Incident Title</span>
              <p className="text-sm font-semibold text-gray-100">{selectedIncident.title}</p>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <span className="text-[11px] text-gray-400 font-mono">Severity Level</span>
                <p className="font-bold text-red-400 font-mono">{selectedIncident.severity}</p>
              </div>
              <div>
                <span className="text-[11px] text-gray-400 font-mono">Current Status</span>
                <p className="capitalize font-semibold text-emerald-400">{selectedIncident.status}</p>
              </div>
              <div>
                <span className="text-[11px] text-gray-400 font-mono">Impacted Microservice</span>
                <p className="font-mono text-gray-200">{selectedIncident.impacted_service_id || "N/A"}</p>
              </div>
              <div>
                <span className="text-[11px] text-gray-400 font-mono">Occurred Timestamp</span>
                <p className="font-mono text-gray-300">
                  {selectedIncident.occurred_at ? new Date(selectedIncident.occurred_at).toLocaleString() : "—"}
                </p>
              </div>
            </div>

            {selectedIncident.root_cause && (
              <div className="p-3 rounded-lg bg-gray-900 border border-gray-800 space-y-1">
                <span className="text-[11px] text-amber-400 font-mono uppercase font-semibold">
                  Root Cause Analysis
                </span>
                <p className="text-gray-300 text-xs leading-relaxed">
                  {selectedIncident.root_cause}
                </p>
              </div>
            )}
          </div>

          <div className="flex items-center justify-end space-x-3 pt-2">
            <Link
              href="/browse/decisions"
              className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg border border-gray-700 bg-gray-800 hover:bg-gray-700 text-gray-200 text-xs transition-colors"
            >
              <FileCode size={13} />
              <span>Inspect Associated ADRs</span>
            </Link>
            <Link
              href={`/search?q=${encodeURIComponent(
                `Explain the timeline and root cause of incident ${selectedIncident.id}`
              )}`}
              className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium transition-colors"
            >
              <Sparkles size={13} />
              <span>Run Root Cause Synthesis in Research</span>
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
