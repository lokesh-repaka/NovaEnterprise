import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import DocumentsPage from "../page";
import * as AuthContextModule from "@/context/AuthContext";
import { apiClient } from "@/api/client";
import type {
  UserRole,
  DocumentResponse,
  DocumentDetailResponse,
  ApprovalRequestResponse,
  DocumentDeletePendingResponse,
  DocumentDeleteExecutedResponse,
} from "@/types/api";

describe("DocumentsPage Integration", () => {
  const mockDocuments: DocumentResponse[] = [
    {
      id: "doc-01",
      filename: "postmortem-inc-2031-payments-api-outage.md",
      content_hash: "hash01",
      chunk_count: 8,
      flagged_injection: false,
      status: "indexed",
      created_at: "2026-11-28T09:00:00Z",
    },
    {
      id: "doc-02",
      filename: "vendor-note-processor-update.md",
      content_hash: "hash02",
      chunk_count: 3,
      flagged_injection: true,
      status: "flagged",
      created_at: "2026-11-28T09:30:00Z",
    },
  ];

  const mockDocumentDetail: DocumentDetailResponse = {
    id: "doc-01",
    filename: "postmortem-inc-2031-payments-api-outage.md",
    content_hash: "hash01",
    chunk_count: 2,
    flagged_injection: false,
    status: "indexed",
    created_at: "2026-11-28T09:00:00Z",
    chunks: [
      {
        id: "chk-01",
        chunk_index: 0,
        text: "SEV1 incident postmortem for Payments API outage.",
        embedding_id: "emb-01",
      },
      {
        id: "chk-02",
        chunk_index: 1,
        text: "Root cause: stale Redis pool exhaustion.",
        embedding_id: "emb-02",
      },
    ],
  };

  const mockApprovals: ApprovalRequestResponse[] = [
    {
      id: "app-101",
      resource_type: "document",
      resource_id: "doc-01",
      action: "delete",
      requester_id: "usr-analyst-01",
      status: "pending",
      decided_by: null,
      created_at: "2026-11-28T10:00:00Z",
    },
  ];

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
    vi.spyOn(apiClient.documents, "list").mockResolvedValue(mockDocuments);
    vi.spyOn(apiClient.documents, "get").mockResolvedValue(mockDocumentDetail);
    vi.spyOn(apiClient.approvals, "list").mockResolvedValue(mockApprovals);
  });

  it("renders documents library and summary metrics", async () => {
    mockUseAuth("analyst");
    render(<DocumentsPage />);

    expect(screen.getByText(/Document Corpus & Approvals/i)).toBeInTheDocument();

    await waitFor(() => {
      expect(
        screen.getByText("postmortem-inc-2031-payments-api-outage.md")
      ).toBeInTheDocument();
      expect(
        screen.getByText("vendor-note-processor-update.md")
      ).toBeInTheDocument();
    });

    // Check injection quarantined label
    expect(screen.getByText(/Quarantined \(N8\)/i)).toBeInTheDocument();
  });

  it("queues approval when analyst requests document deletion (F17)", async () => {
    mockUseAuth("analyst");
    const mockPendingDelete: DocumentDeletePendingResponse = {
      status: "pending_approval",
      approval_request_id: "app-pending-99",
      message: "Deletion request queued for administrative approval",
    };
    vi.spyOn(apiClient.documents, "delete").mockResolvedValue(mockPendingDelete);

    render(<DocumentsPage />);

    await waitFor(() => {
      expect(
        screen.getByText("postmortem-inc-2031-payments-api-outage.md")
      ).toBeInTheDocument();
    });

    // Analyst sees "Request Delete"
    const deleteButtons = screen.getAllByTestId("delete-doc-btn");
    fireEvent.click(deleteButtons[0]);

    await waitFor(() => {
      expect(apiClient.documents.delete).toHaveBeenCalledWith("doc-01");
      expect(
        screen.getByText(/Deletion request queued for administrative approval/i)
      ).toBeInTheDocument();
      expect(screen.getByText(/app-pending-99/i)).toBeInTheDocument();
    });
  });

  it("executes immediate deletion when admin deletes document", async () => {
    mockUseAuth("admin");
    const mockExecutedDelete: DocumentDeleteExecutedResponse = {
      status: "deleted",
      deleted_document_id: "doc-01",
      pruned_chunks: 8,
      message: "Document successfully deleted",
    };
    vi.spyOn(apiClient.documents, "delete").mockResolvedValue(mockExecutedDelete);

    render(<DocumentsPage />);

    await waitFor(() => {
      expect(
        screen.getByText("postmortem-inc-2031-payments-api-outage.md")
      ).toBeInTheDocument();
    });

    const deleteButtons = screen.getAllByTestId("delete-doc-btn");
    fireEvent.click(deleteButtons[0]);

    await waitFor(() => {
      expect(apiClient.documents.delete).toHaveBeenCalledWith("doc-01");
      expect(
        screen.getAllByText(/Document successfully deleted/i).length
      ).toBeGreaterThanOrEqual(1);
    });
  });

  it("opens document inspector and displays semantic chunk breakdown", async () => {
    mockUseAuth("viewer");
    render(<DocumentsPage />);

    await waitFor(() => {
      expect(
        screen.getByText("postmortem-inc-2031-payments-api-outage.md")
      ).toBeInTheDocument();
    });

    const inspectButtons = screen.getAllByTestId("inspect-doc-btn");
    fireEvent.click(inspectButtons[0]);

    await waitFor(() => {
      expect(apiClient.documents.get).toHaveBeenCalledWith("doc-01");
      expect(screen.getByText(/Semantic Chunk Breakdown/i)).toBeInTheDocument();
      expect(
        screen.getByText(/SEV1 incident postmortem for Payments API outage\./i)
      ).toBeInTheDocument();
      expect(
        screen.getByText(/Root cause: stale Redis pool exhaustion\./i)
      ).toBeInTheDocument();
    });
  });

  it("switches to Governance & Approvals tab and renders pending requests", async () => {
    mockUseAuth("admin");
    render(<DocumentsPage />);

    const approvalsTab = screen.getByRole("tab", { name: /Governance & Approvals/i });
    fireEvent.click(approvalsTab);

    await waitFor(() => {
      expect(screen.getByText(/app-101/i)).toBeInTheDocument();
      expect(screen.getByText(/usr-analyst-01/i)).toBeInTheDocument();
    });
  });
});
