"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  CheckCircle2,
  Clock,
  Sparkles,
  User,
  Database,
  ExternalLink,
} from "lucide-react";

export interface HeaderProps {
  currentRole?: "viewer" | "analyst" | "admin";
  onRoleChange?: (role: "viewer" | "analyst" | "admin") => void;
}

export function Header({
  currentRole = "analyst",
  onRoleChange,
}: HeaderProps) {
  const pathname = usePathname();
  const [role, setRole] = useState<"viewer" | "analyst" | "admin">(currentRole);

  const handleRoleSelect = (newRole: "viewer" | "analyst" | "admin") => {
    setRole(newRole);
    if (onRoleChange) {
      onRoleChange(newRole);
    }
  };

  // Human-readable breadcrumb segment
  const getBreadcrumbTitle = () => {
    if (pathname === "/") return "Overview Dashboard";
    if (pathname.startsWith("/search")) return "Intelligence Research";
    if (pathname.startsWith("/research")) return "Research Session Tracer";
    if (pathname.startsWith("/knowledge-graph")) return "Knowledge Graph Explorer";
    if (pathname.startsWith("/documents")) return "Enterprise Corpus & Uploads";
    if (pathname.startsWith("/browse/customers")) return "Customer Records";
    if (pathname.startsWith("/browse/incidents")) return "Incident Management";
    if (pathname.startsWith("/browse/decisions")) return "Architectural Decisions (ADRs)";
    return "Intelligence Console";
  };

  return (
    <header
      data-testid="app-header"
      className="flex items-center justify-between h-16 px-6 border-b border-gray-800 bg-[#0e1526]/90 backdrop-blur sticky top-0 z-20"
    >
      {/* Route Title & Breadcrumbs */}
      <div className="flex items-center space-x-3">
        <span className="text-xs font-mono text-gray-400">NovaEnterprise</span>
        <span className="text-gray-600 font-mono">/</span>
        <h1 className="text-sm font-semibold text-gray-100 tracking-wide">
          {getBreadcrumbTitle()}
        </h1>
      </div>

      {/* Status Badges & Controls */}
      <div className="flex items-center space-x-4">
        {/* Backend Status Badge */}
        <div
          data-testid="backend-status-pill"
          className="flex items-center space-x-1.5 px-2.5 py-1 rounded-full bg-emerald-950/60 text-emerald-400 border border-emerald-800/60 text-[11px] font-mono font-medium shadow-sm"
        >
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
          <span>API :8001 Ready</span>
        </div>

        {/* Demo Role Selector */}
        <div className="flex items-center space-x-2 bg-gray-900 border border-gray-800 rounded-lg p-1 text-xs font-mono">
          <User size={14} className="text-gray-400 ml-1" />
          <span className="text-[11px] text-gray-400">Role:</span>
          <select
            data-testid="role-selector"
            value={role}
            onChange={(e) =>
              handleRoleSelect(e.target.value as "viewer" | "analyst" | "admin")
            }
            className="bg-transparent text-gray-200 text-xs font-semibold focus:outline-none cursor-pointer pr-1"
          >
            <option value="viewer" className="bg-gray-900 text-gray-300">
              viewer (Read-only)
            </option>
            <option value="analyst" className="bg-gray-900 text-gray-300">
              analyst (Research & Ingest)
            </option>
            <option value="admin" className="bg-gray-900 text-gray-300">
              admin (Full Approvals)
            </option>
          </select>
        </div>

        {/* Quick Demo Question Link */}
        <Link
          href="/search"
          className="hidden sm:flex items-center space-x-1 px-3 py-1.5 rounded-md bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium transition-colors shadow-md shadow-blue-600/20"
        >
          <Sparkles size={14} />
          <span>New Research</span>
        </Link>
      </div>
    </header>
  );
}
