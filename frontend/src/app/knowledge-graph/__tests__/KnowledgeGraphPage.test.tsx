import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import KnowledgeGraphPage from "../page";
import * as AuthContextModule from "@/context/AuthContext";
import { apiClient } from "@/api/client";
import type { UserRole, GraphDataResponse, GraphExpandResponse } from "@/types/api";

describe("KnowledgeGraphPage Component", () => {
  const mockGraphData: GraphDataResponse = {
    nodes: [
      {
        id: "srv-payments",
        label: "Service",
        properties: { name: "Payments API", tier: "critical" },
      },
      {
        id: "inc-2031",
        label: "Incident",
        properties: { incident_id: "INC-2031", severity: "SEV1" },
      },
      {
        id: "cust-acme",
        label: "Customer",
        properties: { name: "Acme Corp", sla_tier: "enterprise" },
      },
    ],
    edges: [
      {
        id: "e1",
        source: "inc-2031",
        target: "srv-payments",
        type: "AFFECTED",
        properties: {},
      },
      {
        id: "e2",
        source: "inc-2031",
        target: "cust-acme",
        type: "IMPACTED",
        properties: {},
      },
    ],
  };

  const mockExpandResponse: GraphExpandResponse = {
    nodes: [
      {
        id: "srv-payments",
        label: "Service",
        properties: { name: "Payments API", tier: "critical" },
      },
      {
        id: "team-payments",
        label: "Team",
        properties: { name: "Payments Platform Team" },
      },
    ],
    edges: [
      {
        id: "e3",
        source: "team-payments",
        target: "srv-payments",
        type: "OWNS",
        properties: {},
      },
    ],
  };

  const mockUseAuth = (role: UserRole = "analyst") => {
    vi.spyOn(AuthContextModule, "useAuth").mockReturnValue({
      user: {
        id: "usr-01",
        username: role,
        email: `${role}@novaenterprise.io`,
        role,
        is_active: true,
        created_at: null,
      },
      token: "mock-jwt",
      role,
      demoUsers: [],
      isLoading: false,
      isAuthenticated: true,
      error: null,
      login: vi.fn(),
      logout: vi.fn(),
      switchDemoRole: vi.fn(),
      refreshProfile: vi.fn(),
      hasRole: (requiredRole: UserRole) => {
        const hierarchy: Record<UserRole, number> = { viewer: 1, analyst: 2, admin: 3 };
        return hierarchy[role] >= hierarchy[requiredRole];
      },
      canPerform: () => true,
    });
  };

  beforeEach(() => {
    vi.clearAllMocks();
    mockUseAuth("analyst");
  });

  it("fetches and renders initial graph subgraph", async () => {
    vi.spyOn(apiClient.graph, "getGraph").mockResolvedValue(mockGraphData);

    render(<KnowledgeGraphPage />);

    expect(screen.getByText("Knowledge Graph Explorer")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("Payments API")).toBeInTheDocument();
      expect(screen.getByText("INC-2031")).toBeInTheDocument();
      expect(screen.getByText("Acme Corp")).toBeInTheDocument();
    });

    // Verify entity summary badges
    expect(screen.getByText("3 Nodes")).toBeInTheDocument();
    expect(screen.getByText("2 Edges")).toBeInTheDocument();
  });

  it("selects a node and displays inspector properties", async () => {
    vi.spyOn(apiClient.graph, "getGraph").mockResolvedValue(mockGraphData);

    render(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByText("Payments API")).toBeInTheDocument();
    });

    // Click on node to inspect
    fireEvent.click(screen.getByText("Payments API"));

    await waitFor(() => {
      expect(screen.getByTestId("node-inspector")).toBeInTheDocument();
      expect(screen.getByText("critical")).toBeInTheDocument();
    });
  });

  it("expands 1-hop neighborhood when expand action is triggered", async () => {
    vi.spyOn(apiClient.graph, "getGraph").mockResolvedValue(mockGraphData);
    vi.spyOn(apiClient.graph, "expand").mockResolvedValue(mockExpandResponse);

    render(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByText("Payments API")).toBeInTheDocument();
    });

    // Select Payments API
    fireEvent.click(screen.getByText("Payments API"));

    // Click Expand 1-Hop Neighbors button
    const expandBtn = await screen.findByRole("button", { name: /Expand Neighbors/i });
    fireEvent.click(expandBtn);

    await waitFor(() => {
      expect(screen.getAllByText("Payments Platform Team").length).toBeGreaterThanOrEqual(1);
    });
  });
});
