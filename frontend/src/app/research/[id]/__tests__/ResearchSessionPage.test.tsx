import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import ResearchSessionPage from "../page";
import { apiClient } from "@/api/client";
import type { ResearchSessionResponse } from "@/types/api";

describe("ResearchSessionPage Component", () => {
  const sessionId = "f47ac10b-58cc-4372-a567-0e02b2c3d479";

  const mockRunningSession: ResearchSessionResponse = {
    session_id: sessionId,
    status: "running",
    question: "Which customers were impacted by the Payments API outage?",
    complexity: "complex",
    strategies_used: ["graph", "vector"],
    corrective_rounds: 0,
    verification_ratio: 0.0,
    answer: null,
    citations: [],
    evidence: [],
    sub_questions: [
      {
        id: "sq1",
        question: "Which customers were impacted?",
        strategy: "graph",
        status: "pending",
      },
    ],
    execution_time_seconds: 1.2,
    error_message: null,
    created_at: "2026-11-27T12:00:00Z",
    updated_at: "2026-11-27T12:00:01Z",
  };

  const mockCompletedSession: ResearchSessionResponse = {
    session_id: sessionId,
    status: "completed",
    question: "Which customers were impacted by the Payments API outage?",
    complexity: "complex",
    strategies_used: ["graph", "sql", "vector"],
    corrective_rounds: 0,
    verification_ratio: 1.0,
    answer: "During Q2, three enterprise customers were impacted by the Payments API outage INC-2031 [1]: Acme Corp, TechFlow, and FinEdge. To prevent recurrence, ADR 012 [2] introduced worker queues.",
    citations: [
      {
        citation_id: 1,
        evidence_id: "evi_01",
        source_type: "graph",
        locator: "(Service:Payments API)<-[:AFFECTED]-(Incident:INC-2031)-[:IMPACTED]->(Customer:Acme Corp)",
        snippet: "Acme Corp impacted by INC-2031 on Payments API",
      },
      {
        citation_id: 2,
        evidence_id: "evi_02",
        source_type: "document",
        locator: "documents/adr-012-async-payment-callbacks.md#Section-2",
        snippet: "ADR 012 proposes decoupling payment callbacks using queues",
      },
    ],
    evidence: [
      {
        id: "evi_01",
        sub_question_id: "sq1",
        source_type: "graph",
        locator: "(Service:Payments API)<-[:AFFECTED]-(Incident:INC-2031)-[:IMPACTED]->(Customer:Acme Corp)",
        content: "Acme Corp was impacted by SEV1 outage INC-2031.",
        score: 1.0,
        metadata: { store: "neo4j" },
      },
    ],
    sub_questions: [
      {
        id: "sq1",
        question: "Which customers were impacted by Payments API outage?",
        strategy: "graph",
        status: "answered",
      },
      {
        id: "sq2",
        question: "What architectural decision was made following INC-2031?",
        strategy: "vector",
        status: "answered",
      },
    ],
    execution_time_seconds: 6.84,
    error_message: null,
    created_at: "2026-11-27T12:00:00Z",
    updated_at: "2026-11-27T12:00:07Z",
  };

  const mockFailedSession: ResearchSessionResponse = {
    session_id: sessionId,
    status: "failed",
    question: "Query causing unrecoverable error",
    complexity: null,
    strategies_used: [],
    corrective_rounds: 1,
    verification_ratio: 0.0,
    answer: null,
    citations: [],
    evidence: [],
    sub_questions: [],
    execution_time_seconds: 2.1,
    error_message: "Neo4j traversal timeout after 3 retries",
    created_at: "2026-11-27T12:00:00Z",
    updated_at: "2026-11-27T12:00:02Z",
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders session header and polls running session", async () => {
    vi.spyOn(apiClient.research, "get").mockResolvedValue(mockRunningSession);

    render(<ResearchSessionPage params={Promise.resolve({ id: sessionId })} />);

    expect(screen.getByText("Research Session Tracer")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("Which customers were impacted by the Payments API outage?")).toBeInTheDocument();
    });

    expect(screen.getByTestId("session-status-badge")).toHaveTextContent(/running/i);
    expect(screen.getByText(/Workflow active/i)).toBeInTheDocument();
  });

  it("renders synthesized research report with citations and sub-questions upon completion", async () => {
    vi.spyOn(apiClient.research, "get").mockResolvedValue(mockCompletedSession);

    render(<ResearchSessionPage params={Promise.resolve({ id: sessionId })} />);

    await waitFor(() => {
      expect(screen.getByText(/During Q2, three enterprise customers were impacted/i)).toBeInTheDocument();
    });

    expect(screen.getByTestId("session-status-badge")).toHaveTextContent(/completed/i);
    expect(screen.getByText("100% Verified")).toBeInTheDocument();
    expect(screen.getByText("6.84s")).toBeInTheDocument();

    // Check citations
    expect(screen.getByText("Acme Corp impacted by INC-2031 on Payments API")).toBeInTheDocument();
    expect(screen.getByText("ADR 012 proposes decoupling payment callbacks using queues")).toBeInTheDocument();

    // Check sub-questions
    expect(screen.getByText("Which customers were impacted by Payments API outage?")).toBeInTheDocument();
    expect(screen.getByText("What architectural decision was made following INC-2031?")).toBeInTheDocument();
    expect(screen.getByText("graph")).toBeInTheDocument();
    expect(screen.getByText("vector")).toBeInTheDocument();
  });

  it("renders error alert when session status is failed", async () => {
    vi.spyOn(apiClient.research, "get").mockResolvedValue(mockFailedSession);

    render(<ResearchSessionPage params={Promise.resolve({ id: sessionId })} />);

    await waitFor(() => {
      expect(screen.getByTestId("session-status-badge")).toHaveTextContent(/failed/i);
    });

    expect(screen.getByText(/Neo4j traversal timeout after 3 retries/i)).toBeInTheDocument();
  });

  it("renders 13-node timeline and switches to live telemetry stream tab", async () => {
    vi.spyOn(apiClient.research, "get").mockResolvedValue(mockCompletedSession);
    vi.spyOn(apiClient.research, "getEvents").mockResolvedValue([
      {
        event_id: 1,
        session_id: sessionId,
        node_name: "assess_complexity",
        event_type: "node_complete",
        payload: { complexity: "complex" },
        latency_ms: 120,
        timestamp: "2026-11-27T12:00:01Z",
      },
    ]);

    render(<ResearchSessionPage params={Promise.resolve({ id: sessionId })} />);

    // 13-node timeline and progress bar are immediately present
    expect(screen.getByTestId("node-timeline")).toBeInTheDocument();
    expect(screen.getByTestId("workflow-progress-bar")).toBeInTheDocument();

    // Click Live Telemetry Stream tab
    const eventTabBtn = screen.getByRole("button", { name: /Live Telemetry Stream/i });
    fireEvent.click(eventTabBtn);

    await waitFor(() => {
      expect(screen.getByTestId("live-event-stream")).toBeInTheDocument();
    });
  });
});
