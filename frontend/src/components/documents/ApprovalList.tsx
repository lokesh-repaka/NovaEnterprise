"use client";

import React, { useState, useMemo } from "react";
import {
  ShieldAlert,
  Search,
  CheckCircle2,
  XCircle,
  Clock,
  UserCheck,
  FileText,
  Loader2,
  ExternalLink,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import type { ApprovalRequestResponse } from "@/types/api";

interface ApprovalListProps {
  approvals: ApprovalRequestResponse[];
  isLoading: boolean;
  onReviewApproval: (approval: ApprovalRequestResponse) => void;
}

export function ApprovalList({
  approvals,
  isLoading,
  onReviewApproval,
}: ApprovalListProps) {
  const { role } = useAuth();
  const isAdmin = role === "admin";

  const [searchQuery, setSearchQuery] = useState("");
  const [selectedStatus, setSelectedStatus] = useState<string>("All");

  const filteredApprovals = useMemo(() => {
    return approvals.filter((item) => {
      const matchesSearch =
        item.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
        item.resource_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
        item.requester_id.toLowerCase().includes(searchQuery.toLowerCase());

      if (!matchesSearch) return false;

      if (selectedStatus === "All") return true;
      if (selectedStatus === "Pending") return item.status === "pending";
      if (selectedStatus === "Approved") return item.status === "approved";
      if (selectedStatus === "Rejected") return item.status === "rejected";

      return true;
    });
  }, [approvals, searchQuery, selectedStatus]);

  return (
    <div className="space-y-4">
      {/* Search & Status Filters */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search approvals by Request ID, Resource ID, or Requester..."
            className="w-full rounded-xl border border-gray-800 bg-gray-950/70 pl-9 pr-4 py-2 text-xs text-gray-200 placeholder-gray-500 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-colors"
          />
        </div>

        {/* Filter Pills */}
        <div className="flex items-center space-x-1.5 p-1 rounded-xl border border-gray-800 bg-gray-950/50">
          {["All", "Pending", "Approved", "Rejected"].map((status) => (
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

      {/* Approvals Table */}
      <div className="rounded-xl border border-gray-800 bg-gray-900/60 overflow-hidden">
        {isLoading ? (
          <div className="py-16 flex flex-col items-center justify-center space-y-3">
            <Loader2 className="w-8 h-8 text-blue-400 animate-spin" />
            <p className="text-xs text-gray-400">Loading approval queue...</p>
          </div>
        ) : filteredApprovals.length === 0 ? (
          <div className="py-16 flex flex-col items-center justify-center text-center p-6 space-y-2">
            <ShieldAlert className="w-10 h-10 text-gray-600 mb-1" />
            <p className="text-sm font-semibold text-gray-300">
              No approval requests found
            </p>
            <p className="text-xs text-gray-500 max-w-sm">
              Destructive operations queued by analysts will appear here for
              administrative sign-off.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-gray-950/80 text-[11px] font-mono text-gray-400 uppercase tracking-wider border-b border-gray-800">
                <tr>
                  <th className="py-3 px-4">Approval Request</th>
                  <th className="py-3 px-3">Target Resource</th>
                  <th className="py-3 px-3">Action</th>
                  <th className="py-3 px-3">Requester</th>
                  <th className="py-3 px-3">Status</th>
                  <th className="py-3 px-3">Filed At</th>
                  <th className="py-3 px-4 text-right">Gate Review</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800/60 text-gray-300">
                {filteredApprovals.map((req) => (
                  <tr
                    key={req.id}
                    className="hover:bg-gray-800/30 transition-colors"
                  >
                    {/* Request ID */}
                    <td className="py-3.5 px-4 font-mono font-medium text-gray-200">
                      <div className="flex items-center space-x-2">
                        <ShieldAlert className="w-4 h-4 text-amber-400 shrink-0" />
                        <span className="truncate max-w-[140px]" title={req.id}>
                          {req.id}
                        </span>
                      </div>
                    </td>

                    {/* Target Resource */}
                    <td className="py-3.5 px-3">
                      <div className="flex items-center space-x-1.5 font-mono text-gray-400">
                        <FileText className="w-3.5 h-3.5 text-blue-400 shrink-0" />
                        <span
                          className="truncate max-w-[160px]"
                          title={req.resource_id}
                        >
                          {req.resource_id}
                        </span>
                      </div>
                    </td>

                    {/* Action */}
                    <td className="py-3.5 px-3">
                      <span className="text-[10px] font-semibold uppercase px-2 py-0.5 rounded bg-rose-500/10 text-rose-400 border border-rose-500/20">
                        {req.action}
                      </span>
                    </td>

                    {/* Requester */}
                    <td className="py-3.5 px-3 font-mono text-gray-400">
                      {req.requester_id}
                    </td>

                    {/* Status */}
                    <td className="py-3.5 px-3">
                      <span
                        className={`inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[10px] font-semibold uppercase ${
                          req.status === "approved"
                            ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                            : req.status === "rejected"
                            ? "bg-rose-500/10 text-rose-400 border border-rose-500/20"
                            : "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                        }`}
                      >
                        {req.status === "approved" ? (
                          <CheckCircle2 className="w-3 h-3" />
                        ) : req.status === "rejected" ? (
                          <XCircle className="w-3 h-3" />
                        ) : (
                          <Clock className="w-3 h-3" />
                        )}
                        <span>{req.status}</span>
                      </span>
                    </td>

                    {/* Created */}
                    <td className="py-3.5 px-3 text-[11px] text-gray-500 font-mono">
                      {new Date(req.created_at).toLocaleDateString()}
                    </td>

                    {/* Gate Review Button */}
                    <td className="py-3.5 px-4 text-right">
                      <button
                        data-testid="review-approval-btn"
                        onClick={() => onReviewApproval(req)}
                        className={`px-3 py-1.5 rounded-lg border text-xs font-medium transition-colors ${
                          req.status === "pending"
                            ? isAdmin
                              ? "border-amber-500/40 bg-amber-500/10 text-amber-300 hover:bg-amber-500/20 shadow-sm"
                              : "border-gray-700 bg-gray-800 text-gray-300 hover:bg-gray-700"
                            : "border-gray-800 bg-gray-900 text-gray-400 hover:text-gray-200"
                        }`}
                      >
                        {req.status === "pending"
                          ? isAdmin
                            ? "Review & Decide"
                            : "Inspect Request"
                          : "View Decision"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
