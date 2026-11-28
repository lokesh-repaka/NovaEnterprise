"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  Clock,
  Activity,
  CheckCircle2,
  AlertTriangle,
  FileText,
  Database,
  Network,
  RotateCw,
  ShieldCheck,
  Zap,
  ListOrdered,
  Radio,
} from "lucide-react";
import { apiClient } from "@/api/client";
import { NodeTimeline } from "@/components/research/NodeTimeline";
import { LiveEventTracer } from "@/components/research/LiveEventTracer";
import type {
  ResearchSessionResponse,
  CitationItem,
  SubQuestionItem,
  EvidenceSourceType,
  WorkflowEventResponse,
} from "@/types/api";

interface PageProps {
  params: Promise<{ id: string }>;
}

export default function ResearchSessionPage({ params }: PageProps) {
  const [sessionId, setSessionId] = useState<string>("");
  const [session, setSession] = useState<ResearchSessionResponse | null>(null);
  const [events, setEvents] = useState<WorkflowEventResponse[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [selectedCitationId, setSelectedCitationId] = useState<number | null>(null);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"synthesis" | "events">("synthesis");

  // Safely resolve Next.js 15 async params without suspending the component
  useEffect(() => {
    let isMounted = true;
    Promise.resolve(params).then((resolved) => {
      if (isMounted && resolved?.id) {
        setSessionId(resolved.id);
      }
    });
    return () => {
      isMounted = false;
    };
  }, [params]);

  const fetchSession = useCallback(async (id: string) => {
    try {
      const data = await apiClient.research.get(id);
      setSession(data);
      setFetchError(null);
      return data;
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Failed to load research session";
      setFetchError(message);
      return null;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const fetchEvents = useCallback(async (id: string) => {
    try {
      const evts = await apiClient.research.getEvents(id);
      setEvents(evts);
      return evts;
    } catch {
      // Non-blocking telemetry (Claude.md §16: Telemetry must never break a run)
      return [];
    }
  }, []);

  useEffect(() => {
    if (!sessionId) return;

    let isMounted = true;
    let timer: NodeJS.Timeout | null = null;

    const poll = async () => {
      const [data] = await Promise.all([
        fetchSession(sessionId),
        fetchEvents(sessionId),
      ]);

      if (!isMounted) return;

      // Continue polling every 2000ms while status is running (Claude.md §11)
      if (data && data.status === "running") {
        timer = setTimeout(poll, 2000);
      }
    };

    poll();

    return () => {
      isMounted = false;
      if (timer) clearTimeout(timer);
    };
  }, [sessionId, fetchSession, fetchEvents]);

  const getSourceIcon = (sourceType: EvidenceSourceType) => {
    switch (sourceType) {
      case "graph":
        return <Network size={14} className="text-violet-400" />;
      case "document":
        return <FileText size={14} className="text-blue-400" />;
      case "sql":
        return <Database size={14} className="text-amber-400" />;
      default:
        return <FileText size={14} className="text-gray-400" />;
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "completed":
        return (
          <span
            data-testid="session-status-badge"
            className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium border bg-emerald-950/60 text-emerald-300 border-emerald-700/60"
          >
            <CheckCircle2 size={13} className="mr-1.5 text-emerald-400" />
            completed
          </span>
        );
      case "running":
        return (
          <span
            data-testid="session-status-badge"
            className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium border bg-amber-950/60 text-amber-300 border-amber-700/60"
          >
            <RotateCw size={13} className="mr-1.5 animate-spin text-amber-400" />
            running
          </span>
        );
      case "failed":
        return (
          <span
            data-testid="session-status-badge"
            className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium border bg-rose-950/60 text-rose-300 border-rose-700/60"
          >
            <AlertTriangle size={13} className="mr-1.5 text-rose-400" />
            failed
          </span>
        );
      default:
        return (
          <span
            data-testid="session-status-badge"
            className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium border bg-gray-800 text-gray-300 border-gray-700"
          >
            {status}
          </span>
        );
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Header & Navigation */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-gray-800/80 pb-4">
        <div className="flex items-center space-x-3">
          <Link
            href="/search"
            className="p-2 rounded-lg border border-gray-800 bg-gray-900 text-gray-400 hover:text-white hover:bg-gray-800 transition-colors"
            title="Back to research inquiry"
          >
            <ArrowLeft size={16} />
          </Link>
          <div>
            <div className="flex items-center space-x-2.5">
              <h2 className="text-xl font-bold text-white tracking-tight">
                Research Session Tracer
              </h2>
              {session && getStatusBadge(session.status)}
            </div>
            <p className="text-xs text-gray-400 font-mono mt-0.5">
              Session ID: <span className="text-gray-300">{sessionId || "..."}</span>
            </p>
          </div>
        </div>

        {/* Telemetry Stats Bar */}
        {session && (
          <div className="flex flex-wrap items-center gap-2">
            {session.complexity && (
              <span className="px-2.5 py-1 rounded-md text-xs font-mono font-medium bg-gray-800 text-purple-300 border border-purple-800/40">
                {session.complexity}
              </span>
            )}
            {session.verification_ratio !== null && (
              <span className="px-2.5 py-1 rounded-md text-xs font-mono font-medium bg-emerald-950/40 text-emerald-300 border border-emerald-800/40 flex items-center gap-1">
                <ShieldCheck size={13} />
                {Math.round(session.verification_ratio * 100)}% Verified
              </span>
            )}
            {session.execution_time_seconds !== null && (
              <span className="px-2.5 py-1 rounded-md text-xs font-mono font-medium bg-gray-800 text-gray-300 border border-gray-700/60 flex items-center gap-1">
                <Clock size={13} />
                {session.execution_time_seconds.toFixed(2)}s
              </span>
            )}
            {session.corrective_rounds > 0 && (
              <span className="px-2.5 py-1 rounded-md text-xs font-mono font-medium bg-blue-950/40 text-blue-300 border border-blue-800/40">
                {session.corrective_rounds} corrective rounds
              </span>
            )}
          </div>
        )}
      </div>

      {/* Inquiry Question Banner */}
      {session?.question && (
        <div className="rounded-xl border border-gray-800 bg-gray-900/40 p-4">
          <p className="text-xs font-mono uppercase text-gray-400 mb-1">Inquiry Question</p>
          <p className="text-base font-semibold text-white leading-relaxed">
            {session.question}
          </p>
        </div>
      )}

      {/* Error Alert on Failed Status */}
      {session?.status === "failed" && (
        <div
          data-testid="session-error-alert"
          className="rounded-xl border border-rose-800/60 bg-rose-950/30 p-4 text-rose-300 flex items-start space-x-3"
        >
          <AlertTriangle size={18} className="text-rose-400 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <h4 className="text-sm font-semibold text-rose-200">Execution Failed</h4>
            <p className="text-xs text-rose-300 leading-relaxed font-mono">
              {session.error_message || "An unexpected error occurred during research execution."}
            </p>
          </div>
        </div>
      )}

      {/* Global Fetch Error */}
      {fetchError && !session && (
        <div className="rounded-xl border border-rose-800/60 bg-rose-950/30 p-4 text-rose-300 flex items-start space-x-3">
          <AlertTriangle size={18} className="text-rose-400 shrink-0 mt-0.5" />
          <div>
            <h4 className="text-sm font-semibold text-rose-200">Unable to Fetch Session</h4>
            <p className="text-xs text-rose-300">{fetchError}</p>
          </div>
        </div>
      )}

      {/* 13-Node LangGraph Timeline & Progress Bar (P13-2, F16) */}
      <NodeTimeline
        events={events}
        sessionStatus={session?.status || "running"}
        selectedNode={selectedNode}
        onSelectNode={(nodeId) => {
          setSelectedNode(nodeId);
          if (nodeId) {
            setActiveTab("events");
          }
        }}
      />

      {/* Operational View Switcher Tabs */}
      <div className="flex items-center space-x-2 border-b border-gray-800 pb-2">
        <button
          type="button"
          onClick={() => setActiveTab("synthesis")}
          className={`flex items-center space-x-2 px-3.5 py-1.5 rounded-lg text-xs font-medium transition-colors ${
            activeTab === "synthesis"
              ? "bg-blue-600 text-white shadow-sm"
              : "text-gray-400 hover:text-white hover:bg-gray-800"
          }`}
        >
          <Zap size={14} />
          <span>Synthesis & Citations</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("events")}
          className={`flex items-center space-x-2 px-3.5 py-1.5 rounded-lg text-xs font-medium transition-colors ${
            activeTab === "events"
              ? "bg-blue-600 text-white shadow-sm"
              : "text-gray-400 hover:text-white hover:bg-gray-800"
          }`}
        >
          <Radio size={14} />
          <span>Live Telemetry Stream ({events.length})</span>
        </button>
      </div>

      {/* Tab 1: Synthesis & Citations View */}
      {activeTab === "synthesis" && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column (2 Cols): Synthesized Answer & Decomposed Sub-Questions */}
          <div className="lg:col-span-2 space-y-6">
            {/* Synthesized Research Report */}
            <div className="rounded-xl border border-gray-800 bg-gray-900/60 p-5 space-y-4">
              <div className="flex items-center justify-between border-b border-gray-800 pb-3">
                <h3 className="text-sm font-semibold text-white tracking-tight flex items-center gap-2">
                  <Zap size={16} className="text-emerald-400" />
                  Synthesized Research Report
                </h3>
                {session?.status === "running" && (
                  <span className="flex items-center text-xs font-mono text-amber-400">
                    <RotateCw size={12} className="animate-spin mr-1" />
                    Generating...
                  </span>
                )}
              </div>

              {session?.status === "running" && !session.answer && (
                <div className="space-y-3 py-4 text-center">
                  <div className="inline-flex items-center justify-center p-3 rounded-full bg-amber-950/30 text-amber-400 mb-2">
                    <Activity size={24} className="animate-pulse" />
                  </div>
                  <p className="text-xs text-gray-300 leading-relaxed">
                    Workflow active. The database state will automatically refresh every 2 seconds.
                  </p>
                  <p className="text-xs text-gray-500 font-mono">
                    LangGraph 13-node pipeline is orchestrating retrieval routes...
                  </p>
                </div>
              )}

              {session?.answer && (
                <div className="text-sm text-gray-200 leading-relaxed space-y-3 font-sans">
                  <p className="whitespace-pre-wrap">{session.answer}</p>
                </div>
              )}

              {session?.status === "failed" && !session.answer && (
                <p className="text-xs text-gray-400 italic">
                  Report generation halted due to session failure.
                </p>
              )}
            </div>

            {/* Decomposed Sub-Questions and Routing Strategies */}
            {session?.sub_questions && session.sub_questions.length > 0 && (
              <div className="rounded-xl border border-gray-800 bg-gray-900/60 p-5 space-y-4">
                <div className="flex items-center justify-between border-b border-gray-800 pb-3">
                  <h3 className="text-sm font-semibold text-white tracking-tight">
                    Decomposed Sub-Questions & Routing
                  </h3>
                  <span className="text-xs font-mono text-gray-400">
                    {session.sub_questions.length} queries
                  </span>
                </div>

                <div className="space-y-3">
                  {session.sub_questions.map((sq: SubQuestionItem) => (
                    <div
                      key={sq.id}
                      className="p-3.5 rounded-lg border border-gray-800 bg-gray-950/60 flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:border-gray-700 transition-colors"
                    >
                      <div className="space-y-1">
                        <p className="text-xs font-mono text-gray-400">ID: {sq.id}</p>
                        <p className="text-sm font-medium text-white">{sq.question}</p>
                      </div>

                      <div className="flex items-center space-x-2 shrink-0">
                        <span className="px-2 py-0.5 rounded text-xs font-mono font-medium bg-indigo-950/60 text-indigo-300 border border-indigo-800/40">
                          {sq.strategy}
                        </span>
                        <span
                          className={`px-2 py-0.5 rounded text-xs font-mono capitalize ${
                            sq.status === "answered"
                              ? "bg-emerald-950/60 text-emerald-300 border border-emerald-800/40"
                              : sq.status === "failed"
                              ? "bg-rose-950/60 text-rose-300 border border-rose-800/40"
                              : "bg-gray-800 text-gray-300 border border-gray-700"
                          }`}
                        >
                          {sq.status}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Right Column (1 Col): Citations & Telemetry */}
          <div className="space-y-6">
            {/* Verified Citations List */}
            <div className="rounded-xl border border-gray-800 bg-gray-900/60 p-5 space-y-4">
              <div className="flex items-center justify-between border-b border-gray-800 pb-3">
                <h3 className="text-sm font-semibold text-white tracking-tight flex items-center gap-2">
                  <ShieldCheck size={16} className="text-indigo-400" />
                  Verified Citations
                </h3>
                <span className="text-xs font-mono text-gray-400">
                  {session?.citations?.length || 0} citations
                </span>
              </div>

              {session?.citations && session.citations.length > 0 ? (
                <div className="space-y-3">
                  {session.citations.map((c: CitationItem) => (
                    <div
                      key={c.citation_id}
                      onClick={() =>
                        setSelectedCitationId(
                          selectedCitationId === c.citation_id ? null : c.citation_id
                        )
                      }
                      className={`p-3 rounded-lg border transition-all cursor-pointer ${
                        selectedCitationId === c.citation_id
                          ? "border-emerald-600/80 bg-emerald-950/20"
                          : "border-gray-800 bg-gray-950/50 hover:border-gray-700"
                      }`}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center space-x-2">
                          <span className="px-1.5 py-0.5 rounded text-xs font-mono font-bold bg-gray-800 text-emerald-400">
                            [{c.citation_id}]
                          </span>
                          <span className="inline-flex items-center space-x-1 text-xs font-mono text-gray-400">
                            {getSourceIcon(c.source_type)}
                            <span>{c.source_type.toUpperCase()}</span>
                          </span>
                        </div>
                        <span className="text-xs font-mono text-gray-500">
                          {c.evidence_id}
                        </span>
                      </div>

                      <p className="text-xs text-gray-300 font-medium leading-relaxed mb-2">
                        {c.snippet}
                      </p>

                      <div className="pt-2 border-t border-gray-800/80">
                        <p className="text-[11px] font-mono text-gray-400 break-all">
                          {c.locator}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-gray-400 italic py-2">
                  {session?.status === "running"
                    ? "Awaiting citation verification..."
                    : "No citations recorded for this session."}
                </p>
              )}
            </div>

            {/* Quick Telemetry Link Card */}
            <div className="rounded-xl border border-gray-800 bg-gray-900/60 p-5 space-y-3">
              <h3 className="text-sm font-semibold text-white tracking-tight flex items-center gap-2">
                <Activity size={16} className="text-blue-400" />
                Telemetry Summary
              </h3>
              <p className="text-xs text-gray-400">
                {events.length} workflow transition events captured in database.
              </p>
              <button
                type="button"
                onClick={() => setActiveTab("events")}
                className="w-full py-2 px-3 text-xs font-mono font-medium rounded-lg bg-blue-600/20 hover:bg-blue-600/30 text-blue-300 border border-blue-500/30 transition-colors flex items-center justify-center space-x-1.5"
              >
                <Radio size={13} />
                <span>Open Live Event Tracer</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Tab 2: Live Event Tracer & Timeline View (P13-2, F16) */}
      {activeTab === "events" && (
        <LiveEventTracer
          sessionId={sessionId}
          isRunning={session?.status === "running"}
          initialEvents={events}
          selectedNode={selectedNode}
          onSelectNode={setSelectedNode}
        />
      )}
    </div>
  );
}
