"use client";

import React, { useEffect, useState } from "react";
import {
  FileText,
  Layers,
  ShieldAlert,
  Hash,
  X,
  Loader2,
  AlertTriangle,
  Database,
} from "lucide-react";
import { apiClient } from "@/api/client";
import type { DocumentDetailResponse } from "@/types/api";

interface DocumentInspectorModalProps {
  isOpen: boolean;
  documentId: string | null;
  onClose: () => void;
}

export function DocumentInspectorModal({
  isOpen,
  documentId,
  onClose,
}: DocumentInspectorModalProps) {
  const [detail, setDetail] = useState<DocumentDetailResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen || !documentId) {
      setDetail(null);
      setError(null);
      return;
    }

    let isMounted = true;
    setIsLoading(true);
    setError(null);

    apiClient.documents
      .get(documentId)
      .then((data) => {
        if (isMounted) setDetail(data);
      })
      .catch((err: unknown) => {
        if (isMounted) {
          setError(
            err instanceof Error ? err.message : "Failed to load document details"
          );
        }
      })
      .finally(() => {
        if (isMounted) setIsLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [isOpen, documentId]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full max-w-3xl max-h-[85vh] rounded-2xl border border-gray-800 bg-gray-900 shadow-2xl flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-gray-800 px-6 py-4 bg-gray-950/60">
          <div className="flex items-center space-x-3">
            <div className="p-2 rounded-lg bg-blue-500/10 text-blue-400 border border-blue-500/20">
              <FileText className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-semibold text-white truncate max-w-lg">
                {detail?.filename || "Document Details"}
              </h3>
              <p className="text-xs text-gray-400 font-mono">
                {documentId}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-gray-400 hover:text-white hover:bg-gray-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 overflow-y-auto space-y-6 flex-1">
          {isLoading ? (
            <div className="py-16 flex flex-col items-center justify-center space-y-3">
              <Loader2 className="w-8 h-8 text-blue-400 animate-spin" />
              <p className="text-xs text-gray-400">Loading semantic chunks...</p>
            </div>
          ) : error ? (
            <div className="rounded-lg border border-rose-500/30 bg-rose-950/20 p-4 text-xs text-rose-300 flex items-center space-x-2">
              <AlertTriangle className="w-5 h-5 text-rose-400 shrink-0" />
              <span>{error}</span>
            </div>
          ) : detail ? (
            <>
              {/* Metadata Cards */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                <div className="p-3 rounded-xl border border-gray-800 bg-gray-950/50">
                  <span className="text-[10px] text-gray-500 uppercase tracking-wider block">
                    Status
                  </span>
                  <span className="font-semibold text-emerald-400 capitalize block mt-0.5">
                    {detail.status}
                  </span>
                </div>
                <div className="p-3 rounded-xl border border-gray-800 bg-gray-950/50">
                  <span className="text-[10px] text-gray-500 uppercase tracking-wider block">
                    Chunks
                  </span>
                  <span className="font-semibold text-gray-200 block mt-0.5">
                    {detail.chunk_count} semantic segments
                  </span>
                </div>
                <div className="p-3 rounded-xl border border-gray-800 bg-gray-950/50">
                  <span className="text-[10px] text-gray-500 uppercase tracking-wider block">
                    Injection Scan
                  </span>
                  <span
                    className={`font-semibold block mt-0.5 ${
                      detail.flagged_injection
                        ? "text-amber-400"
                        : "text-gray-300"
                    }`}
                  >
                    {detail.flagged_injection
                      ? "Quarantined (N8)"
                      : "Clean (Verified)"}
                  </span>
                </div>
                <div className="p-3 rounded-xl border border-gray-800 bg-gray-950/50">
                  <span className="text-[10px] text-gray-500 uppercase tracking-wider block">
                    Content Hash
                  </span>
                  <span
                    className="font-mono text-[11px] text-gray-400 block mt-0.5 truncate"
                    title={detail.content_hash}
                  >
                    {detail.content_hash}
                  </span>
                </div>
              </div>

              {/* Chunks Section */}
              <div className="space-y-3">
                <div className="flex items-center space-x-2">
                  <Layers className="w-4 h-4 text-blue-400" />
                  <h4 className="text-xs font-semibold uppercase tracking-wider text-gray-300">
                    Semantic Chunk Breakdown ({detail.chunks.length})
                  </h4>
                </div>

                <div className="space-y-3">
                  {detail.chunks.map((chunk) => (
                    <div
                      key={chunk.id}
                      className="rounded-xl border border-gray-800 bg-gray-950/40 p-4 space-y-2 hover:border-gray-700 transition-colors"
                    >
                      <div className="flex items-center justify-between text-[11px] text-gray-400 pb-2 border-b border-gray-800/60 font-mono">
                        <span className="font-semibold text-blue-400">
                          Chunk #{chunk.chunk_index}
                        </span>
                        <div className="flex items-center space-x-3">
                          <span title={chunk.id} className="text-gray-500">
                            ID: {chunk.id.slice(0, 8)}...
                          </span>
                          {chunk.embedding_id && (
                            <span className="text-emerald-500/80">
                              Vector: {chunk.embedding_id.slice(0, 8)}...
                            </span>
                          )}
                        </div>
                      </div>
                      <p className="text-xs text-gray-300 leading-relaxed font-mono whitespace-pre-wrap bg-gray-950/70 p-3 rounded-lg border border-gray-800/40">
                        {chunk.text}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            </>
          ) : null}
        </div>

        {/* Footer */}
        <div className="border-t border-gray-800 px-6 py-3.5 bg-gray-950/40 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg border border-gray-700 bg-gray-800 text-xs text-gray-300 hover:bg-gray-700 hover:text-white transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
