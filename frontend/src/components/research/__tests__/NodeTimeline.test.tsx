import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { NodeTimeline } from "../NodeTimeline";
import type { WorkflowEventResponse } from "@/types/api";

describe("NodeTimeline Component", () => {
  const sessionId = "f47ac10b-58cc-4372-a567-0e02b2c3d479";

  const mockCompletedEvents: WorkflowEventResponse[] = [
    {
      event_id: 1,
      session_id: sessionId,
      node_name: "recall_memory",
      event_type: "node_complete",
      payload: { memory_count: 2 },
      latency_ms: 45,
      timestamp: "2026-11-27T12:00:00.045Z",
    },
    {
      event_id: 2,
      session_id: sessionId,
      node_name: "analyze_query",
      event_type: "node_complete",
      payload: { intent: "enterprise_incident_lookup" },
      latency_ms: 120,
      timestamp: "2026-11-27T12:00:00.165Z",
    },
    {
      event_id: 3,
      session_id: sessionId,
      node_name: "assess_complexity",
      event_type: "node_complete",
      payload: { complexity: "complex" },
      latency_ms: 110,
      timestamp: "2026-11-27T12:00:00.275Z",
    },
    {
      event_id: 4,
      session_id: sessionId,
      node_name: "decompose",
      event_type: "node_complete",
      payload: { sub_question_count: 2 },
      latency_ms: 95,
      timestamp: "2026-11-27T12:00:00.370Z",
    },
    {
      event_id: 5,
      session_id: sessionId,
      node_name: "route_retrieval",
      event_type: "node_complete",
      payload: { routes: { sq1: "graph", sq2: "vector" } },
      latency_ms: 60,
      timestamp: "2026-11-27T12:00:00.430Z",
    },
    {
      event_id: 6,
      session_id: sessionId,
      node_name: "execute_retrieval",
      event_type: "node_complete",
      payload: { total_records_fetched: 5 },
      latency_ms: 350,
      timestamp: "2026-11-27T12:00:00.780Z",
    },
    {
      event_id: 7,
      session_id: sessionId,
      node_name: "collect_evidence",
      event_type: "node_complete",
      payload: { evidence_count: 4 },
      latency_ms: 50,
      timestamp: "2026-11-27T12:00:00.830Z",
    },
    {
      event_id: 8,
      session_id: sessionId,
      node_name: "check_missing_evidence",
      event_type: "node_complete",
      payload: { needs_retry: false },
      latency_ms: 70,
      timestamp: "2026-11-27T12:00:00.900Z",
    },
    {
      event_id: 9,
      session_id: sessionId,
      node_name: "verify_evidence",
      event_type: "node_complete",
      payload: { verification_ratio: 1.0 },
      latency_ms: 140,
      timestamp: "2026-11-27T12:00:01.040Z",
    },
    {
      event_id: 10,
      session_id: sessionId,
      node_name: "synthesize_answer",
      event_type: "node_complete",
      payload: { citation_count: 2 },
      latency_ms: 410,
      timestamp: "2026-11-27T12:00:01.450Z",
    },
    {
      event_id: 11,
      session_id: sessionId,
      node_name: "verify_citations",
      event_type: "node_complete",
      payload: { resolved_citations: 2, invalid_citations: 0 },
      latency_ms: 80,
      timestamp: "2026-11-27T12:00:01.530Z",
    },
    {
      event_id: 12,
      session_id: sessionId,
      node_name: "update_memory",
      event_type: "node_complete",
      payload: { stored: true },
      latency_ms: 35,
      timestamp: "2026-11-27T12:00:01.565Z",
    },
  ];

  it("renders 13-node topology timeline container and all canonical nodes", () => {
    render(<NodeTimeline events={mockCompletedEvents} sessionStatus="completed" />);

    expect(screen.getByTestId("node-timeline")).toBeInTheDocument();
    expect(screen.getByTestId("workflow-progress-bar")).toBeInTheDocument();

    // Check key 13 canonical nodes
    expect(screen.getByText("Recall Memory")).toBeInTheDocument();
    expect(screen.getByText("Analyze Query")).toBeInTheDocument();
    expect(screen.getByText("Assess Complexity")).toBeInTheDocument();
    expect(screen.getByText("Decompose Query")).toBeInTheDocument();
    expect(screen.getByText("Route Retrieval")).toBeInTheDocument();
    expect(screen.getByText("Execute Retrieval")).toBeInTheDocument();
    expect(screen.getByText("Collect Evidence")).toBeInTheDocument();
    expect(screen.getByText("Check Missing Evidence")).toBeInTheDocument();
    expect(screen.getByText("Verify Evidence")).toBeInTheDocument();
    expect(screen.getByText("Synthesize Answer")).toBeInTheDocument();
    expect(screen.getByText("Verify Citations")).toBeInTheDocument();
    expect(screen.getByText("Update Memory")).toBeInTheDocument();
  });

  it("renders 100% progress when session status is completed", () => {
    render(<NodeTimeline events={mockCompletedEvents} sessionStatus="completed" />);

    const progressBar = screen.getByTestId("workflow-progress-bar");
    expect(progressBar).toHaveTextContent("100%");
    expect(screen.getByText("45ms")).toBeInTheDocument();
    expect(screen.getByText("410ms")).toBeInTheDocument();
  });

  it("indicates in-progress running state for currently active node", () => {
    const runningEvents: WorkflowEventResponse[] = [
      {
        event_id: 1,
        session_id: sessionId,
        node_name: "recall_memory",
        event_type: "node_complete",
        payload: {},
        latency_ms: 40,
        timestamp: "2026-11-27T12:00:00Z",
      },
      {
        event_id: 2,
        session_id: sessionId,
        node_name: "analyze_query",
        event_type: "node_start",
        payload: {},
        latency_ms: null,
        timestamp: "2026-11-27T12:00:00.1Z",
      },
    ];

    render(<NodeTimeline events={runningEvents} sessionStatus="running" />);

    expect(screen.getByTestId("node-status-analyze_query")).toHaveAttribute("data-status", "running");
    expect(screen.getByTestId("node-status-recall_memory")).toHaveAttribute("data-status", "completed");
    expect(screen.getByTestId("node-status-synthesize_answer")).toHaveAttribute("data-status", "pending");
  });

  it("handles skipped corrective retrieval node when retry is not needed", () => {
    render(<NodeTimeline events={mockCompletedEvents} sessionStatus="completed" />);

    const correctiveNode = screen.getByTestId("node-status-corrective_retrieval");
    expect(correctiveNode).toHaveAttribute("data-status", "skipped");
  });

  it("allows selecting a node to view its specific execution details", () => {
    const onSelectNode = vi.fn();
    render(
      <NodeTimeline
        events={mockCompletedEvents}
        sessionStatus="completed"
        onSelectNode={onSelectNode}
      />
    );

    fireEvent.click(screen.getByText("Assess Complexity"));
    expect(onSelectNode).toHaveBeenCalledWith("assess_complexity");
  });
});
