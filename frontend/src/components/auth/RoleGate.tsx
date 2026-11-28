"use client";

import React from "react";
import { useAuth, RoleAction } from "@/context/AuthContext";
import type { UserRole } from "@/types/api";

export interface RoleGateProps {
  requiredRole?: UserRole;
  action?: RoleAction;
  fallback?: React.ReactNode;
  showDisabled?: boolean;
  disabledTooltip?: string;
  children: React.ReactNode;
}

/**
 * RoleGate conditionally renders children based on user role or action permission.
 *
 * If the user lacks access:
 * - If `showDisabled` is true: wraps children in a visual disabled container.
 * - Else if `fallback` is provided: renders the fallback element.
 * - Otherwise: renders null (hidden).
 */
export function RoleGate({
  requiredRole,
  action,
  fallback = null,
  showDisabled = false,
  disabledTooltip,
  children,
}: RoleGateProps) {
  const { hasRole, canPerform } = useAuth();

  let hasAccess = true;

  if (action) {
    hasAccess = canPerform(action);
  } else if (requiredRole) {
    hasAccess = hasRole(requiredRole);
  }

  if (hasAccess) {
    return <>{children}</>;
  }

  if (showDisabled) {
    const tooltipText =
      disabledTooltip ||
      (action
        ? `Action '${action}' requires elevated permissions`
        : `Requires '${requiredRole}' role or higher`);

    return (
      <div
        data-testid="role-disabled-wrapper"
        title={tooltipText}
        className="opacity-50 cursor-not-allowed pointer-events-none select-none inline-block w-full"
        aria-disabled="true"
      >
        {children}
      </div>
    );
  }

  return <>{fallback}</>;
}
