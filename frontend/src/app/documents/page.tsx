"use client";

import React, { useState, useEffect, useCallback, useMemo } from "react";
import {
  FileText,
  Layers,
  ShieldAlert,
  Clock,
  CheckCircle2,
  AlertTriangle,
  UploadCloud,
  ChevronRight,
  ShieldCheck,
} from "lucide-react";
import { apiClient } from "@/api/client";
import { useAuth } from "@/context/AuthContext";
import { UploadDropzone } from "@/components/documents/UploadDropzone";
import { DocumentList } from "@/components/documents/DocumentList";
import { DocumentInspectorModal } from "@/components/documents/DocumentInspectorModal";
import { ApprovalList } from "@/components/documents/ApprovalList";
import { ApprovalModal } from "@/components/documents/ApprovalModal";
import type {
  DocumentResponse,
  DocumentUploadResponse,
  DocumentDeleteResponse,
  DocumentDeletePendingResponse,
  ApprovalRequestResponse,
  ApprovalDecisionResponse,
} from "@/types/api";

type ActiveTab = "documents" | "approvals";

export default function DocumentsPage() {
  const { role } = useAuth();

  const [activeTab, setActiveTab] = useState<ActiveTab>("documents");
  const [documents, setDocuments] = useState<DocumentResponse[]>([]);
  const [approvals, setApprovals] = useState<ApprovalRequestResponse[]>([]);
  const [isLoadingDocs, setIsLoadingDocs] = useState(true);
  const [isLoadingApprovals, setIsLoadingApprovals] = useState(true);

  // Inspector & Modal States
  const [inspectingDocId, setInspectingDocId] = useState<string | null>(null);
  const [selectedApproval, setSelectedApproval] =
    useState<ApprovalRequestResponse | null>(null);
  const [isApprovalModalOpen, setIsApprovalModalOpen] = useState(false);

  // Notifications / Feedback
  const [alertNotice, setAlertNotice] = useState<{
    type: "info" | "warning" | "success";
    title: string;
    message: string;
    requestId?: string;
  } | null>(null);

  // Fetch Documents
  const loadDocuments = useCallback(async () => {
    setIsLoadingDocs(true);
    try {
      const data = await apiClient.documents.list({ limit: 100 });
      setDocuments(data);
    } catch {
      // In tests or offline, handle gracefully
    } finally {
      setIsLoadingDocs(false);
    }
  }, []);

  // Fetch Approvals
  const loadApprovals = useCallback(async () => {
    setIsLoadingApprovals(true);
    try {
      const data = await apiClient.approvals.list({ limit: 100 });
      setApprovals(data);
    } catch {
      // In tests or offline, handle gracefully
    } finally {
      setIsLoadingApprovals(false);
    }
  }, []);

  useEffect(() => {
    loadDocuments();
    loadApprovals();
  }, [loadDocuments, loadApprovals]);

  // Document upload handler
  const handleUploadSuccess = useCallback(
    (newDoc: DocumentUploadResponse) => {
      loadDocuments();
      setAlertNotice({
        type: newDoc.flagged_injection ? "warning" : "success",
        title: newDoc.flagged_injection
          ? "Document Ingested with Prompt Injection Quarantine (N8)"
          : "Document Ingested Successfully",
        message: `Indexed "${newDoc.filename}" into ${newDoc.chunk_count} semantic segments.`,
      });
    },
    [loadDocuments]
  );

  // Document delete response handler (Analyst vs Admin - F17)
  const handleDeleteSuccess = useCallback(
    (docId: string, result: DocumentDeleteResponse) => {
      if (result.status === "pending_approval") {
        const pending = result as DocumentDeletePendingResponse;
        setAlertNotice({
          type: "warning",
          title: "Deletion Request Queued for Approval (F17)",
          message: pending.message,
          requestId: pending.approval_request_id,
        });
        loadApprovals();
      } else {
        setAlertNotice({
          type: "success",
          title: "Document Successfully Deleted",
          message:
            result.message ||
            `Document '${docId}' has been pruned from vector and graph indices.`,
        });
        loadDocuments();
      }
    },
    [loadDocuments, loadApprovals]
  );

  // Approval decision handler (Admin - F17)
  const handleApprovalDecisionSuccess = useCallback(
    (decision: ApprovalDecisionResponse) => {
      setAlertNotice({
        type: decision.status === "approved" ? "success" : "info",
        title: `Approval Request ${decision.status.toUpperCase()}`,
        message: `Decision recorded by ${decision.decided_by}. Target document updated.`,
      });
      loadApprovals();
      loadDocuments();
    },
    [loadApprovals, loadDocuments]
  );

  // Computed KPIs
  const totalChunks = useMemo(
    () => documents.reduce((acc, doc) => acc + (doc.chunk_count || 0), 0),
    [documents]
  );
  const flaggedCount = useMemo(
    () => documents.filter((doc) => doc.flagged_injection).length,
    [documents]
  );
  const pendingApprovalsCount = useMemo(
    () => approvals.filter((app) => app.status === "pending").length,
    [approvals]
  );

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="space-y-1.5">
          <h2 className="text-2xl font-bold text-white tracking-tight">
            Document Corpus & Approvals
          </h2>
          <p className="text-xs text-gray-400 max-w-2xl leading-relaxed">
            Enterprise document library with automated prompt-injection quarantine
            (N8), 5MB size allowlist (N7), and 2-person Human-in-the-Loop approval
            gates on destructive document deletion (F17).
          </p>
        </div>
      </div>

      {/* KPI Stats Bar */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="rounded-xl border border-gray-800 bg-gray-900/60 p-4">
          <div className="flex items-center justify-between text-gray-400 text-xs">
            <span>Indexed Documents</span>
            <FileText className="w-4 h-4 text-blue-400" />
          </div>
          <div className="text-2xl font-bold text-white mt-1">
            {documents.length}
          </div>
          <div className="text-[11px] text-gray-500 mt-1">
            Across Markdown, text & PDF
          </div>
        </div>

        <div className="rounded-xl border border-gray-800 bg-gray-900/60 p-4">
          <div className="flex items-center justify-between text-gray-400 text-xs">
            <span>Semantic Chunks</span>
            <Layers className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold text-white mt-1">
            {totalChunks}
          </div>
          <div className="text-[11px] text-gray-500 mt-1">
            Embedded into vector space
          </div>
        </div>

        <div className="rounded-xl border border-gray-800 bg-gray-900/60 p-4">
          <div className="flex items-center justify-between text-gray-400 text-xs">
            <span>Injection Shield (N8)</span>
            <ShieldAlert className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-2xl font-bold text-amber-400 mt-1">
            {flaggedCount}
          </div>
          <div className="text-[11px] text-amber-500/80 mt-1">
            {flaggedCount > 0 ? "Quarantined payloads" : "Zero injections detected"}
          </div>
        </div>

        <div className="rounded-xl border border-gray-800 bg-gray-900/60 p-4">
          <div className="flex items-center justify-between text-gray-400 text-xs">
            <span>Pending Approvals (F17)</span>
            <Clock className="w-4 h-4 text-rose-400" />
          </div>
          <div className="text-2xl font-bold text-rose-400 mt-1">
            {pendingApprovalsCount}
          </div>
          <div className="text-[11px] text-gray-500 mt-1">
            Awaiting administrator sign-off
          </div>
        </div>
      </div>

      {/* Global Alert Notification Banner */}
      {alertNotice && (
        <div
          className={`rounded-xl border p-4 text-xs flex items-start justify-between space-x-3 transition-all ${
            alertNotice.type === "warning"
              ? "border-amber-500/40 bg-amber-500/10 text-amber-200"
              : alertNotice.type === "success"
              ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-200"
              : "border-blue-500/40 bg-blue-500/10 text-blue-200"
          }`}
        >
          <div className="flex items-start space-x-2.5">
            {alertNotice.type === "warning" ? (
              <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
            ) : alertNotice.type === "success" ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
            ) : (
              <FileText className="w-4 h-4 text-blue-400 shrink-0 mt-0.5" />
            )}
            <div className="space-y-0.5">
              <span className="font-semibold block">{alertNotice.title}</span>
              <p className="opacity-90 leading-relaxed">{alertNotice.message}</p>
              {alertNotice.requestId && (
                <div className="pt-1 flex items-center space-x-2">
                  <span className="font-mono text-[11px] text-amber-300">
                    Approval Request: {alertNotice.requestId}
                  </span>
                  <button
                    onClick={() => setActiveTab("approvals")}
                    className="underline text-[11px] text-amber-400 hover:text-white font-medium"
                  >
                    View in Approvals Queue &rarr;
                  </button>
                </div>
              )}
            </div>
          </div>
          <button
            onClick={() => setAlertNotice(null)}
            className="text-gray-400 hover:text-white text-xs px-2 py-0.5 rounded"
          >
            &times;
          </button>
        </div>
      )}

      {/* Main Tab Navigation */}
      <div className="flex items-center space-x-2 border-b border-gray-800 pb-px">
        <button
          role="tab"
          aria-selected={activeTab === "documents"}
          onClick={() => setActiveTab("documents")}
          className={`flex items-center space-x-2 px-4 py-2.5 text-xs font-semibold border-b-2 transition-colors ${
            activeTab === "documents"
              ? "border-blue-500 text-white"
              : "border-transparent text-gray-400 hover:text-gray-200"
          }`}
        >
          <FileText className="w-4 h-4" />
          <span>Document Library & Ingestion</span>
          <span className="ml-1.5 px-2 py-0.5 rounded-full text-[10px] bg-gray-800 text-gray-300">
            {documents.length}
          </span>
        </button>

        <button
          role="tab"
          aria-selected={activeTab === "approvals"}
          onClick={() => setActiveTab("approvals")}
          className={`flex items-center space-x-2 px-4 py-2.5 text-xs font-semibold border-b-2 transition-colors ${
            activeTab === "approvals"
              ? "border-amber-500 text-white"
              : "border-transparent text-gray-400 hover:text-gray-200"
          }`}
        >
          <ShieldAlert className="w-4 h-4" />
          <span>Governance & Approvals</span>
          {pendingApprovalsCount > 0 && (
            <span className="ml-1.5 px-2 py-0.5 rounded-full text-[10px] bg-amber-500/20 text-amber-400 font-bold border border-amber-500/30">
              {pendingApprovalsCount}
            </span>
          )}
        </button>
      </div>

      {/* Tab Panels */}
      {activeTab === "documents" ? (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Document Ingestion Dropzone */}
          <div className="lg:col-span-1 space-y-4">
            <div className="rounded-xl border border-gray-800 bg-gray-900/60 p-5 space-y-3">
              <div className="flex items-center space-x-2">
                <UploadCloud className="w-4 h-4 text-blue-400" />
                <h3 className="text-xs font-mono font-semibold uppercase tracking-wider text-gray-300">
                  Document Ingestion (F13, N7)
                </h3>
              </div>
              <p className="text-[11px] text-gray-400 leading-relaxed">
                Ingest internal Markdown runbooks, postmortems, ADRs, and PDF
                policies. Automatic parsing, chunking, and named entity
                extraction into vector and knowledge graph indices.
              </p>
              <UploadDropzone onUploadSuccess={handleUploadSuccess} />
            </div>
          </div>

          {/* Document Library Table */}
          <div className="lg:col-span-2 space-y-4">
            <DocumentList
              documents={documents}
              isLoading={isLoadingDocs}
              onInspect={(id) => setInspectingDocId(id)}
              onDeleteSuccess={handleDeleteSuccess}
            />
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="rounded-xl border border-gray-800 bg-gray-900/40 p-4 flex items-center justify-between text-xs text-gray-400">
            <div className="flex items-center space-x-2">
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
              <span>
                Administrative Approval Gate (F17): Destructive deletions by
                analysts are queued for explicit 2-person admin review.
              </span>
            </div>
            <span className="font-mono text-[11px] text-gray-500">
              Active Persona: <strong className="text-gray-200 capitalize">{role}</strong>
            </span>
          </div>

          <ApprovalList
            approvals={approvals}
            isLoading={isLoadingApprovals}
            onReviewApproval={(req) => {
              setSelectedApproval(req);
              setIsApprovalModalOpen(true);
            }}
          />
        </div>
      )}

      {/* Document Inspector Modal */}
      <DocumentInspectorModal
        isOpen={Boolean(inspectingDocId)}
        documentId={inspectingDocId}
        onClose={() => setInspectingDocId(null)}
      />

      {/* Approval Decision Modal */}
      <ApprovalModal
        isOpen={isApprovalModalOpen}
        approval={selectedApproval}
        onClose={() => {
          setIsApprovalModalOpen(false);
          setSelectedApproval(null);
        }}
        onDecisionSuccess={handleApprovalDecisionSuccess}
      />
    </div>
  );
}
