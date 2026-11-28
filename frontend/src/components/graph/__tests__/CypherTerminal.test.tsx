import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { CypherTerminal } from "../CypherTerminal";
import * as AuthContextModule from "@/context/AuthContext";
import { apiClient } from "@/api/client";
import type { UserRole, CypherQueryResponse } from "@/types/api";

describe("CypherTerminal Component", () => {
  const mockCypherResponse: CypherQueryResponse = {
    execution_time_ms: 18.5,
    results: [
      { "s.name": "Payments API", "i.incident_id": "INC-2031" },
    ],
    nodes: [
      { id: "srv-payments", label: "Service", properties: { name: "Payments API" } },
      { id: "inc-2031", label: "Incident", properties: { incident_id: "INC-2031" } },
    ],
    edges: [
      { id: "e1", source: "inc-2031", target: "srv-payments", type: "AFFECTED", properties: {} },
    ],
  };

  const mockUseAuth = (role: UserRole) => {
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
      canPerform: (action: string) => {
        if (action === "cypher" || action === "research" || action === "upload") {
          return role === "analyst" || role === "admin";
        }
        if (action === "admin" || action === "approve" || action === "delete") {
          return role === "admin";
        }
        return true;
      },
    });
  };

  beforeEach(() => {
    vi.clearAllMocks();
    mockUseAuth("analyst");
  });

  it("renders query editor and templates", () => {
    render(<CypherTerminal onResultsLoaded={vi.fn()} />);

    expect(screen.getByTestId("cypher-terminal")).toBeInTheDocument();
    expect(screen.getByRole("textbox")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Run Cypher/i })).toBeInTheDocument();
  });

  it("disables execution button for viewer role (Claude.md line 380)", () => {
    mockUseAuth("viewer");

    render(<CypherTerminal onResultsLoaded={vi.fn()} />);

    const runBtn = screen.getByRole("button", { name: /Run Cypher/i });
    expect(runBtn).toBeDisabled();
  });

  it("executes query and displays results with execution latency", async () => {
    vi.spyOn(apiClient.graph, "queryCypher").mockResolvedValue(mockCypherResponse);

    render(<CypherTerminal onResultsLoaded={vi.fn()} />);

    const runBtn = screen.getByRole("button", { name: /Run Cypher/i });
    fireEvent.click(runBtn);

    await waitFor(() => {
      expect(screen.getByText("Payments API")).toBeInTheDocument();
      expect(screen.getByText("INC-2031")).toBeInTheDocument();
    });

    expect(screen.getByText(/18.5ms/i)).toBeInTheDocument();
    expect(screen.getByText(/1 result/i)).toBeInTheDocument();
  });

  it("displays error message if Cypher query syntax is invalid", async () => {
    vi.spyOn(apiClient.graph, "queryCypher").mockRejectedValue(
      new Error("Invalid Cypher syntax: Unexpected token near 'WHERE'")
    );

    render(<CypherTerminal onResultsLoaded={vi.fn()} />);

    const runBtn = screen.getByRole("button", { name: /Run Cypher/i });
    fireEvent.click(runBtn);

    await waitFor(() => {
      expect(screen.getByText(/Invalid Cypher syntax/i)).toBeInTheDocument();
    });
  });
});
