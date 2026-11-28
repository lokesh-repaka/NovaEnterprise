"use client";

import React, { useState } from "react";
import {
  ShieldAlert,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Loader2,
  X,
  Lock,
  UserCheck,
} from "lucide-react";
import { apiClient } from "@/api/client";
import { useAuth } from "@/context/AuthContext";
import type {
  ApprovalRequestResponse,
  ApprovalDecisionResponse,
} from "@/types/api";

interface ApprovalModalProps {
  isOpen: boolean;
  approval: ApprovalRequestResponse | null;
  onClose: () => void;
  onDecisionSuccess: (decision: ApprovalDecisionResponse) => void;
}

export function ApprovalModal({
  isOpen,
  approval,
  onClose,
  onDecisionSuccess,
}: ApprovalModalProps) {
  const { canPerform } = useAuth();
  const canApprove = canPerform("approve"); // Only admin can approve/reject (F17)

  const [reason, setReason] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen || !approval) return null;

  const handleDecision = async (decision: "approved" | "rejected") => {
    if (!canApprove) return;
    setIsSubmitting(true);
    setError(null);

    try {
      const response = await apiClient.approvals.decide(approval.id, {
        decision,
        reason: reason.trim() || undefined,
      });
      onDecisionSuccess(response);
      onClose();
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Failed to record approval decision";
      setError(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full max-w-lg rounded-2xl border border-gray-800 bg-gray-900 shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-gray-800 px-6 py-4 bg-gray-950/60">
          <div className="flex items-center space-x-3">
            <div className="p-2 rounded-lg bg-amber-500/10 text-amber-400 border border-amber-500/20">
              <ShieldAlert className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-semibold text-white">
                Administrative Approval Gate (F17)
              </h3>
              <p className="text-xs text-gray-400">
                Human-in-the-Loop review for destructive document operations
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

        {/* Content */}
        <div className="p-6 space-y-5">
          {/* Metadata Grid */}
          <div className="grid grid-cols-2 gap-3 p-4 rounded-xl border border-gray-800 bg-gray-950/40 text-xs">
            <div>
              <span className="text-[10px] text-gray-500 uppercase tracking-wider block">
                Approval Request ID
              </span>
              <span className="font-mono text-gray-300 block mt-0.5 font-medium truncate">
                {approval.id}
              </span>
            </div>
            <div>
              <span className="text-[10px] text-gray-500 uppercase tracking-wider block">
                Action Type
              </span>
              <span className="text-rose-400 font-semibold uppercase block mt-0.5">
                {approval.action} Document
              </span>
            </div>
            <div>
              <span className="text-[10px] text-gray-500 uppercase tracking-wider block">
                Target Resource
              </span>
              <span
                className="font-mono text-gray-300 block mt-0.5 truncate"
                title={approval.resource_id}
              >
                {approval.resource_id}
              </span>
            </div>
            <div>
              <span className="text-[10px] text-gray-500 uppercase tracking-wider block">
                Requested By
              </span>
              <span className="font-mono text-blue-400 block mt-0.5">
                {approval.requester_id}
              </span>
            </div>
            <div className="col-span-2 pt-1 border-t border-gray-800/60 flex items-center justify-between">
              <span className="text-[10px] text-gray-500">Status</span>
              <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20 uppercase">
                {approval.status}
              </span>
            </div>
          </div>

          {/* Decision Justification Input */}
          <div className="space-y-1.5">
            <label className="block text-xs font-medium text-gray-300">
              Audit Justification / Decision Notes
            </label>
            <textarea
              data-testid="approval-reason-input"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="e.g. Verified document is obsolete and replaced by newer policy document..."
              disabled={!canApprove || isSubmitting}
              rows={3}
              className="w-full rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 text-xs text-gray-200 placeholder-gray-500 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-colors disabled:opacity-50"
            />
          </div>

          {/* Role Restriction Banner (F17) */}
          {!canApprove && (
            <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-200 flex items-start space-x-2.5">
              <Lock className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
              <div>
                <span className="font-semibold text-amber-300 block">
                  Admin role required to resolve approval gates (F17)
                </span>
                <p className="text-amber-200/80 mt-0.5 text-[11px]">
                  Analysts may file deletion requests, but only administrators
                  can approve or reject destructive document pruning.
                </p>
              </div>
            </div>
          )}

          {/* Error Banner */}
          {error && (
            <div className="rounded-lg border border-rose-500/30 bg-rose-950/20 p-3 text-xs text-rose-300 flex items-start space-x-2">
              <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}
        </div>

        {/* Footer Actions */}
        <div className="flex items-center justify-between border-t border-gray-800 px-6 py-4 bg-gray-950/40">
          <button
            onClick={onClose}
            disabled={isSubmitting}
            className="px-4 py-2 rounded-lg border border-gray-700 bg-gray-800 text-xs text-gray-300 hover:bg-gray-700 hover:text-white transition-colors"
          >
            Cancel
          </button>

          <div className="flex items-center space-x-2.5">
            <button
              data-testid="reject-decision-btn"
              onClick={() => handleDecision("rejected")}
              disabled={!canApprove || isSubmitting}
              className="flex items-center space-x-1.5 px-3.5 py-2 rounded-lg border border-rose-500/30 bg-rose-500/10 text-rose-400 hover:bg-rose-500/20 text-xs font-semibold transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isSubmitting ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <XCircle className="w-3.5 h-3.5" />
              )}
              <span>Reject Request</span>
            </button>

            <button
              data-testid="approve-decision-btn"
              onClick={() => handleDecision("approved")}
              disabled={!canApprove || isSubmitting}
              className="flex items-center space-x-1.5 px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isSubmitting ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <CheckCircle2 className="w-3.5 h-3.5" />
              )}
              <span>Approve Deletion</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
