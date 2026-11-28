"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  User,
  Sparkles,
  LogIn,
  LogOut,
  ShieldAlert,
} from "lucide-react";
import { useOptionalAuth } from "@/context/AuthContext";
import { LoginModal } from "@/components/auth/LoginModal";
import { RoleGate } from "@/components/auth/RoleGate";
import type { UserRole } from "@/types/api";

export interface HeaderProps {
  currentRole?: UserRole;
  onRoleChange?: (role: UserRole) => void;
}

const ROLE_BADGE_COLORS: Record<UserRole, { bg: string; text: string; border: string }> = {
  admin: {
    bg: "bg-purple-950/60",
    text: "text-purple-300",
    border: "border-purple-800/60",
  },
  analyst: {
    bg: "bg-blue-950/60",
    text: "text-blue-300",
    border: "border-blue-800/60",
  },
  viewer: {
    bg: "bg-emerald-950/60",
    text: "text-emerald-300",
    border: "border-emerald-800/60",
  },
};

export function Header({
  currentRole,
  onRoleChange,
}: HeaderProps) {
  const pathname = usePathname();
  const [isLoginOpen, setIsLoginOpen] = useState(false);
  const authContext = useOptionalAuth();

  const [localRole, setLocalRole] = useState<UserRole>(currentRole ?? "analyst");
  const effectiveRole = authContext ? authContext.role : (currentRole ?? localRole);

  const handleRoleSelect = (newRole: UserRole) => {
    setLocalRole(newRole);
    if (authContext) {
      authContext.switchDemoRole(newRole);
    }
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

  const badgeStyle = ROLE_BADGE_COLORS[effectiveRole] || ROLE_BADGE_COLORS.analyst;

  return (
    <>
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
        <div className="flex items-center space-x-3">
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
              value={effectiveRole}
              onChange={(e) =>
                handleRoleSelect(e.target.value as UserRole)
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

          {/* User Persona / Auth Switcher Button */}
          <button
            data-testid="auth-persona-btn"
            onClick={() => setIsLoginOpen(true)}
            title="Switch demo persona or login"
            className={`flex items-center space-x-1.5 px-2.5 py-1 rounded-lg border text-xs font-mono transition-colors ${badgeStyle.bg} ${badgeStyle.text} ${badgeStyle.border} hover:opacity-90`}
          >
            <span className="font-semibold uppercase text-[10px]">
              {authContext?.user?.username || effectiveRole}
            </span>
          </button>

          {/* Quick Demo Question Link (Role-aware: disabled for viewer) */}
          {authContext ? (
            <RoleGate
              action="research"
              showDisabled
              disabledTooltip="Research creation requires Analyst or Admin role"
            >
              <Link
                href="/search"
                className="hidden sm:flex items-center space-x-1 px-3 py-1.5 rounded-md bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium transition-colors shadow-md shadow-blue-600/20"
              >
                <Sparkles size={14} />
                <span>New Research</span>
              </Link>
            </RoleGate>
          ) : (
            <Link
              href="/search"
              className="hidden sm:flex items-center space-x-1 px-3 py-1.5 rounded-md bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium transition-colors shadow-md shadow-blue-600/20"
            >
              <Sparkles size={14} />
              <span>New Research</span>
            </Link>
          )}
        </div>
      </header>

      {/* Modal Dialog */}
      {isLoginOpen && (
        <LoginModal isOpen={isLoginOpen} onClose={() => setIsLoginOpen(false)} />
      )}
    </>
  );
}
