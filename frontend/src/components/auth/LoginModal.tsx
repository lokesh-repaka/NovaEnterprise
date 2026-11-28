"use client";

import React, { useState } from "react";
import {
  X,
  User,
  ShieldCheck,
  KeyRound,
  LogIn,
  AlertCircle,
  Loader2,
  CheckCircle2,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import type { UserRole, DemoUser } from "@/types/api";

export interface LoginModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const ROLE_BADGE_STYLES: Record<UserRole, { bg: string; text: string; border: string }> = {
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

export function LoginModal({ isOpen, onClose }: LoginModalProps) {
  const { demoUsers, role: currentRole, switchDemoRole, login, isLoading } = useAuth();
  const [activeTab, setActiveTab] = useState<"demo" | "credentials">("demo");
  const [usernameOrEmail, setUsernameOrEmail] = useState("");
  const [password, setPassword] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (!isOpen) return null;

  const handleDemoSelect = async (role: UserRole) => {
    try {
      await switchDemoRole(role);
      onClose();
    } catch {
      // Error is tracked in AuthContext
    }
  };

  const handleCredentialSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    setIsSubmitting(true);

    try {
      await login({ username_or_email: usernameOrEmail, password });
      onClose();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Authentication failed";
      setFormError(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleFillDemoAdmin = () => {
    setUsernameOrEmail("admin@novaenterprise.io");
    setPassword("demo_password");
  };

  return (
    <div
      data-testid="login-modal-backdrop"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4 overflow-y-auto"
    >
      <div
        data-testid="login-modal"
        className="relative w-full max-w-lg rounded-xl border border-gray-800 bg-[#0d121f] p-6 shadow-2xl text-gray-100"
      >
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-gray-800">
          <div className="flex items-center space-x-2.5">
            <div className="p-2 rounded-lg bg-blue-600/20 text-blue-400 border border-blue-500/30">
              <KeyRound size={20} />
            </div>
            <div>
              <h2 className="text-base font-semibold text-white">
                Enterprise Authentication
              </h2>
              <p className="text-xs text-gray-400">
                Switch demo persona or login with enterprise credentials
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            aria-label="Close dialog"
            className="p-1 rounded-md text-gray-400 hover:text-white hover:bg-gray-800 transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {/* Tab Switcher */}
        <div className="flex border-b border-gray-800 my-4 text-xs font-medium">
          <button
            data-testid="tab-demo"
            onClick={() => {
              setActiveTab("demo");
              setFormError(null);
            }}
            className={`flex items-center space-x-1.5 px-4 py-2.5 border-b-2 transition-colors ${
              activeTab === "demo"
                ? "border-blue-500 text-blue-400 font-semibold"
                : "border-transparent text-gray-400 hover:text-gray-200"
            }`}
          >
            <User size={14} />
            <span>1-Click Demo Personas</span>
          </button>
          <button
            data-testid="tab-credentials"
            onClick={() => {
              setActiveTab("credentials");
              setFormError(null);
            }}
            className={`flex items-center space-x-1.5 px-4 py-2.5 border-b-2 transition-colors ${
              activeTab === "credentials"
                ? "border-blue-500 text-blue-400 font-semibold"
                : "border-transparent text-gray-400 hover:text-gray-200"
            }`}
          >
            <LogIn size={14} />
            <span>Password Login</span>
          </button>
        </div>

        {/* Tab 1: Demo Personas */}
        {activeTab === "demo" && (
          <div className="space-y-3 py-1">
            <p className="text-xs text-gray-400 mb-2">
              Select an enterprise persona to instantly evaluate RBAC permissions without entering passwords:
            </p>
            {demoUsers.map((demo: DemoUser) => {
              const isCurrent = currentRole === demo.role;
              const style = ROLE_BADGE_STYLES[demo.role] || ROLE_BADGE_STYLES.viewer;

              return (
                <div
                  key={demo.id}
                  data-testid={`demo-persona-card-${demo.role}`}
                  className={`flex items-center justify-between p-3.5 rounded-lg border transition-all ${
                    isCurrent
                      ? "border-blue-500/80 bg-blue-950/20 shadow-md"
                      : "border-gray-800 hover:border-gray-700 bg-gray-900/60"
                  }`}
                >
                  <div className="space-y-1">
                    <div className="flex items-center space-x-2">
                      <span className="text-sm font-semibold text-gray-100">
                        {demo.name}
                      </span>
                      <span
                        className={`text-[10px] font-mono uppercase px-2 py-0.5 rounded-full border ${style.bg} ${style.text} ${style.border}`}
                      >
                        {demo.role}
                      </span>
                      {isCurrent && (
                        <span className="flex items-center space-x-1 text-[11px] text-blue-400 font-medium">
                          <CheckCircle2 size={12} />
                          <span>Active</span>
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-gray-400 font-mono text-[11px]">
                      {demo.email}
                    </p>
                    <p className="text-xs text-gray-300">{demo.description}</p>
                  </div>

                  <button
                    data-testid={`btn-select-demo-${demo.role}`}
                    onClick={() => handleDemoSelect(demo.role)}
                    disabled={isLoading || isCurrent}
                    className={`ml-4 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                      isCurrent
                        ? "bg-gray-800 text-gray-400 cursor-default"
                        : "bg-blue-600 hover:bg-blue-500 text-white shadow-sm hover:shadow-blue-600/30"
                    }`}
                  >
                    {isCurrent ? "Current" : "Switch"}
                  </button>
                </div>
              );
            })}
          </div>
        )}

        {/* Tab 2: Standard Login Form */}
        {activeTab === "credentials" && (
          <form onSubmit={handleCredentialSubmit} className="space-y-4 py-1">
            {formError && (
              <div
                data-testid="login-error-alert"
                className="flex items-center space-x-2 p-3 rounded-lg bg-red-950/50 border border-red-800/80 text-red-300 text-xs"
              >
                <AlertCircle size={15} className="flex-shrink-0" />
                <span>{formError}</span>
              </div>
            )}

            <div className="space-y-1">
              <label
                htmlFor="username_or_email"
                className="block text-xs font-medium text-gray-300 font-mono"
              >
                Username or Work Email
              </label>
              <input
                id="username_or_email"
                data-testid="input-username"
                type="text"
                required
                value={usernameOrEmail}
                onChange={(e) => setUsernameOrEmail(e.target.value)}
                placeholder="admin@novaenterprise.io"
                className="w-full px-3 py-2 rounded-lg bg-gray-900 border border-gray-800 text-gray-100 text-xs font-mono focus:border-blue-500 focus:outline-none"
              />
            </div>

            <div className="space-y-1">
              <label
                htmlFor="password"
                className="block text-xs font-medium text-gray-300 font-mono"
              >
                Password
              </label>
              <input
                id="password"
                data-testid="input-password"
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
                className="w-full px-3 py-2 rounded-lg bg-gray-900 border border-gray-800 text-gray-100 text-xs focus:border-blue-500 focus:outline-none"
              />
            </div>

            <div className="flex items-center justify-between text-xs text-gray-400 pt-1">
              <button
                type="button"
                onClick={handleFillDemoAdmin}
                className="text-blue-400 hover:underline text-[11px]"
              >
                Fill Demo Admin Credentials
              </button>
              <span className="text-[11px] font-mono text-gray-500">
                Demo pw: demo_password
              </span>
            </div>

            <div className="pt-2 flex justify-end space-x-3">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 rounded-lg border border-gray-800 text-xs text-gray-300 hover:bg-gray-800 transition-colors"
              >
                Cancel
              </button>
              <button
                data-testid="btn-submit-login"
                type="submit"
                disabled={isSubmitting}
                className="flex items-center space-x-1.5 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium transition-colors disabled:opacity-50"
              >
                {isSubmitting ? (
                  <>
                    <Loader2 size={14} className="animate-spin" />
                    <span>Signing in...</span>
                  </>
                ) : (
                  <>
                    <LogIn size={14} />
                    <span>Sign In</span>
                  </>
                )}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
