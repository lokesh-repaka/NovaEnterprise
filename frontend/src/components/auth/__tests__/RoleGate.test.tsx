import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { RoleGate } from "../RoleGate";
import * as AuthContextModule from "@/context/AuthContext";

describe("RoleGate Component", () => {
  const mockUseAuth = (role: "viewer" | "analyst" | "admin") => {
    const ROLE_LEVELS = { viewer: 1, analyst: 2, admin: 3 };
    const canPerformMap = {
      research: role === "analyst" || role === "admin",
      upload: role === "analyst" || role === "admin",
      cypher: role === "analyst" || role === "admin",
      delete: role === "admin",
      reindex: role === "admin",
      approve: role === "admin",
    };

    vi.spyOn(AuthContextModule, "useAuth").mockReturnValue({
      user: null,
      token: "test-token",
      role,
      demoUsers: [],
      isLoading: false,
      isAuthenticated: true,
      error: null,
      login: vi.fn(),
      switchDemoRole: vi.fn(),
      logout: vi.fn(),
      hasRole: (requiredRole) => ROLE_LEVELS[role] >= ROLE_LEVELS[requiredRole],
      canPerform: (action) => Boolean(canPerformMap[action]),
      refreshProfile: vi.fn(),
    });
  };

  it("renders children when user role meets requiredRole", () => {
    mockUseAuth("analyst");

    render(
      <RoleGate requiredRole="analyst">
        <div data-testid="protected-content">Protected Content</div>
      </RoleGate>
    );

    expect(screen.getByTestId("protected-content")).toBeInTheDocument();
  });

  it("renders children when user role exceeds requiredRole", () => {
    mockUseAuth("admin");

    render(
      <RoleGate requiredRole="analyst">
        <div data-testid="protected-content">Protected Content</div>
      </RoleGate>
    );

    expect(screen.getByTestId("protected-content")).toBeInTheDocument();
  });

  it("renders null when user role is below requiredRole and no fallback provided", () => {
    mockUseAuth("viewer");

    render(
      <RoleGate requiredRole="analyst">
        <div data-testid="protected-content">Protected Content</div>
      </RoleGate>
    );

    expect(screen.queryByTestId("protected-content")).not.toBeInTheDocument();
  });

  it("renders custom fallback when user lacks required role", () => {
    mockUseAuth("viewer");

    render(
      <RoleGate
        requiredRole="admin"
        fallback={<div data-testid="access-denied">Admin Required</div>}
      >
        <div data-testid="protected-content">Admin Only</div>
      </RoleGate>
    );

    expect(screen.queryByTestId("protected-content")).not.toBeInTheDocument();
    expect(screen.getByTestId("access-denied")).toBeInTheDocument();
  });

  it("renders disabled wrapper when showDisabled is true", () => {
    mockUseAuth("viewer");

    render(
      <RoleGate requiredRole="analyst" showDisabled>
        <button data-testid="action-btn">Start Research</button>
      </RoleGate>
    );

    const btn = screen.getByTestId("action-btn");
    expect(btn).toBeInTheDocument();
    const wrapper = btn.closest("[data-testid='role-disabled-wrapper']");
    expect(wrapper).toBeInTheDocument();
    expect(wrapper).toHaveClass("opacity-50");
    expect(wrapper).toHaveClass("cursor-not-allowed");
  });

  it("checks granular action permissions correctly", () => {
    mockUseAuth("analyst");

    // Analyst can perform research
    const { rerender } = render(
      <RoleGate action="research">
        <span data-testid="research-btn">Research</span>
      </RoleGate>
    );
    expect(screen.getByTestId("research-btn")).toBeInTheDocument();

    // Analyst cannot perform delete (admin only)
    rerender(
      <RoleGate action="delete">
        <span data-testid="delete-btn">Delete</span>
      </RoleGate>
    );
    expect(screen.queryByTestId("delete-btn")).not.toBeInTheDocument();
  });
});
