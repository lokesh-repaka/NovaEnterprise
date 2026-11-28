"use client";

import React, { useState, useMemo } from "react";
import {
  FileText,
  Search,
  Eye,
  Trash2,
  ShieldAlert,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Clock,
  Layers,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { apiClient } from "@/api/client";
import type { DocumentResponse, DocumentDeleteResponse } from "@/types/api";

interface DocumentListProps {
  documents: DocumentResponse[];
  isLoading: boolean;
  onInspect: (docId: string) => void;
  onDeleteSuccess: (docId: string, result: DocumentDeleteResponse) => void;
}

export function DocumentList({
  documents,
  isLoading,
  onInspect,
  onDeleteSuccess,
}: DocumentListProps) {
  const { role, canPerform } = useAuth();
  const isAdmin = role === "admin";
  const isAnalyst = role === "analyst";
  const canDelete = isAdmin || isAnalyst; // Analyst requests approval, Admin deletes immediately (F17)

  const [searchQuery, setSearchQuery] = useState("");
  const [selectedStatus, setSelectedStatus] = useState<string>("All");
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const filteredDocuments = useMemo(() => {
    return documents.filter((doc) => {
      const matchesSearch =
        doc.filename.toLowerCase().includes(searchQuery.toLowerCase()) ||
        doc.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
        doc.content_hash.toLowerCase().includes(searchQuery.toLowerCase());

      if (!matchesSearch) return false;

      if (selectedStatus === "All") return true;
      if (selectedStatus === "Indexed") return doc.status === "indexed";
      if (selectedStatus === "Flagged")
        return doc.status === "flagged" || doc.flagged_injection;
      if (selectedStatus === "Pending") return doc.status === "pending";

      return true;
    });
  }, [documents, searchQuery, selectedStatus]);

  const handleDelete = async (docId: string) => {
    if (!canDelete) return;
    setDeletingId(docId);
    setActionError(null);

    try {
      const result = await apiClient.documents.delete(docId);
      onDeleteSuccess(docId, result);
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Failed to execute document deletion";
      setActionError(message);
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="space-y-4">
      {/* Search & Filter Bar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search documents by name, UUID, or content hash..."
            className="w-full rounded-xl border border-gray-800 bg-gray-950/70 pl-9 pr-4 py-2 text-xs text-gray-200 placeholder-gray-500 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-colors"
          />
        </div>

        {/* Filter Pills */}
        <div className="flex items-center space-x-1.5 p-1 rounded-xl border border-gray-800 bg-gray-950/50">
          {["All", "Indexed", "Flagged", "Pending"].map((status) => (
            <button
              key={status}
              onClick={() => setSelectedStatus(status)}
              className={`px-3 py-1 rounded-lg text-xs font-medium transition-colors ${
                selectedStatus === status
                  ? "bg-blue-600 text-white"
                  : "text-gray-400 hover:text-gray-200 hover:bg-gray-800/60"
              }`}
            >
              {status}
            </button>
          ))}
        </div>
      </div>

      {actionError && (
        <div className="rounded-lg border border-rose-500/30 bg-rose-950/20 p-3 text-xs text-rose-300 flex items-center space-x-2">
          <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
          <span>{actionError}</span>
        </div>
      )}

      {/* Documents Table */}
      <div className="rounded-xl border border-gray-800 bg-gray-900/60 overflow-hidden">
        {isLoading ? (
          <div className="py-16 flex flex-col items-center justify-center space-y-3">
            <Loader2 className="w-8 h-8 text-blue-400 animate-spin" />
            <p className="text-xs text-gray-400">Loading document library...</p>
          </div>
        ) : filteredDocuments.length === 0 ? (
          <div className="py-16 flex flex-col items-center justify-center text-center p-6 space-y-2">
            <FileText className="w-10 h-10 text-gray-600 mb-1" />
            <p className="text-sm font-semibold text-gray-300">
              No matching documents found
            </p>
            <p className="text-xs text-gray-500 max-w-sm">
              Upload documents using the dropzone or adjust your search filters.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-gray-950/80 text-[11px] font-mono text-gray-400 uppercase tracking-wider border-b border-gray-800">
                <tr>
                  <th className="py-3 px-4">Document / ID</th>
                  <th className="py-3 px-3">Status</th>
                  <th className="py-3 px-3">Injection Scan (N8)</th>
                  <th className="py-3 px-3">Chunks</th>
                  <th className="py-3 px-3">Created</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800/60 text-gray-300">
                {filteredDocuments.map((doc) => {
                  const isBeingDeleted = deletingId === doc.id;
                  return (
                    <tr
                      key={doc.id}
                      className="hover:bg-gray-800/30 transition-colors"
                    >
                      {/* Document info */}
                      <td className="py-3.5 px-4">
                        <div className="flex items-center space-x-3">
                          <div className="p-2 rounded-lg bg-gray-800 text-gray-300 border border-gray-700/60">
                            <FileText className="w-4 h-4 text-blue-400" />
                          </div>
                          <div>
                            <span className="font-semibold text-gray-200 block truncate max-w-xs sm:max-w-md">
                              {doc.filename}
                            </span>
                            <span
                              className="text-[10px] font-mono text-gray-500 block truncate max-w-xs"
                              title={doc.id}
                            >
                              ID: {doc.id}
                            </span>
                          </div>
                        </div>
                      </td>

                      {/* Status */}
                      <td className="py-3.5 px-3">
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold uppercase ${
                            doc.status === "indexed"
                              ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                              : doc.status === "flagged"
                              ? "bg-rose-500/10 text-rose-400 border border-rose-500/20"
                              : "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                          }`}
                        >
                          {doc.status}
                        </span>
                      </td>

                      {/* Injection Scan */}
                      <td className="py-3.5 px-3">
                        {doc.flagged_injection ? (
                          <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20">
                            <ShieldAlert className="w-3 h-3" />
                            <span>Quarantined (N8)</span>
                          </span>
                        ) : (
                          <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                            <CheckCircle2 className="w-3 h-3" />
                            <span>Clean</span>
                          </span>
                        )}
                      </td>

                      {/* Chunks */}
                      <td className="py-3.5 px-3">
                        <span className="inline-flex items-center space-x-1 text-gray-400 font-mono text-[11px]">
                          <Layers className="w-3.5 h-3.5 text-gray-500" />
                          <span>{doc.chunk_count}</span>
                        </span>
                      </td>

                      {/* Created */}
                      <td className="py-3.5 px-3 text-[11px] text-gray-500 font-mono">
                        {new Date(doc.created_at).toLocaleDateString()}
                      </td>

                      {/* Actions */}
                      <td className="py-3.5 px-4 text-right">
                        <div className="flex items-center justify-end space-x-2">
                          <button
                            data-testid="inspect-doc-btn"
                            onClick={() => onInspect(doc.id)}
                            title="Inspect semantic chunks"
                            className="p-1.5 rounded-lg border border-gray-700 bg-gray-800 text-gray-300 hover:text-white hover:bg-gray-700 transition-colors"
                          >
                            <Eye className="w-4 h-4" />
                          </button>

                          <button
                            data-testid="delete-doc-btn"
                            onClick={() => handleDelete(doc.id)}
                            disabled={!canDelete || isBeingDeleted}
                            title={
                              !canDelete
                                ? "Requires Analyst or Admin role"
                                : isAdmin
                                ? "Delete document immediately (Admin)"
                                : "Request document deletion approval (Analyst)"
                            }
                            className={`flex items-center space-x-1 px-2.5 py-1.5 rounded-lg border text-xs font-medium transition-colors ${
                              !canDelete
                                ? "border-gray-800 bg-gray-900 text-gray-600 cursor-not-allowed opacity-50"
                                : isAdmin
                                ? "border-rose-500/30 bg-rose-500/10 text-rose-400 hover:bg-rose-500/20"
                                : "border-amber-500/30 bg-amber-500/10 text-amber-400 hover:bg-amber-500/20"
                            }`}
                          >
                            {isBeingDeleted ? (
                              <Loader2 className="w-3.5 h-3.5 animate-spin" />
                            ) : (
                              <Trash2 className="w-3.5 h-3.5" />
                            )}
                            <span className="hidden sm:inline">
                              {isAdmin ? "Delete" : "Request Delete"}
                            </span>
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
