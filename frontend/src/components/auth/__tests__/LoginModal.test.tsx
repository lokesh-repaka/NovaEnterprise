import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { LoginModal } from "../LoginModal";
import * as AuthContextModule from "@/context/AuthContext";
import type { DemoUser } from "@/types/api";

describe("LoginModal Component", () => {
  const mockDemoUsers: DemoUser[] = [
    {
      id: "usr-admin-01",
      username: "admin",
      email: "admin@novaenterprise.io",
      role: "admin",
      name: "Alex Vance (Admin)",
      description: "Full access: approval workflow, reindex, delete",
    },
    {
      id: "usr-analyst-01",
      username: "analyst",
      email: "analyst@novaenterprise.io",
      role: "analyst",
      name: "Morgan Reed (Analyst)",
      description: "Research execution, document upload, Cypher explorer",
    },
    {
      id: "usr-viewer-01",
      username: "viewer",
      email: "viewer@novaenterprise.io",
      role: "viewer",
      name: "Taylor Swift (Viewer)",
      description: "Read-only access to dashboards, browse entities, citations",
    },
  ];

  const mockSwitchDemoRole = vi.fn();
  const mockLogin = vi.fn();
  const mockOnClose = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();

    vi.spyOn(AuthContextModule, "useAuth").mockReturnValue({
      user: null,
      token: null,
      role: "analyst",
      demoUsers: mockDemoUsers,
      isLoading: false,
      isAuthenticated: false,
      error: null,
      login: mockLogin,
      switchDemoRole: mockSwitchDemoRole,
      logout: vi.fn(),
      hasRole: vi.fn().mockReturnValue(true),
      canPerform: vi.fn().mockReturnValue(true),
      refreshProfile: vi.fn(),
    });
  });

  it("does not render when isOpen is false", () => {
    render(<LoginModal isOpen={false} onClose={mockOnClose} />);
    expect(screen.queryByTestId("login-modal")).not.toBeInTheDocument();
  });

  it("renders demo personas when open", () => {
    render(<LoginModal isOpen={true} onClose={mockOnClose} />);
    expect(screen.getByTestId("login-modal")).toBeInTheDocument();
    expect(screen.getByText("Alex Vance (Admin)")).toBeInTheDocument();
    expect(screen.getByText("Morgan Reed (Analyst)")).toBeInTheDocument();
    expect(screen.getByText("Taylor Swift (Viewer)")).toBeInTheDocument();
  });

  it("calls switchDemoRole and onClose when switching demo persona", async () => {
    mockSwitchDemoRole.mockResolvedValueOnce(undefined);

    render(<LoginModal isOpen={true} onClose={mockOnClose} />);

    const switchBtn = screen.getByTestId("btn-select-demo-admin");
    fireEvent.click(switchBtn);

    await waitFor(() => {
      expect(mockSwitchDemoRole).toHaveBeenCalledWith("admin");
      expect(mockOnClose).toHaveBeenCalled();
    });
  });

  it("switches to credentials tab and submits login form", async () => {
    mockLogin.mockResolvedValueOnce(undefined);

    render(<LoginModal isOpen={true} onClose={mockOnClose} />);

    // Switch tab
    fireEvent.click(screen.getByTestId("tab-credentials"));
    expect(screen.getByLabelText("Username or Work Email")).toBeInTheDocument();

    // Fill inputs
    fireEvent.change(screen.getByTestId("input-username"), {
      target: { value: "analyst@novaenterprise.io" },
    });
    fireEvent.change(screen.getByTestId("input-password"), {
      target: { value: "demo_password" },
    });

    fireEvent.click(screen.getByTestId("btn-submit-login"));

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith({
        username_or_email: "analyst@novaenterprise.io",
        password: "demo_password",
      });
      expect(mockOnClose).toHaveBeenCalled();
    });
  });

  it("displays error alert when login fails", async () => {
    mockLogin.mockRejectedValueOnce(new Error("Invalid username or password"));

    render(<LoginModal isOpen={true} onClose={mockOnClose} />);

    fireEvent.click(screen.getByTestId("tab-credentials"));

    fireEvent.change(screen.getByTestId("input-username"), {
      target: { value: "bad@novaenterprise.io" },
    });
    fireEvent.change(screen.getByTestId("input-password"), {
      target: { value: "wrongpass" },
    });

    fireEvent.click(screen.getByTestId("btn-submit-login"));

    await waitFor(() => {
      expect(screen.getByTestId("login-error-alert")).toBeInTheDocument();
      expect(screen.getByText("Invalid username or password")).toBeInTheDocument();
    });
  });

  it("calls onClose when close button is clicked", () => {
    render(<LoginModal isOpen={true} onClose={mockOnClose} />);
    fireEvent.click(screen.getByLabelText("Close dialog"));
    expect(mockOnClose).toHaveBeenCalled();
  });
});
