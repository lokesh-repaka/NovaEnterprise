"use client";

import React, { useState, useEffect, useCallback, useMemo } from "react";
import {
  Activity,
  Search,
  ChevronDown,
  ChevronRight,
  Clock,
  Code,
  Filter,
  CheckCircle2,
  AlertCircle,
  Play,
  Pause,
  Database,
  Network,
  Cpu,
  RefreshCw,
} from "lucide-react";
import { apiClient } from "@/api/client";
import type { WorkflowEventResponse } from "@/types/api";

export interface LiveEventTracerProps {
  sessionId: string;
  isRunning: boolean;
  initialEvents?: WorkflowEventResponse[];
  selectedNode?: string | null;
  onSelectNode?: (nodeName: string | null) => void;
}

export function LiveEventTracer({
  sessionId,
  isRunning,
  initialEvents = [],
  selectedNode,
  onSelectNode,
}: LiveEventTracerProps) {
  const [events, setEvents] = useState<WorkflowEventResponse[]>(initialEvents);
  const [searchFilter, setSearchFilter] = useState("");
  const [expandedEventIds, setExpandedEventIds] = useState<Set<number>>(new Set());
  const [isPaused, setIsPaused] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  // Sync initialEvents if provided and events state is empty
  useEffect(() => {
    if (initialEvents.length > 0 && events.length === 0) {
      setEvents(initialEvents);
    }
  }, [initialEvents, events.length]);

  const fetchEvents = useCallback(async () => {
    if (!sessionId) return;
    try {
      setIsLoading(true);
      const data = await apiClient.research.getEvents(sessionId);
      setEvents(data);
    } catch {
      // Non-blocking telemetry error (Claude.md §16: Telemetry must never break a run)
    } finally {
      setIsLoading(false);
    }
  }, [sessionId]);

  // Polling loop while session is running (Claude.md §11)
  useEffect(() => {
    let isMounted = true;
    let timer: NodeJS.Timeout | null = null;

    const poll = async () => {
      if (!isPaused && isRunning) {
        await fetchEvents();
      }
      if (isMounted && isRunning && !isPaused) {
        timer = setTimeout(poll, 2000);
      }
    };

    poll();

    return () => {
      isMounted = false;
      if (timer) clearTimeout(timer);
    };
  }, [sessionId, isRunning, isPaused, fetchEvents]);

  const toggleExpand = (eventId: number) => {
    setExpandedEventIds((prev) => {
      const next = new Set(prev);
      if (next.has(eventId)) {
        next.delete(eventId);
      } else {
        next.add(eventId);
      }
      return next;
    });
  };

  const expandAll = () => {
    setExpandedEventIds(new Set(events.map((e) => e.event_id)));
  };

  const collapseAll = () => {
    setExpandedEventIds(new Set());
  };

  // Filter events based on selectedNode and search filter
  const filteredEvents = useMemo(() => {
    return events.filter((e) => {
      if (selectedNode && e.node_name !== selectedNode) {
        return false;
      }
      if (!searchFilter.trim()) {
        return true;
      }
      const query = searchFilter.toLowerCase();
      const nodeMatch = e.node_name.toLowerCase().includes(query);
      const typeMatch = e.event_type.toLowerCase().includes(query);
      const payloadMatch = JSON.stringify(e.payload || {}).toLowerCase().includes(query);
      return nodeMatch || typeMatch || payloadMatch;
    });
  }, [events, selectedNode, searchFilter]);

  const getEventTypeBadge = (eventType: string) => {
    switch (eventType) {
      case "node_complete":
        return (
          <span className="px-2 py-0.5 rounded text-[11px] font-mono font-medium bg-emerald-950/60 text-emerald-300 border border-emerald-800/40">
            complete
          </span>
        );
      case "node_start":
        return (
          <span className="px-2 py-0.5 rounded text-[11px] font-mono font-medium bg-blue-950/60 text-blue-300 border border-blue-800/40">
            start
          </span>
        );
      case "tool_call":
        return (
          <span className="px-2 py-0.5 rounded text-[11px] font-mono font-medium bg-purple-950/60 text-purple-300 border border-purple-800/40">
            tool
          </span>
        );
      case "error":
        return (
          <span className="px-2 py-0.5 rounded text-[11px] font-mono font-medium bg-rose-950/60 text-rose-300 border border-rose-800/40">
            error
          </span>
        );
      default:
        return (
          <span className="px-2 py-0.5 rounded text-[11px] font-mono font-medium bg-gray-800 text-gray-300 border border-gray-700">
            {eventType}
          </span>
        );
    }
  };

  const getNodeIcon = (nodeName: string) => {
    if (nodeName.includes("retrieval") || nodeName.includes("evidence")) {
      return <Database size={13} className="text-amber-400" />;
    }
    if (nodeName.includes("graph")) {
      return <Network size={13} className="text-violet-400" />;
    }
    return <Cpu size={13} className="text-blue-400" />;
  };

  return (
    <div data-testid="live-event-stream" className="space-y-4">
      {/* Control Header & Filters */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-gray-900/60 border border-gray-800 rounded-xl p-3.5">
        <div className="flex items-center space-x-2">
          <Activity size={16} className="text-emerald-400" />
          <h3 className="text-sm font-semibold text-white tracking-tight">
            Live Execution Telemetry
          </h3>
          <span className="text-xs font-mono px-2 py-0.5 rounded-full bg-gray-800 text-gray-300 border border-gray-700">
            {filteredEvents.length} / {events.length} events
          </span>
          {isRunning && (
            <span className="flex items-center space-x-1.5 text-xs font-mono text-emerald-400 pl-2">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-ping" />
              <span>Streaming</span>
            </span>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {/* Node Filter Pill */}
          {selectedNode && (
            <div className="flex items-center space-x-1.5 px-2.5 py-1 rounded-md text-xs font-mono bg-blue-950/60 text-blue-300 border border-blue-800/40">
              <Filter size={11} />
              <span>Node: {selectedNode}</span>
              <button
                type="button"
                onClick={() => onSelectNode?.(null)}
                className="ml-1 text-gray-400 hover:text-white"
                title="Clear node filter"
              >
                ×
              </button>
            </div>
          )}

          {/* Search Input */}
          <div className="relative">
            <Search
              size={13}
              className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400"
            />
            <input
              type="text"
              placeholder="Filter events..."
              value={searchFilter}
              onChange={(e) => setSearchFilter(e.target.value)}
              className="pl-8 pr-3 py-1 text-xs rounded-lg border border-gray-800 bg-gray-950 text-white placeholder-gray-500 focus:outline-none focus:border-blue-500 w-44 sm:w-56"
            />
          </div>

          {/* Action buttons */}
          {isRunning && (
            <button
              type="button"
              onClick={() => setIsPaused(!isPaused)}
              className="p-1.5 rounded-lg border border-gray-800 bg-gray-950 hover:bg-gray-800 text-gray-300 text-xs transition-colors flex items-center space-x-1"
              title={isPaused ? "Resume live streaming" : "Pause live streaming"}
            >
              {isPaused ? <Play size={13} /> : <Pause size={13} />}
            </button>
          )}

          <button
            type="button"
            onClick={fetchEvents}
            disabled={isLoading}
            className="p-1.5 rounded-lg border border-gray-800 bg-gray-950 hover:bg-gray-800 text-gray-300 text-xs transition-colors"
            title="Refresh events"
          >
            <RefreshCw size={13} className={isLoading ? "animate-spin" : ""} />
          </button>

          <div className="flex items-center space-x-1 border-l border-gray-800 pl-2">
            <button
              type="button"
              onClick={expandAll}
              className="text-[11px] font-mono text-gray-400 hover:text-white px-1.5 py-0.5 rounded hover:bg-gray-800"
            >
              Expand
            </button>
            <button
              type="button"
              onClick={collapseAll}
              className="text-[11px] font-mono text-gray-400 hover:text-white px-1.5 py-0.5 rounded hover:bg-gray-800"
            >
              Collapse
            </button>
          </div>
        </div>
      </div>

      {/* Events Stream List */}
      <div className="space-y-2">
        {filteredEvents.length === 0 ? (
          <div className="p-8 text-center rounded-xl border border-gray-800/80 bg-gray-950/40 space-y-2">
            <Activity size={24} className="mx-auto text-gray-600 animate-pulse" />
            <p className="text-xs text-gray-400 font-mono">
              {events.length === 0
                ? isRunning
                  ? "Awaiting initial node telemetry events from LangGraph orchestrator..."
                  : "No telemetry events recorded for this session."
                : "No events match current filter criteria."}
            </p>
          </div>
        ) : (
          filteredEvents.map((event) => {
            const isExpanded = expandedEventIds.has(event.event_id);
            const hasPayload =
              event.payload && Object.keys(event.payload).length > 0;

            return (
              <div
                key={event.event_id}
                data-testid={`event-row-${event.event_id}`}
                onClick={() => hasPayload && toggleExpand(event.event_id)}
                className={`rounded-lg border transition-all text-xs font-mono ${
                  hasPayload ? "cursor-pointer" : ""
                } ${
                  isExpanded
                    ? "border-blue-700/60 bg-blue-950/10"
                    : "border-gray-800/80 bg-gray-950/50 hover:border-gray-700 hover:bg-gray-900/30"
                }`}
              >
                {/* Event Row Summary */}
                <div className="p-3 flex items-center justify-between gap-3">
                  <div className="flex items-center space-x-2.5 overflow-hidden">
                    {hasPayload ? (
                      isExpanded ? (
                        <ChevronDown size={14} className="text-gray-400 shrink-0" />
                      ) : (
                        <ChevronRight size={14} className="text-gray-400 shrink-0" />
                      )
                    ) : (
                      <div className="w-3.5" />
                    )}

                    <span className="text-gray-500 shrink-0">#{event.event_id}</span>

                    <div className="flex items-center space-x-1.5 shrink-0">
                      {getNodeIcon(event.node_name)}
                      <span className="text-white font-semibold">
                        {event.node_name}
                      </span>
                    </div>

                    {getEventTypeBadge(event.event_type)}
                  </div>

                  <div className="flex items-center space-x-3 shrink-0 text-gray-400">
                    {event.latency_ms !== null && (
                      <span className="flex items-center space-x-1 text-emerald-400 font-medium">
                        <Clock size={11} />
                        <span>{event.latency_ms}ms</span>
                      </span>
                    )}

                    <span className="text-gray-500 text-[11px]">
                      {event.timestamp
                        ? new Date(event.timestamp).toLocaleTimeString()
                        : "--"}
                    </span>
                  </div>
                </div>

                {/* Expandable Sanitized Payload Inspector */}
                {isExpanded && hasPayload && (
                  <div className="px-4 pb-3 pt-1 border-t border-gray-800/60 bg-gray-950/80">
                    <div className="flex items-center justify-between text-[11px] text-gray-500 mb-1.5 pt-1">
                      <span className="flex items-center space-x-1">
                        <Code size={12} />
                        <span>Sanitized Telemetry Payload (F16, N9)</span>
                      </span>
                      <span className="text-gray-600">Strict Prompt Privacy Enforced</span>
                    </div>

                    <pre className="p-2.5 rounded bg-black/60 border border-gray-800/80 text-[11px] text-gray-300 font-mono overflow-x-auto leading-relaxed">
                      {JSON.stringify(event.payload, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
