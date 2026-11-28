"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import {
  Search,
  Sparkles,
  Clock,
  ArrowRight,
  AlertCircle,
  Loader2,
  CheckCircle2,
  Activity,
  FileText,
  RotateCcw,
} from "lucide-react";
import { apiClient } from "@/api/client";
import { useAuth } from "@/context/AuthContext";
import { RoleGate } from "@/components/auth/RoleGate";
import type { ResearchSessionSummary, QueryComplexity, ResearchStatus } from "@/types/api";

const CANONICAL_TEMPLATES = [
  {
    id: "canonical",
    label: "Payments API Outage & ADR Blast Radius (Canonical)",
    query:
      "Which customers were impacted by the Payments API outage last quarter and what ADR was created to address it?",
  },
  {
    id: "incident-root-cause",
    label: "Incident INC-2031 Post-Mortem & Ownership",
    query:
      "What is the root cause of incident INC-2031 and which team owns the affected microservice?",
  },
  {
    id: "customer-sla",
    label: "Enterprise Customer Directory & High-Severity Impact",
    query:
      "List enterprise customers with SLA tier enterprise that experienced service degradation.",
  },
];

const COMPLEXITY_BADGES: Record<QueryComplexity, { bg: string; text: string; border: string }> = {
  simple: {
    bg: "bg-emerald-950/60",
    text: "text-emerald-300",
    border: "border-emerald-800/60",
  },
  moderate: {
    bg: "bg-blue-950/60",
    text: "text-blue-300",
    border: "border-blue-800/60",
  },
  complex: {
    bg: "bg-purple-950/60",
    text: "text-purple-300",
    border: "border-purple-800/60",
  },
};

const STATUS_BADGES: Record<ResearchStatus, { bg: string; text: string; border: string }> = {
  running: {
    bg: "bg-amber-950/60",
    text: "text-amber-300",
    border: "border-amber-800/60",
  },
  completed: {
    bg: "bg-emerald-950/60",
    text: "text-emerald-300",
    border: "border-emerald-800/60",
  },
  failed: {
    bg: "bg-red-950/60",
    text: "text-red-300",
    border: "border-red-800/60",
  },
};

function SearchContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user, canPerform } = useAuth();

  const [question, setQuestion] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [recentSessions, setRecentSessions] = useState<ResearchSessionSummary[]>([]);
  const [isLoadingSessions, setIsLoadingSessions] = useState(true);

  // Pre-fill query if passed via search param (e.g. from browse views)
  useEffect(() => {
    const q = searchParams.get("q");
    if (q) {
      setQuestion(q);
    }
  }, [searchParams]);

  // Load recent research sessions
  useEffect(() => {
    let isMounted = true;
    async function loadSessions() {
      try {
        const data = await apiClient.research.list({ limit: 10 });
        if (isMounted) {
          setRecentSessions(data);
        }
      } catch {
        // Non-blocking for recent sessions
      } finally {
        if (isMounted) {
          setIsLoadingSessions(false);
        }
      }
    }
    loadSessions();
    return () => {
      isMounted = false;
    };
  }, []);

  const handleLaunchResearch = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = question.trim();
    if (!trimmed) return;

    setIsSubmitting(true);
    setError(null);

    try {
      // 202 Accepted Async Intake (F1)
      const res = await apiClient.research.create({
        question: trimmed,
        user_id: user?.id,
      });

      router.push(`/research/${res.session_id}`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to initiate research workflow";
      setError(msg);
      setIsSubmitting(false);
    }
  };

  const handleTemplateSelect = (templateQuery: string) => {
    setQuestion(templateQuery);
    setError(null);
  };

  const canExecute = canPerform("research");

  return (
    <div className="space-y-8 max-w-6xl mx-auto">
      {/* Page Header */}
      <div className="flex flex-col space-y-1.5">
        <div className="flex items-center space-x-2">
          <Sparkles className="text-blue-400" size={20} />
          <h2 className="text-2xl font-bold text-white tracking-tight">
            Research Intelligence Interface
          </h2>
        </div>
        <p className="text-xs text-gray-400 leading-relaxed">
          Enter an enterprise inquiry across document corpus, SQL transactional databases, and graph models.
          The 13-node LangGraph workflow decomposes queries into sub-questions, executes multi-store retrieval,
          and performs citation and claim verification.
        </p>
      </div>

      {/* Inquiry Formulation Card */}
      <div className="rounded-xl border border-gray-800 bg-[#0d121f] p-6 shadow-2xl space-y-5">
        <form onSubmit={handleLaunchResearch} className="space-y-4">
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label
                htmlFor="inquiry-input"
                className="text-xs font-mono font-medium text-gray-300"
              >
                Enterprise NL Inquiry Prompt
              </label>
              <span className="text-[11px] font-mono text-gray-500">
                {question.length} / 2000 chars
              </span>
            </div>

            <textarea
              id="inquiry-input"
              rows={4}
              required
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Enter an enterprise inquiry: e.g. Which customers were impacted by the Payments API outage last quarter and what ADR was created to address it?"
              className="w-full rounded-lg border border-gray-800 bg-gray-950 p-4 text-xs font-mono text-gray-100 placeholder-gray-500 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all leading-relaxed"
            />
          </div>

          {/* Quick Canonical Templates */}
          <div className="space-y-2">
            <span className="text-[11px] font-mono text-gray-400 uppercase tracking-wider">
              Canonical Question Presets:
            </span>
            <div className="flex flex-wrap gap-2">
              {CANONICAL_TEMPLATES.map((tmpl) => (
                <button
                  key={tmpl.id}
                  data-testid={`template-btn-${tmpl.id}`}
                  type="button"
                  onClick={() => handleTemplateSelect(tmpl.query)}
                  className="px-3 py-1.5 rounded-lg border border-gray-800 bg-gray-900/80 hover:bg-gray-800 text-[11px] text-gray-300 hover:text-white transition-colors text-left flex items-center space-x-1.5"
                >
                  <Sparkles size={12} className="text-blue-400 flex-shrink-0" />
                  <span>{tmpl.label}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Error Banner */}
          {error && (
            <div
              data-testid="research-error-banner"
              className="flex items-center space-x-2 p-3.5 rounded-lg bg-red-950/40 border border-red-800 text-red-300 text-xs"
            >
              <AlertCircle size={16} className="flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Controls Bar */}
          <div className="flex items-center justify-between pt-2 border-t border-gray-800/80">
            <div className="text-[11px] font-mono text-gray-400 flex items-center space-x-1.5">
              <Activity size={14} className="text-emerald-400" />
              <span>LangGraph Multi-Agent RAG Engine · F1 (202 Intake)</span>
            </div>

            <RoleGate
              action="research"
              showDisabled
              disabledTooltip="Research inquiry creation requires Analyst or Admin role"
            >
              <button
                type="submit"
                disabled={isSubmitting || !question.trim() || !canExecute}
                className="inline-flex items-center space-x-2 rounded-lg bg-blue-600 px-5 py-2.5 text-xs font-semibold text-white shadow-lg shadow-blue-600/20 hover:bg-blue-500 disabled:opacity-50 transition-all cursor-pointer disabled:cursor-not-allowed"
              >
                {isSubmitting ? (
                  <>
                    <Loader2 size={14} className="animate-spin" />
                    <span>Launching Workflow (202)...</span>
                  </>
                ) : (
                  <>
                    <Search size={14} />
                    <span>Launch Research (202 Accepted)</span>
                  </>
                )}
              </button>
            </RoleGate>
          </div>
        </form>
      </div>

      {/* Recent Research Sessions */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-white font-mono flex items-center space-x-2">
            <Clock size={15} className="text-gray-400" />
            <span>Recent Research Sessions</span>
          </h3>
          <span className="text-xs text-gray-500 font-mono">
            Poll state stored in database
          </span>
        </div>

        <div className="rounded-xl border border-gray-800 bg-[#0d121f] overflow-hidden shadow-xl">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-gray-800 bg-gray-900/80 text-gray-400 font-mono text-[11px] uppercase tracking-wider">
                  <th className="py-3 px-4">Session ID</th>
                  <th className="py-3 px-4">Inquiry Question</th>
                  <th className="py-3 px-4">Complexity</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Created</th>
                  <th className="py-3 px-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800/60 font-sans">
                {isLoadingSessions ? (
                  <tr>
                    <td colSpan={6} className="py-8 text-center text-gray-500">
                      <Loader2 size={20} className="animate-spin mx-auto mb-1 text-blue-500" />
                      <span>Loading recent sessions...</span>
                    </td>
                  </tr>
                ) : recentSessions.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-8 text-center text-gray-500 font-mono text-xs">
                      No research sessions recorded yet. Launch your first query above.
                    </td>
                  </tr>
                ) : (
                  recentSessions.map((s) => {
                    const statusBadge = STATUS_BADGES[s.status] || STATUS_BADGES.running;
                    const complexityBadge = s.complexity
                      ? COMPLEXITY_BADGES[s.complexity]
                      : null;

                    return (
                      <tr
                        key={s.session_id}
                        className="hover:bg-gray-800/50 transition-colors"
                      >
                        <td className="py-3 px-4 font-mono text-[11px] text-gray-400">
                          {s.session_id.substring(0, 8)}...
                        </td>
                        <td className="py-3 px-4 font-medium text-gray-200 max-w-md truncate">
                          {s.question}
                        </td>
                        <td className="py-3 px-4">
                          {complexityBadge ? (
                            <span
                              className={`px-2 py-0.5 rounded-full text-[10px] font-mono uppercase font-semibold border ${complexityBadge.bg} ${complexityBadge.text} ${complexityBadge.border}`}
                            >
                              {s.complexity}
                            </span>
                          ) : (
                            <span className="text-gray-500 font-mono text-[11px]">—</span>
                          )}
                        </td>
                        <td className="py-3 px-4">
                          <span
                            className={`flex items-center space-x-1.5 w-fit px-2 py-0.5 rounded-full text-[10px] font-mono capitalize font-medium border ${statusBadge.bg} ${statusBadge.text} ${statusBadge.border}`}
                          >
                            {s.status === "running" && (
                              <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
                            )}
                            {s.status === "completed" && (
                              <CheckCircle2 size={11} className="text-emerald-400" />
                            )}
                            {s.status === "failed" && (
                              <AlertCircle size={11} className="text-red-400" />
                            )}
                            <span>{s.status}</span>
                          </span>
                        </td>
                        <td className="py-3 px-4 font-mono text-[11px] text-gray-400">
                          {new Date(s.created_at).toLocaleTimeString("en-US", {
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
                        </td>
                        <td className="py-3 px-4 text-right">
                          <Link
                            href={`/research/${s.session_id}`}
                            className="inline-flex items-center space-x-1 px-2.5 py-1 rounded bg-blue-600/20 hover:bg-blue-600/40 text-blue-400 border border-blue-500/30 text-[11px] font-mono transition-colors"
                          >
                            <span>Trace</span>
                            <ArrowRight size={11} />
                          </Link>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function SearchPage() {
  return (
    <React.Suspense
      fallback={
        <div className="flex items-center justify-center p-12 text-gray-500 font-mono text-sm">
          <Loader2 className="animate-spin mr-2" size={16} />
          Loading research interface...
        </div>
      }
    >
      <SearchContent />
    </React.Suspense>
  );
}
