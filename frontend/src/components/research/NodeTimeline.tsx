"use client";

import React, { useMemo } from "react";
import {
  CheckCircle2,
  Loader2,
  AlertTriangle,
  MinusCircle,
  Circle,
  Activity,
  Clock,
  Sparkles,
} from "lucide-react";
import type { WorkflowEventResponse, ResearchStatus } from "@/types/api";

export interface NodeDefinition {
  id: string;
  label: string;
  description: string;
  phase: "analyze" | "retrieve" | "synthesize" | "verify";
}

export const CANONICAL_NODES: NodeDefinition[] = [
  {
    id: "recall_memory",
    label: "Recall Memory",
    description: "Retrieve relevant prior enterprise context",
    phase: "analyze",
  },
  {
    id: "analyze_query",
    label: "Analyze Query",
    description: "Classify intent and extract domain entities",
    phase: "analyze",
  },
  {
    id: "assess_complexity",
    label: "Assess Complexity",
    description: "Determine execution strategy complexity",
    phase: "analyze",
  },
  {
    id: "decompose",
    label: "Decompose Query",
    description: "Partition inquiry into sub-questions",
    phase: "analyze",
  },
  {
    id: "route_retrieval",
    label: "Route Retrieval",
    description: "Route sub-questions to vector, graph, or SQL",
    phase: "retrieve",
  },
  {
    id: "execute_retrieval",
    label: "Execute Retrieval",
    description: "Execute parallel queries across data stores",
    phase: "retrieve",
  },
  {
    id: "collect_evidence",
    label: "Collect Evidence",
    description: "Gather, deduplicate, and score evidence items",
    phase: "retrieve",
  },
  {
    id: "check_missing_evidence",
    label: "Check Missing Evidence",
    description: "Assess evidence sufficiency for answer",
    phase: "retrieve",
  },
  {
    id: "corrective_retrieval",
    label: "Corrective Retrieval",
    description: "Bounded corrective retrieval loop if needed",
    phase: "retrieve",
  },
  {
    id: "verify_evidence",
    label: "Verify Evidence",
    description: "Ground claims against collected evidence",
    phase: "verify",
  },
  {
    id: "synthesize_answer",
    label: "Synthesize Answer",
    description: "Draft response with [n] citation anchors",
    phase: "synthesize",
  },
  {
    id: "verify_citations",
    label: "Verify Citations",
    description: "Validate citation locators and ground truth",
    phase: "verify",
  },
  {
    id: "update_memory",
    label: "Update Memory",
    description: "Persist session insights to episodic memory",
    phase: "synthesize",
  },
];

export type NodeStatus = "completed" | "running" | "skipped" | "failed" | "pending";

export interface NodeTimelineProps {
  events: WorkflowEventResponse[];
  sessionStatus: ResearchStatus;
  selectedNode?: string | null;
  onSelectNode?: (nodeName: string | null) => void;
}

