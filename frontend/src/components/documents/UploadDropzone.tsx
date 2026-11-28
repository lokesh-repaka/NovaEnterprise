"use client";

import React, { useState, useRef, useCallback } from "react";
import {
  UploadCloud,
  FileText,
  AlertTriangle,
  CheckCircle2,
  ShieldAlert,
  Loader2,
  Lock,
  RefreshCw,
} from "lucide-react";
import { apiClient } from "@/api/client";
import { useAuth } from "@/context/AuthContext";
import type { DocumentUploadResponse } from "@/types/api";

const ALLOWED_EXTENSIONS = [".md", ".txt", ".pdf"];
const MAX_UPLOAD_BYTES = 5 * 1024 * 1024; // 5 MB per N7

interface UploadDropzoneProps {
  onUploadSuccess?: (doc: DocumentUploadResponse) => void;
  className?: string;
}

export function UploadDropzone({
  onUploadSuccess,
  className = "",
}: UploadDropzoneProps) {
  const { canPerform } = useAuth();
  const canUpload = canPerform("upload");

  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [lastUploadedDoc, setLastUploadedDoc] =
    useState<DocumentUploadResponse | null>(null);
  const [stagedFileName, setStagedFileName] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const validateFile = useCallback((file: File): string | null => {
    if (!file) return "No file selected.";

    // 1. Check extension allowlist (.md, .txt, .pdf per N7)
    const lowerName = file.name.toLowerCase();
    const hasValidExt = ALLOWED_EXTENSIONS.some((ext) =>
      lowerName.endsWith(ext)
    );
    if (!hasValidExt) {
      return `Invalid file format for "${file.name}". Only .md, .txt, and .pdf documents are permitted (N7).`;
    }

    // 2. Check file size cap (5MB per N7)
    if (file.size > MAX_UPLOAD_BYTES) {
      const sizeMb = (file.size / (1024 * 1024)).toFixed(2);
      return `File size exceeds 5MB limit (${sizeMb} MB detected) (N7).`;
    }

    // 3. Check for empty file
    if (file.size === 0) {
      return `File "${file.name}" is empty (0 bytes).`;
    }

    return null;
  }, []);

  const handleProcessFile = useCallback(
    async (file: File) => {
      setValidationError(null);
      setUploadError(null);

      const error = validateFile(file);
      if (error) {
        setValidationError(error);
        return;
      }

      setStagedFileName(file.name);
      setIsUploading(true);

      try {
        const response = await apiClient.documents.upload(file);
        setLastUploadedDoc(response);
        if (onUploadSuccess) {
          onUploadSuccess(response);
        }
      } catch (err: unknown) {
        const message =
          err instanceof Error
            ? err.message
            : "Failed to upload and ingest document";
        setUploadError(message);
      } finally {
        setIsUploading(false);
      }
    },
    [validateFile, onUploadSuccess]
  );

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    if (canUpload && !isUploading) {
      setIsDragging(true);
    }
  };

  const handleDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    if (!canUpload || isUploading) return;

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const file = e.dataTransfer.files[0];
      handleProcessFile(file);
    }
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const file = e.target.files[0];
      handleProcessFile(file);
    }
    // Reset file input so re-uploading the same file triggers change
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const handleReset = () => {
    setLastUploadedDoc(null);
    setValidationError(null);
    setUploadError(null);
    setStagedFileName(null);
  };

  return (
    <div className={`space-y-4 ${className}`}>
      {/* Hidden File Input */}
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileInputChange}
        accept=".md,.txt,.pdf"
        disabled={!canUpload || isUploading}
        className="hidden"
        data-testid="file-upload-input"
      />

      {/* Upload Box / Staged Status */}
      {lastUploadedDoc ? (
        <div className="rounded-xl border border-emerald-500/30 bg-emerald-950/20 p-5 space-y-4">
          <div className="flex items-start justify-between">
            <div className="flex items-center space-x-3">
              <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                <CheckCircle2 className="w-5 h-5" />
              </div>
              <div>
                <h4 className="text-sm font-semibold text-emerald-200">
                  Document Ingested Successfully
                </h4>
                <p className="text-xs text-gray-400 font-mono mt-0.5">
                  {lastUploadedDoc.filename}
                </p>
              </div>
            </div>
            <button
              onClick={handleReset}
              className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg border border-gray-700 bg-gray-800 text-xs text-gray-300 hover:bg-gray-700 hover:text-white transition-colors"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Upload Another</span>
            </button>
          </div>

          {/* Prompt Injection Detection Alert (N8) */}
          {lastUploadedDoc.flagged_injection && (
            <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-xs text-amber-200 flex items-start space-x-3">
              <ShieldAlert className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
              <div className="space-y-1">
                <span className="font-semibold text-amber-300">
                  Prompt Injection Payload Detected (N8)
                </span>
                <p className="text-amber-200/80 leading-relaxed">
                  Adversarial prompt injection pattern was detected in this
                  document. Content has been quarantined as inert data; it will
                  never execute as agent instructions.
                </p>
              </div>
            </div>
          )}

          {/* Ingestion Metadata Badges */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1 border-t border-gray-800/80">
            <div className="bg-gray-900/60 rounded-lg p-2.5 border border-gray-800">
              <span className="text-[10px] text-gray-500 uppercase tracking-wider block">
                Document ID
              </span>
              <span
                className="text-xs font-mono text-gray-300 truncate block mt-0.5"
                title={lastUploadedDoc.document_id || lastUploadedDoc.id}
              >
                {lastUploadedDoc.document_id || lastUploadedDoc.id}
              </span>
            </div>
            <div className="bg-gray-900/60 rounded-lg p-2.5 border border-gray-800">
              <span className="text-[10px] text-gray-500 uppercase tracking-wider block">
                Semantic Chunks
              </span>
              <span className="text-xs font-semibold text-gray-200 block mt-0.5">
                Chunks: {lastUploadedDoc.chunk_count}
              </span>
            </div>
            <div className="bg-gray-900/60 rounded-lg p-2.5 border border-gray-800">
              <span className="text-[10px] text-gray-500 uppercase tracking-wider block">
                Graph Entities
              </span>
              <span className="text-xs font-semibold text-gray-200 block mt-0.5">
                Entities: {lastUploadedDoc.entities_extracted ?? 0}
              </span>
            </div>
            <div className="bg-gray-900/60 rounded-lg p-2.5 border border-gray-800">
              <span className="text-[10px] text-gray-500 uppercase tracking-wider block">
                Status
              </span>
              <span className="text-xs font-medium text-emerald-400 capitalize block mt-0.5">
                {lastUploadedDoc.status}
              </span>
            </div>
          </div>
        </div>
      ) : (
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => {
            if (canUpload && !isUploading && fileInputRef.current) {
              fileInputRef.current.click();
            }
          }}
          className={`relative rounded-xl border-2 border-dashed p-8 flex flex-col items-center justify-center text-center transition-all ${
            !canUpload
              ? "border-gray-800 bg-gray-950/60 cursor-not-allowed opacity-75"
              : isDragging
              ? "border-blue-500 bg-blue-500/10 cursor-copy scale-[1.01]"
              : isUploading
              ? "border-blue-500/40 bg-gray-900/60 cursor-wait"
              : "border-gray-700 hover:border-blue-500/70 bg-gray-900/40 hover:bg-gray-900/60 cursor-pointer"
          }`}
        >
          {isUploading ? (
            <div className="space-y-3 py-2">
              <Loader2 className="w-8 h-8 text-blue-400 animate-spin mx-auto" />
              <div>
                <p className="text-sm font-semibold text-gray-200">
                  Uploading and indexing document...
                </p>
                <p className="text-xs text-gray-400 font-mono mt-1">
                  {stagedFileName}
                </p>
              </div>
            </div>
          ) : !canUpload ? (
            <div className="space-y-3 py-2">
              <div className="p-3 rounded-full bg-gray-800 text-gray-400 mx-auto w-fit">
                <Lock className="w-6 h-6" />
              </div>
              <div className="space-y-1">
                <p className="text-sm font-semibold text-gray-300">
                  Upload restricted to Analyst and Admin roles
                </p>
                <p className="text-xs text-gray-500 max-w-sm mx-auto">
                  Viewer role is read-only. Switch to Analyst or Admin persona in
                  the top navigation to upload documents.
                </p>
              </div>
            </div>
          ) : (
            <div className="space-y-3 py-2">
              <div className="p-3.5 rounded-full bg-blue-600/10 text-blue-400 border border-blue-500/20 mx-auto w-fit group-hover:scale-105 transition-transform">
                <UploadCloud className="w-7 h-7" />
              </div>
              <div className="space-y-1">
                <p className="text-sm font-semibold text-gray-200">
                  Upload Enterprise Document
                </p>
                <p className="text-xs text-gray-400">
                  Drag and drop files here or click to browse
                </p>
              </div>
              <div className="flex items-center justify-center space-x-2 pt-1 text-[11px] text-gray-500 font-mono">
                <span>Formats: .md, .txt, .pdf</span>
                <span>•</span>
                <span>5MB limit (N7)</span>
                <span>•</span>
                <span>Prompt Injection Scanned (N8)</span>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Validation Error Banner */}
      {validationError && (
        <div className="rounded-lg border border-red-500/30 bg-red-950/20 p-3 text-xs text-red-300 flex items-start space-x-2.5">
          <AlertTriangle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
          <div className="flex-1">
            <span className="font-semibold text-red-200">Validation Error: </span>
            {validationError}
          </div>
        </div>
      )}

      {/* API Upload Error Banner */}
      {uploadError && (
        <div className="rounded-lg border border-red-500/30 bg-red-950/20 p-3 text-xs text-red-300 flex items-start space-x-2.5">
          <AlertTriangle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
          <div className="flex-1">
            <span className="font-semibold text-red-200">Upload Failed: </span>
            {uploadError}
          </div>
        </div>
      )}
    </div>
  );
}
