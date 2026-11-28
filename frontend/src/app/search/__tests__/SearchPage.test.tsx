import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import SearchPage from "../page";
import { apiClient } from "@/api/client";
import * as AuthContextModule from "@/context/AuthContext";
import type { ResearchCreateResponse, ResearchSessionSummary } from "@/types/api";

const mockPush = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
  }),
  useSearchParams: () => ({
    get: (param: string) => (param === "q" ? "" : null),
  }),
}));

describe("SearchPage Component", () => {
  const mockRecentSessions: ResearchSessionSummary[] = [
    {
      session_id: "sess-01",
      question: "Which customers were impacted by Payments API outage?",
      status: "completed",
      complexity: "complex",
      created_at: "2026-11-27T10:00:00Z",
      updated_at: "2026-11-27T10:00:08Z",
    },
    {
      session_id: "sess-02",
      question: "List all active tier-1 services",
      status: "running",
      complexity: "simple",
      created_at: "2026-11-27T11:00:00Z",
      updated_at: "2026-11-27T11:00:02Z",
    },
  ];

  const mockUseAuth = (role: "viewer" | "analyst" | "admin") => {
    vi.spyOn(AuthContextModule, "useAuth").mockReturnValue({
      user: { id: "usr-01", username: "analyst", email: "analyst@novaenterprise.io", role, is_active: true, created_at: "" },
      token: "mock-token",
      role,
      demoUsers: [],
      isLoading: false,
      isAuthenticated: true,
      error: null,
      login: vi.fn(),
      switchDemoRole: vi.fn(),
      logout: vi.fn(),
      hasRole: (req) => (role === "admin" ? true : role === req),
      canPerform: (act) => (act === "research" ? role !== "viewer" : true),
      refreshProfile: vi.fn(),
    });
  };

  beforeEach(() => {
    vi.clearAllMocks();
    mockUseAuth("analyst");
    vi.spyOn(apiClient.research, "list").mockResolvedValue(mockRecentSessions);
  });

  it("renders research input interface and title", async () => {
    render(<SearchPage />);

    expect(screen.getByText("Research Intelligence Interface")).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/enter an enterprise inquiry/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /launch research/i })).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("Which customers were impacted by Payments API outage?")).toBeInTheDocument();
    });
  });

  it("populates inquiry textarea when template is clicked", () => {
    render(<SearchPage />);

    const canonicalTemplateBtn = screen.getByTestId("template-btn-canonical");
    fireEvent.click(canonicalTemplateBtn);

    const textarea = screen.getByPlaceholderText(/enter an enterprise inquiry/i) as HTMLTextAreaElement;
    expect(textarea.value).toContain("Payments API");
  });

  it("launches research, receives 202 session id, and navigates to active session view", async () => {
    const mockCreated: ResearchCreateResponse = {
      session_id: "f47ac10b-58cc-4372-a567-0e02b2c3d479",
      status: "running",
      question: "Which customers were impacted by Payments API outage?",
      created_at: "2026-11-27T12:00:00Z",
    };

    vi.spyOn(apiClient.research, "create").mockResolvedValue(mockCreated);

    render(<SearchPage />);

    const textarea = screen.getByPlaceholderText(/enter an enterprise inquiry/i);
    fireEvent.change(textarea, {
      target: { value: "Which customers were impacted by Payments API outage?" },
    });

    const submitBtn = screen.getByRole("button", { name: /launch research/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(apiClient.research.create).toHaveBeenCalledWith({
        question: "Which customers were impacted by Payments API outage?",
        user_id: "usr-01",
      });
      expect(mockPush).toHaveBeenCalledWith("/research/f47ac10b-58cc-4372-a567-0e02b2c3d479");
    });
  });

  it("disables research submission for viewer role (Claude.md line 380)", () => {
    mockUseAuth("viewer");

    render(<SearchPage />);

    const submitBtn = screen.getByRole("button", { name: /launch research/i });
    expect(submitBtn).toBeDisabled();
    const disabledWrapper = submitBtn.closest("[data-testid='role-disabled-wrapper']");
    expect(disabledWrapper).toBeInTheDocument();
  });

  it("renders recent research sessions table with status indicators", async () => {
    render(<SearchPage />);

    await waitFor(() => {
      expect(screen.getByText("Which customers were impacted by Payments API outage?")).toBeInTheDocument();
    });

    expect(screen.getByText("List all active tier-1 services")).toBeInTheDocument();
    expect(screen.getByText("completed")).toBeInTheDocument();
    expect(screen.getByText("running")).toBeInTheDocument();
  });

  it("displays error message if research intake fails", async () => {
    vi.spyOn(apiClient.research, "create").mockRejectedValue(new Error("Graph store offline"));

    render(<SearchPage />);

    const textarea = screen.getByPlaceholderText(/enter an enterprise inquiry/i);
    fireEvent.change(textarea, { target: { value: "Fail this inquiry" } });

    fireEvent.click(screen.getByRole("button", { name: /launch research/i }));

    await waitFor(() => {
      expect(screen.getByText(/graph store offline/i)).toBeInTheDocument();
    });
  });
});
