import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { GraphCanvas } from "../GraphCanvas";
import type { GraphNode, GraphEdge } from "@/types/api";

describe("GraphCanvas Component", () => {
  const mockNodes: GraphNode[] = [
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
  ];

  const mockEdges: GraphEdge[] = [
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
  ];

  it("renders graph canvas container, nodes, and edges", () => {
    render(<GraphCanvas nodes={mockNodes} edges={mockEdges} />);

    expect(screen.getByTestId("graph-canvas")).toBeInTheDocument();
    expect(screen.getByText("Payments API")).toBeInTheDocument();
    expect(screen.getByText("INC-2031")).toBeInTheDocument();
    expect(screen.getByText("Acme Corp")).toBeInTheDocument();
  });

  it("triggers onSelectNode when a node is clicked", () => {
    const onSelectNode = vi.fn();
    render(
      <GraphCanvas
        nodes={mockNodes}
        edges={mockEdges}
        onSelectNode={onSelectNode}
      />
    );

    fireEvent.click(screen.getByText("Payments API"));
    expect(onSelectNode).toHaveBeenCalledWith(
      expect.objectContaining({ id: "srv-payments" })
    );
  });

  it("filters visible nodes by entity label filter", () => {
    render(<GraphCanvas nodes={mockNodes} edges={mockEdges} />);

    // Click filter for Customer
    const customerFilterBtn = screen.getByRole("button", { name: /^Customer/i });
    fireEvent.click(customerFilterBtn);

    expect(screen.getByText("Acme Corp")).toBeInTheDocument();
    expect(screen.queryByText("Payments API")).not.toBeInTheDocument();
  });

  it("filters visible nodes by search query", () => {
    render(<GraphCanvas nodes={mockNodes} edges={mockEdges} />);

    const searchInput = screen.getByPlaceholderText(/search nodes/i);
    fireEvent.change(searchInput, { target: { value: "INC-2031" } });

    expect(screen.getByText("INC-2031")).toBeInTheDocument();
    expect(screen.queryByText("Acme Corp")).not.toBeInTheDocument();
  });

  it("provides zoom and reset controls", () => {
    render(<GraphCanvas nodes={mockNodes} edges={mockEdges} />);

    expect(screen.getByTitle(/zoom in/i)).toBeInTheDocument();
    expect(screen.getByTitle(/zoom out/i)).toBeInTheDocument();
    expect(screen.getByTitle(/reset view/i)).toBeInTheDocument();
  });
});
