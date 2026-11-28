import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { LiveEventTracer } from "../LiveEventTracer";
import { apiClient } from "@/api/client";
import type { WorkflowEventResponse } from "@/types/api";

describe("LiveEventTracer Component", () => {
  const sessionId = "f47ac10b-58cc-4372-a567-0e02b2c3d479";

  const mockEvents: WorkflowEventResponse[] = [
    {
      event_id: 101,
      session_id: sessionId,
      node_name: "assess_complexity",
      event_type: "node_complete",
      payload: {
        complexity: "complex",
        reason: "Cross-domain entity join involving customers, incidents, and decisions",
      },
      latency_ms: 142,
      timestamp: "2026-11-27T12:00:01.142Z",
    },
    {
      event_id: 102,
      session_id: sessionId,
      node_name: "route_retrieval",
      event_type: "node_complete",
      payload: {
        routes: {
          sq1: "graph",
          sq2: "vector",
        },
      },
      latency_ms: 88,
      timestamp: "2026-11-27T12:00:01.230Z",
    },
    {
      event_id: 103,
      session_id: sessionId,
      node_name: "execute_retrieval",
      event_type: "tool_call",
      payload: {
        tool: "cypher_traversal",
        query: "MATCH (s:Service {name: 'Payments API'})<-[:AFFECTED]-(i:Incident) RETURN i",
      },
      latency_ms: 215,
      timestamp: "2026-11-27T12:00:01.445Z",
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders live event stream container and polls events when running", async () => {
    vi.spyOn(apiClient.research, "getEvents").mockResolvedValue(mockEvents);

    render(<LiveEventTracer sessionId={sessionId} isRunning={true} />);

    expect(screen.getByTestId("live-event-stream")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("assess_complexity")).toBeInTheDocument();
      expect(screen.getByText("route_retrieval")).toBeInTheDocument();
      expect(screen.getByText("execute_retrieval")).toBeInTheDocument();
    });

    expect(screen.getByText("142ms")).toBeInTheDocument();
    expect(screen.getByText("88ms")).toBeInTheDocument();
  });

  it("expands and inspects sanitized payload on event click", async () => {
    vi.spyOn(apiClient.research, "getEvents").mockResolvedValue(mockEvents);

    render(<LiveEventTracer sessionId={sessionId} isRunning={false} initialEvents={mockEvents} />);

    // Click to expand event 101 payload
    const eventRow = screen.getByTestId("event-row-101");
    fireEvent.click(eventRow);

    await waitFor(() => {
      expect(screen.getByText(/Cross-domain entity join involving customers/i)).toBeInTheDocument();
    });
  });

  it("filters events by search query", async () => {
    render(<LiveEventTracer sessionId={sessionId} isRunning={false} initialEvents={mockEvents} />);

    expect(screen.getByText("assess_complexity")).toBeInTheDocument();
    expect(screen.getByText("route_retrieval")).toBeInTheDocument();

    const searchInput = screen.getByPlaceholderText(/filter events/i);
    fireEvent.change(searchInput, { target: { value: "cypher" } });

    await waitFor(() => {
      expect(screen.queryByText("assess_complexity")).not.toBeInTheDocument();
      expect(screen.getByText("execute_retrieval")).toBeInTheDocument();
    });
  });

  it("filters events when selectedNode prop is passed from timeline", async () => {
    render(
      <LiveEventTracer
        sessionId={sessionId}
        isRunning={false}
        initialEvents={mockEvents}
        selectedNode="route_retrieval"
      />
    );

    expect(screen.queryByText("assess_complexity")).not.toBeInTheDocument();
    expect(screen.getByText("route_retrieval")).toBeInTheDocument();
  });
});
