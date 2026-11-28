import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import IncidentsBrowsePage from "../page";
import { apiClient } from "@/api/client";
import type { IncidentResponse } from "@/types/api";

describe("IncidentsBrowsePage Component", () => {
  const mockIncidents: IncidentResponse[] = [
    {
      id: "inc-2031",
      title: "Payments API Outage during Q2 Peak Processing",
      severity: "SEV1",
      status: "resolved",
      root_cause: "Connection pool exhaustion due to slow downstream vendor auth callback",
      impacted_service_id: "svc-payments-api",
      occurred_at: "2026-05-14T14:22:00Z",
      resolved_at: "2026-05-14T16:45:00Z",
      created_at: "2026-05-14T14:25:00Z",
    },
    {
      id: "inc-1092",
      title: "Order Ingestion Latency Spike",
      severity: "SEV2",
      status: "investigating",
      root_cause: null,
      impacted_service_id: "svc-orders-engine",
      occurred_at: "2026-06-01T09:15:00Z",
      resolved_at: null,
      created_at: "2026-06-01T09:20:00Z",
    },
    {
      id: "inc-0544",
      title: "Catalog Cache Invalidation Stalling",
      severity: "SEV3",
      status: "mitigated",
      root_cause: "Redis memory fragmentation",
      impacted_service_id: "svc-catalog-cache",
      occurred_at: "2026-06-12T11:00:00Z",
      resolved_at: "2026-06-12T11:45:00Z",
      created_at: "2026-06-12T11:05:00Z",
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders page title and table columns", async () => {
    vi.spyOn(apiClient.incidents, "list").mockResolvedValue(mockIncidents);

    render(<IncidentsBrowsePage />);

    expect(screen.getByText("Incident Records")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("Payments API Outage during Q2 Peak Processing")).toBeInTheDocument();
    });

    expect(screen.getByText("Incident ID")).toBeInTheDocument();
    expect(screen.getByText("Title & Summary")).toBeInTheDocument();
    expect(screen.getByText("Severity")).toBeInTheDocument();
    expect(screen.getByText("Status")).toBeInTheDocument();
    expect(screen.getByText("Impacted Service")).toBeInTheDocument();
  });

  it("renders severity and status badges", async () => {
    vi.spyOn(apiClient.incidents, "list").mockResolvedValue(mockIncidents);

    render(<IncidentsBrowsePage />);

    await waitFor(() => {
      expect(screen.getAllByText("SEV1").length).toBeGreaterThan(0);
    });

    expect(screen.getAllByText("SEV2").length).toBeGreaterThan(0);
    expect(screen.getAllByText("SEV3").length).toBeGreaterThan(0);
    expect(screen.getAllByText("resolved").length).toBeGreaterThan(0);
    expect(screen.getAllByText("investigating").length).toBeGreaterThan(0);
  });

  it("filters incidents by search input", async () => {
    vi.spyOn(apiClient.incidents, "list").mockResolvedValue(mockIncidents);

    render(<IncidentsBrowsePage />);

    await waitFor(() => {
      expect(screen.getByText("Payments API Outage during Q2 Peak Processing")).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText(/search incidents/i);
    fireEvent.change(searchInput, { target: { value: "Latency Spike" } });

    expect(screen.getByText("Order Ingestion Latency Spike")).toBeInTheDocument();
    expect(screen.queryByText("Payments API Outage during Q2 Peak Processing")).not.toBeInTheDocument();
  });

  it("filters incidents by severity selector", async () => {
    vi.spyOn(apiClient.incidents, "list").mockResolvedValue(mockIncidents);

    render(<IncidentsBrowsePage />);

    await waitFor(() => {
      expect(screen.getByText("Payments API Outage during Q2 Peak Processing")).toBeInTheDocument();
    });

    const sevSelect = screen.getByTestId("severity-filter-select");
    fireEvent.change(sevSelect, { target: { value: "SEV1" } });

    expect(screen.getByText("Payments API Outage during Q2 Peak Processing")).toBeInTheDocument();
    expect(screen.queryByText("Order Ingestion Latency Spike")).not.toBeInTheDocument();
  });

  it("opens incident detail drawer on row click and displays root cause", async () => {
    vi.spyOn(apiClient.incidents, "list").mockResolvedValue(mockIncidents);

    render(<IncidentsBrowsePage />);

    await waitFor(() => {
      expect(screen.getByText("Payments API Outage during Q2 Peak Processing")).toBeInTheDocument();
    });

    const incidentRow = screen.getByTestId("incident-row-inc-2031");
    fireEvent.click(incidentRow);

    await waitFor(() => {
      expect(screen.getByTestId("incident-detail-drawer")).toBeInTheDocument();
    });

    const drawer = screen.getByTestId("incident-detail-drawer");
    expect(drawer).toHaveTextContent(/Connection pool exhaustion due to slow downstream vendor auth callback/i);
  });
});
