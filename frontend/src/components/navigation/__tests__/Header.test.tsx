import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { Header } from "../Header";

// Mock next/navigation usePathname
vi.mock("next/navigation", () => ({
  usePathname: () => "/search",
}));

describe("Header Navigation Component", () => {
  it("renders route breadcrumb title matching pathname", () => {
    render(<Header currentRole="analyst" />);
    expect(screen.getByText("Intelligence Research")).toBeInTheDocument();
  });

  it("displays backend liveness status badge", () => {
    render(<Header currentRole="analyst" />);
    expect(screen.getByTestId("backend-status-pill")).toBeInTheDocument();
    expect(screen.getByText("API :8001 Ready")).toBeInTheDocument();
  });

  it("renders role selector and invokes callback on change", () => {
    const handleRoleChange = vi.fn();
    render(<Header currentRole="analyst" onRoleChange={handleRoleChange} />);

    const select = screen.getByTestId("role-selector");
    expect(select).toHaveValue("analyst");

    fireEvent.change(select, { target: { value: "admin" } });
    expect(handleRoleChange).toHaveBeenCalledWith("admin");
  });

  it("renders quick link to New Research", () => {
    render(<Header currentRole="analyst" />);
    const newResearchLink = screen.getByText("New Research").closest("a");
    expect(newResearchLink).toHaveAttribute("href", "/search");
  });
});
