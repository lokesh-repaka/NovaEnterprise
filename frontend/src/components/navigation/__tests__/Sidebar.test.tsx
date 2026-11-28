import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { Sidebar } from "../Sidebar";

// Mock next/navigation usePathname
vi.mock("next/navigation", () => ({
  usePathname: () => "/search",
}));

describe("Sidebar Navigation Component", () => {
  it("renders brand title and intelligence console subtitle", () => {
    render(<Sidebar currentRole="analyst" />);
    expect(screen.getByText("NovaEnterprise")).toBeInTheDocument();
    expect(screen.getByText("Intelligence Console")).toBeInTheDocument();
  });

  it("renders all core navigation links", () => {
    render(<Sidebar currentRole="analyst" />);
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
    expect(screen.getByText("Research & Search")).toBeInTheDocument();
    expect(screen.getByText("Knowledge Graph")).toBeInTheDocument();
    expect(screen.getByText("Documents & Corpus")).toBeInTheDocument();
    expect(screen.getByText("Customers")).toBeInTheDocument();
    expect(screen.getByText("Incidents")).toBeInTheDocument();
    expect(screen.getByText("Decisions (ADRs)")).toBeInTheDocument();
  });

  it("indicates active link for current pathname", () => {
    render(<Sidebar currentRole="analyst" />);
    const activeLink = screen.getByText("Research & Search").closest("a");
    expect(activeLink).toHaveClass("text-blue-400");
  });

  it("displays current user role in the footer", () => {
    render(<Sidebar currentRole="admin" />);
    expect(screen.getByText("admin")).toBeInTheDocument();
  });

  it("toggles collapse state on button click", () => {
    render(<Sidebar currentRole="analyst" />);
    const toggleBtn = screen.getByLabelText("Collapse sidebar");
    fireEvent.click(toggleBtn);
    expect(screen.getByLabelText("Expand sidebar")).toBeInTheDocument();
  });
});
