import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import DecisionsBrowsePage from "../page";
import { apiClient } from "@/api/client";
import type { DecisionResponse } from "@/types/api";

describe("DecisionsBrowsePage Component", () => {
  const mockDecisions: DecisionResponse[] = [
    {
      id: "adr-012",
      title: "Asynchronous Payment Processing via Worker Queues and Circuit Breaker",
      status: "accepted",
      context: "Downstream vendor authentication callbacks caused connection pool exhaustion in incident INC-2031.",
      decision: "Introduce asynchronous payment processing via worker queues and an automated circuit breaker.",
      consequences: "Prevents synchronous blocking on payment gateways; increases eventual consistency latency by up to 200ms.",
      incident_id: "inc-2031",
      decided_at: "2026-05-18T10:00:00Z",
      created_at: "2026-05-18T10:00:00Z",
    },
    {
      id: "adr-009",
      title: "Shared Redis Cluster for Ephemeral Session Cache",
      status: "proposed",
      context: "Multi-region session validation creates Aurora PostgreSQL read pressure.",
      decision: "Deploy a global Redis replica cluster.",
      consequences: "Reduces database read IOPS by 65%.",
      incident_id: null,
      decided_at: null,
      created_at: "2026-04-12T09:30:00Z",
    },
    {
      id: "adr-004",
      title: "Monolithic Batch Billing Synchronizer",
      status: "superseded",
      context: "Original batch processing design from 2024.",
      decision: "Run cron job every 4 hours.",
      consequences: "Did not scale past 10,000 customers.",
      incident_id: null,
      decided_at: "2024-02-01T00:00:00Z",
      created_at: "2024-02-01T00:00:00Z",
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders page title and table columns", async () => {
    vi.spyOn(apiClient.decisions, "list").mockResolvedValue(mockDecisions);

    render(<DecisionsBrowsePage />);

    expect(screen.getByText("Architectural Decisions (ADRs)")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("Asynchronous Payment Processing via Worker Queues and Circuit Breaker")).toBeInTheDocument();
    });

    expect(screen.getByText("ADR ID")).toBeInTheDocument();
    expect(screen.getByText("Decision Title")).toBeInTheDocument();
    expect(screen.getByText("Status")).toBeInTheDocument();
    expect(screen.getByText("Incident Link")).toBeInTheDocument();
  });

  it("renders status badges correctly", async () => {
    vi.spyOn(apiClient.decisions, "list").mockResolvedValue(mockDecisions);

    render(<DecisionsBrowsePage />);

    await waitFor(() => {
      expect(screen.getByText("accepted")).toBeInTheDocument();
    });

    expect(screen.getByText("proposed")).toBeInTheDocument();
    expect(screen.getByText("superseded")).toBeInTheDocument();
  });

  it("filters decisions by search query", async () => {
    vi.spyOn(apiClient.decisions, "list").mockResolvedValue(mockDecisions);

    render(<DecisionsBrowsePage />);

    await waitFor(() => {
      expect(screen.getByText("Asynchronous Payment Processing via Worker Queues and Circuit Breaker")).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText(/search architectural decisions/i);
    fireEvent.change(searchInput, { target: { value: "Redis" } });

    expect(screen.getByText("Shared Redis Cluster for Ephemeral Session Cache")).toBeInTheDocument();
    expect(screen.queryByText("Asynchronous Payment Processing via Worker Queues and Circuit Breaker")).not.toBeInTheDocument();
  });

  it("filters decisions by status selector", async () => {
    vi.spyOn(apiClient.decisions, "list").mockResolvedValue(mockDecisions);

    render(<DecisionsBrowsePage />);

    await waitFor(() => {
      expect(screen.getByText("Asynchronous Payment Processing via Worker Queues and Circuit Breaker")).toBeInTheDocument();
    });

    const statusSelect = screen.getByTestId("status-filter-select");
    fireEvent.change(statusSelect, { target: { value: "accepted" } });

    expect(screen.getByText("Asynchronous Payment Processing via Worker Queues and Circuit Breaker")).toBeInTheDocument();
    expect(screen.queryByText("Shared Redis Cluster for Ephemeral Session Cache")).not.toBeInTheDocument();
  });

  it("opens ADR detail drawer on row click and displays context and consequences", async () => {
    vi.spyOn(apiClient.decisions, "list").mockResolvedValue(mockDecisions);

    render(<DecisionsBrowsePage />);

    await waitFor(() => {
      expect(screen.getByText("Asynchronous Payment Processing via Worker Queues and Circuit Breaker")).toBeInTheDocument();
    });

    const adrRow = screen.getByTestId("decision-row-adr-012");
    fireEvent.click(adrRow);

    await waitFor(() => {
      expect(screen.getByTestId("decision-detail-drawer")).toBeInTheDocument();
    });

    expect(screen.getByText(/Downstream vendor authentication callbacks caused connection pool exhaustion/i)).toBeInTheDocument();
    expect(screen.getByText(/Prevents synchronous blocking on payment gateways/i)).toBeInTheDocument();
  });
});
