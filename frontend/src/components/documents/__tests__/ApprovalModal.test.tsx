import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ApprovalModal } from "../ApprovalModal";
import * as AuthContextModule from "@/context/AuthContext";
import { apiClient } from "@/api/client";
import type { UserRole, ApprovalRequestResponse, ApprovalDecisionResponse } from "@/types/api";

describe("ApprovalModal Component", () => {
  const mockApproval: ApprovalRequestResponse = {
    id: "app-880e-001",
    resource_type: "document",
    resource_id: "doc-550e-001",
    action: "delete",
    requester_id: "usr-analyst-01",
    status: "pending",
    decided_by: null,
    created_at: "2026-11-28T11:00:00Z",
  };

  const mockApprovedDecision: ApprovalDecisionResponse = {
    id: "app-880e-001",
    status: "approved",
    decided_by: "admin",
    decided_at: "2026-11-28T11:30:00Z",
    execution_result: {
      deleted_document_id: "doc-550e-001",
      pruned_chunks: 8,
    },
  };

  const mockRejectedDecision: ApprovalDecisionResponse = {
    id: "app-880e-001",
    status: "rejected",
    decided_by: "admin",
    decided_at: "2026-11-28T11:35:00Z",
    execution_result: {
      reason: "Document is required for active compliance audit.",
    },
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
        if (action === "upload" || action === "research" || action === "cypher") {
          return role === "analyst" || role === "admin";
        }
        if (action === "delete" || action === "approve" || action === "reindex") {
          return role === "admin";
        }
        return true;
      },
    });
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders pending approval request details", () => {
    mockUseAuth("admin");
    render(
      <ApprovalModal
        isOpen={true}
        approval={mockApproval}
        onClose={vi.fn()}
        onDecisionSuccess={vi.fn()}
      />
    );

    expect(screen.getByText(/Administrative Approval Gate/i)).toBeInTheDocument();
    expect(screen.getByText(/app-880e-001/i)).toBeInTheDocument();
    expect(screen.getByText(/doc-550e-001/i)).toBeInTheDocument();
    expect(screen.getByText(/usr-analyst-01/i)).toBeInTheDocument();
  });

  it("allows admin to approve request with reason", async () => {
    mockUseAuth("admin");
    vi.spyOn(apiClient.approvals, "decide").mockResolvedValue(mockApprovedDecision);
    const onDecisionSuccess = vi.fn();
    const onClose = vi.fn();

    render(
      <ApprovalModal
        isOpen={true}
        approval={mockApproval}
        onClose={onClose}
        onDecisionSuccess={onDecisionSuccess}
      />
    );

    const reasonInput = screen.getByTestId("approval-reason-input");
    fireEvent.change(reasonInput, {
      target: { value: "Approved removal of obsolete postmortem." },
    });

    const approveBtn = screen.getByTestId("approve-decision-btn");
    fireEvent.click(approveBtn);

    await waitFor(() => {
      expect(apiClient.approvals.decide).toHaveBeenCalledWith("app-880e-001", {
        decision: "approved",
        reason: "Approved removal of obsolete postmortem.",
      });
      expect(onDecisionSuccess).toHaveBeenCalledWith(mockApprovedDecision);
    });
  });

  it("allows admin to reject request with reason", async () => {
    mockUseAuth("admin");
    vi.spyOn(apiClient.approvals, "decide").mockResolvedValue(mockRejectedDecision);
    const onDecisionSuccess = vi.fn();

    render(
      <ApprovalModal
        isOpen={true}
        approval={mockApproval}
        onClose={vi.fn()}
        onDecisionSuccess={onDecisionSuccess}
      />
    );

    const reasonInput = screen.getByTestId("approval-reason-input");
    fireEvent.change(reasonInput, {
      target: { value: "Rejected: document still referenced in active tickets." },
    });

    const rejectBtn = screen.getByTestId("reject-decision-btn");
    fireEvent.click(rejectBtn);

    await waitFor(() => {
      expect(apiClient.approvals.decide).toHaveBeenCalledWith("app-880e-001", {
        decision: "rejected",
        reason: "Rejected: document still referenced in active tickets.",
      });
      expect(onDecisionSuccess).toHaveBeenCalledWith(mockRejectedDecision);
    });
  });

  it("disables decision buttons and warns when caller is non-admin (F17)", () => {
    mockUseAuth("analyst");
    render(
      <ApprovalModal
        isOpen={true}
        approval={mockApproval}
        onClose={vi.fn()}
        onDecisionSuccess={vi.fn()}
      />
    );

    expect(
      screen.getByText(/Admin role required to resolve approval gates/i)
    ).toBeInTheDocument();

    const approveBtn = screen.getByTestId("approve-decision-btn");
    const rejectBtn = screen.getByTestId("reject-decision-btn");
    expect(approveBtn).toBeDisabled();
    expect(rejectBtn).toBeDisabled();
  });
});