export function NodeTimeline({
  events,
  sessionStatus,
  selectedNode,
  onSelectNode,
}: NodeTimelineProps) {
  // Compute per-node status and latency
  const nodeStates = useMemo(() => {
    const states: Record<
      string,
      { status: NodeStatus; latencyMs: number | null; error?: string }
    > = {};

    // Map completed events
    const completedNodes = new Map<string, number | null>();
    const startedNodes = new Set<string>();
    const failedNodes = new Map<string, string>();

    let hasCorrectiveRetry = false;

    for (const e of events) {
      if (e.event_type === "node_complete") {
        completedNodes.set(e.node_name, e.latency_ms);
        if (e.node_name === "check_missing_evidence" && e.payload?.needs_retry) {
          hasCorrectiveRetry = true;
        }
        if (e.node_name === "corrective_retrieval") {
          hasCorrectiveRetry = true;
        }
      } else if (e.event_type === "node_start") {
        startedNodes.add(e.node_name);
      } else if (e.event_type === "error") {
        failedNodes.set(
          e.node_name,
          typeof e.payload?.error === "string"
            ? e.payload.error
            : "Node execution failed"
        );
      }
    }

    let foundActiveRunning = false;

    for (let i = 0; i < CANONICAL_NODES.length; i++) {
      const node = CANONICAL_NODES[i];
      const isCompleted = completedNodes.has(node.id);
      const isStarted = startedNodes.has(node.id);
      const isFailed = failedNodes.has(node.id);

      if (isCompleted) {
        states[node.id] = {
          status: "completed",
          latencyMs: completedNodes.get(node.id) ?? null,
        };
      } else if (isFailed) {
        states[node.id] = {
          status: "failed",
          latencyMs: null,
          error: failedNodes.get(node.id),
        };
      } else if (sessionStatus === "completed") {
        // If workflow completed and this node wasn't executed
        if (node.id === "corrective_retrieval" && !hasCorrectiveRetry) {
          states[node.id] = { status: "skipped", latencyMs: null };
        } else {
          states[node.id] = { status: "completed", latencyMs: null };
        }
      } else if (sessionStatus === "failed") {
        if (isStarted) {
          states[node.id] = { status: "failed", latencyMs: null };
        } else {
          states[node.id] = { status: "pending", latencyMs: null };
        }
      } else {
        // Running session
        if (isStarted && !isCompleted) {
          states[node.id] = { status: "running", latencyMs: null };
          foundActiveRunning = true;
        } else if (!foundActiveRunning && !isCompleted) {
          // If corrective retrieval wasn't triggered and we passed check_missing_evidence
          if (
            node.id === "corrective_retrieval" &&
            completedNodes.has("check_missing_evidence") &&
            !hasCorrectiveRetry
          ) {
            states[node.id] = { status: "skipped", latencyMs: null };
          } else {
            states[node.id] = { status: "running", latencyMs: null };
            foundActiveRunning = true;
          }
        } else {
          states[node.id] = { status: "pending", latencyMs: null };
        }
      }
    }

    return states;
  }, [events, sessionStatus]);

  // Compute progress percentage
  const progressPercentage = useMemo(() => {
    if (sessionStatus === "completed") return 100;

    let completedCount = 0;
    let totalCount = 0;

    for (const node of CANONICAL_NODES) {
      const st = nodeStates[node.id]?.status;
      if (st === "skipped") continue; // Don't count skipped nodes in denominator
      totalCount++;
      if (st === "completed") {
        completedCount++;
      }
    }

    if (totalCount === 0) return 0;
    return Math.min(100, Math.round((completedCount / totalCount) * 100));
  }, [sessionStatus, nodeStates]);

  const totalElapsedLatency = useMemo(() => {
    let sum = 0;
    for (const node of CANONICAL_NODES) {
      const lat = nodeStates[node.id]?.latencyMs;
      if (lat) sum += lat;
    }
    return sum;
  }, [nodeStates]);

  const getStatusIcon = (status: NodeStatus) => {
    switch (status) {
      case "completed":
        return <CheckCircle2 size={16} className="text-emerald-400" />;
      case "running":
        return <Loader2 size={16} className="text-amber-400 animate-spin" />;
      case "failed":
        return <AlertTriangle size={16} className="text-rose-400" />;
      case "skipped":
        return <MinusCircle size={16} className="text-gray-500" />;
      case "pending":
      default:
        return <Circle size={16} className="text-gray-600" />;
    }
  };

  const getStatusBadgeStyle = (status: NodeStatus, isSelected: boolean) => {
    if (isSelected) {
      return "border-blue-500 bg-blue-950/40 text-blue-200 ring-1 ring-blue-500/50";
    }
    switch (status) {
      case "completed":
        return "border-emerald-800/60 bg-emerald-950/20 text-emerald-300 hover:border-emerald-700";
      case "running":
        return "border-amber-700/80 bg-amber-950/30 text-amber-200 hover:border-amber-600 animate-pulse";
      case "failed":
        return "border-rose-800/60 bg-rose-950/30 text-rose-300 hover:border-rose-700";
      case "skipped":
        return "border-gray-800 bg-gray-900/30 text-gray-500 hover:border-gray-700 opacity-70";
      case "pending":
      default:
        return "border-gray-800 bg-gray-950/40 text-gray-400 hover:border-gray-700";
    }
  };

  return (
    <div data-testid="node-timeline" className="space-y-4">
      {/* Overall Milestone Progress Bar */}
      <div
        data-testid="workflow-progress-bar"
        className="rounded-xl border border-gray-800 bg-gray-900/60 p-4 space-y-3"
      >
        <div className="flex items-center justify-between text-xs">
          <div className="flex items-center space-x-2 font-mono">
            <Activity size={14} className="text-blue-400" />
            <span className="font-semibold text-white">LangGraph 13-Node Orchestrator</span>
            <span className="text-gray-500">•</span>
            <span
              className={
                sessionStatus === "completed"
                  ? "text-emerald-400 font-bold"
                  : sessionStatus === "running"
                  ? "text-amber-400 font-bold"
                  : "text-rose-400 font-bold"
              }
            >
              {sessionStatus.toUpperCase()}
            </span>
          </div>
          <div className="flex items-center space-x-3 text-xs font-mono text-gray-400">
            {totalElapsedLatency > 0 && (
              <span className="flex items-center gap-1 text-gray-300">
                <Clock size={12} />
                {totalElapsedLatency}ms
              </span>
            )}
            <span className="font-bold text-white text-sm">{progressPercentage}%</span>
          </div>
        </div>

        {/* Progress Fill Bar */}
        <div className="w-full h-2.5 rounded-full bg-gray-800 overflow-hidden relative">
          <div
            className={`h-full transition-all duration-500 rounded-full ${
              sessionStatus === "completed"
                ? "bg-gradient-to-r from-emerald-500 to-teal-400"
                : sessionStatus === "failed"
                ? "bg-gradient-to-r from-amber-500 to-rose-500"
                : "bg-gradient-to-r from-blue-500 via-indigo-500 to-purple-500"
            }`}
            style={{ width: `${progressPercentage}%` }}
          />
        </div>
      </div>

      {/* 13-Node Flow Visualizer */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2.5">
        {CANONICAL_NODES.map((node, index) => {
          const state = nodeStates[node.id] || { status: "pending", latencyMs: null };
          const isSelected = selectedNode === node.id;

          return (
            <button
              key={node.id}
              type="button"
              onClick={() => onSelectNode?.(isSelected ? null : node.id)}
              className={`p-3 rounded-lg border text-left transition-all relative flex flex-col justify-between ${getStatusBadgeStyle(
                state.status,
                isSelected
              )}`}
            >
              <div className="flex items-start justify-between w-full mb-1">
                <span className="text-[10px] font-mono text-gray-500">
                  Step {String(index + 1).padStart(2, "0")}
                </span>
                <div
                  data-testid={`node-status-${node.id}`}
                  data-status={state.status}
                  className="flex items-center space-x-1"
                >
                  {getStatusIcon(state.status)}
                </div>
              </div>

              <div>
                <p className="text-xs font-semibold tracking-tight text-white line-clamp-1">
                  {node.label}
                </p>
                <p className="text-[10px] text-gray-400 line-clamp-1 mt-0.5">
                  {node.description}
                </p>
              </div>

              <div className="mt-2 pt-1.5 border-t border-gray-800/60 flex items-center justify-between text-[10px] font-mono">
                <span className="text-gray-500 capitalize">{node.phase}</span>
                {state.latencyMs !== null && (
                  <span className="text-gray-300 font-medium">{state.latencyMs}ms</span>
                )}
                {state.status === "skipped" && (
                  <span className="text-gray-500 italic">skipped</span>
                )}
                {state.status === "running" && (
                  <span className="text-amber-400 font-semibold animate-pulse">active</span>
                )}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
