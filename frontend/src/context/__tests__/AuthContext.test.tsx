import React from "react";
import { render, screen, act, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { AuthProvider, useAuth } from "../AuthContext";
import { apiClient } from "@/api/client";
import type { DemoUser, TokenResponse, UserProfileResponse, UserRole } from "@/types/api";

// Test consumer component
function TestConsumer() {
  const {
    user,
    token,
    role,
    demoUsers,
    isLoading,
    isAuthenticated,
    login,
    switchDemoRole,
    logout,
    hasRole,
    canPerform,
  } = useAuth();

  return (
    <div>
      <div data-testid="auth-loading">{isLoading ? "loading" : "ready"}</div>
      <div data-testid="auth-status">{isAuthenticated ? "authenticated" : "unauthenticated"}</div>
      <div data-testid="auth-role">{role}</div>
      <div data-testid="auth-token">{token || "no-token"}</div>
      <div data-testid="auth-username">{user?.username || "no-user"}</div>
      <div data-testid="auth-demo-count">{demoUsers.length}</div>

      <button data-testid="btn-login" onClick={() => login({ username_or_email: "analyst@novaenterprise.io", password: "demo_password" })}>
        Login
      </button>
      <button data-testid="btn-switch-admin" onClick={() => switchDemoRole("admin")}>
        Switch to Admin
      </button>
      <button data-testid="btn-switch-viewer" onClick={() => switchDemoRole("viewer")}>
        Switch to Viewer
      </button>
      <button data-testid="btn-logout" onClick={() => logout()}>
        Logout
      </button>

      <div data-testid="check-viewer">{hasRole("viewer") ? "yes" : "no"}</div>
      <div data-testid="check-analyst">{hasRole("analyst") ? "yes" : "no"}</div>
      <div data-testid="check-admin">{hasRole("admin") ? "yes" : "no"}</div>

      <div data-testid="can-research">{canPerform("research") ? "yes" : "no"}</div>
      <div data-testid="can-upload">{canPerform("upload") ? "yes" : "no"}</div>
      <div data-testid="can-cypher">{canPerform("cypher") ? "yes" : "no"}</div>
      <div data-testid="can-delete">{canPerform("delete") ? "yes" : "no"}</div>
      <div data-testid="can-approve">{canPerform("approve") ? "yes" : "no"}</div>
    </div>
  );
}

describe("AuthContext and AuthProvider", () => {
  const mockDemoUsers: DemoUser[] = [
    {
      id: "usr-admin-01",
      username: "admin",
      email: "admin@novaenterprise.io",
      role: "admin",
      name: "Alex Vance (Admin)",
      description: "Full access",
    },
    {
      id: "usr-analyst-01",
      username: "analyst",
      email: "analyst@novaenterprise.io",
      role: "analyst",
      name: "Morgan Reed (Analyst)",
      description: "Research execution",
    },
    {
      id: "usr-viewer-01",
      username: "viewer",
      email: "viewer@novaenterprise.io",
      role: "viewer",
      name: "Taylor Swift (Viewer)",
      description: "Read-only access",
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();

    vi.spyOn(apiClient.auth, "getDemoUsers").mockResolvedValue(mockDemoUsers);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("loads demo users and initializes default state", async () => {
    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId("auth-loading")).toHaveTextContent("ready");
    });

    expect(screen.getByTestId("auth-demo-count")).toHaveTextContent("3");
    expect(screen.getByTestId("auth-role")).toHaveTextContent("analyst");
  });

  it("rehydrates token from localStorage on mount and verifies profile", async () => {
    const mockProfile: UserProfileResponse = {
      id: "usr-admin-01",
      username: "admin",
      email: "admin@novaenterprise.io",
      role: "admin",
      is_active: true,
      created_at: "2026-11-27T10:00:00Z",
    };

    localStorage.setItem("nova_access_token", "saved-admin-jwt");
    vi.spyOn(apiClient.auth, "me").mockResolvedValue(mockProfile);

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId("auth-username")).toHaveTextContent("admin");
    });

    expect(screen.getByTestId("auth-role")).toHaveTextContent("admin");
    expect(screen.getByTestId("auth-token")).toHaveTextContent("saved-admin-jwt");
    expect(screen.getByTestId("auth-status")).toHaveTextContent("authenticated");
  });

  it("switches demo roles, updates tokens and evaluates RBAC permissions correctly", async () => {
    const adminTokenResp: TokenResponse = {
      access_token: "jwt-admin-token",
      token_type: "bearer",
      expires_in: 86400,
      role: "admin",
      user_id: "usr-admin-01",
      email: "admin@novaenterprise.io",
      username: "admin",
    };

    const viewerTokenResp: TokenResponse = {
      access_token: "jwt-viewer-token",
      token_type: "bearer",
      expires_in: 86400,
      role: "viewer",
      user_id: "usr-viewer-01",
      email: "viewer@novaenterprise.io",
      username: "viewer",
    };

    vi.spyOn(apiClient.auth, "getDemoToken").mockImplementation(async (role: UserRole = "analyst") => {
      if (role === "admin") return adminTokenResp;
      return viewerTokenResp;
    });

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId("auth-loading")).toHaveTextContent("ready");
    });

    // Switch to Admin
    act(() => {
      screen.getByTestId("btn-switch-admin").click();
    });

    await waitFor(() => {
      expect(screen.getByTestId("auth-role")).toHaveTextContent("admin");
    });

    expect(screen.getByTestId("auth-token")).toHaveTextContent("jwt-admin-token");
    expect(localStorage.getItem("nova_access_token")).toBe("jwt-admin-token");
    expect(screen.getByTestId("check-viewer")).toHaveTextContent("yes");
    expect(screen.getByTestId("check-analyst")).toHaveTextContent("yes");
    expect(screen.getByTestId("check-admin")).toHaveTextContent("yes");
    expect(screen.getByTestId("can-research")).toHaveTextContent("yes");
    expect(screen.getByTestId("can-upload")).toHaveTextContent("yes");
    expect(screen.getByTestId("can-cypher")).toHaveTextContent("yes");
    expect(screen.getByTestId("can-delete")).toHaveTextContent("yes");
    expect(screen.getByTestId("can-approve")).toHaveTextContent("yes");

    // Switch to Viewer
    act(() => {
      screen.getByTestId("btn-switch-viewer").click();
    });

    await waitFor(() => {
      expect(screen.getByTestId("auth-role")).toHaveTextContent("viewer");
    });

    expect(screen.getByTestId("auth-token")).toHaveTextContent("jwt-viewer-token");
    expect(screen.getByTestId("check-viewer")).toHaveTextContent("yes");
    expect(screen.getByTestId("check-analyst")).toHaveTextContent("no");
    expect(screen.getByTestId("check-admin")).toHaveTextContent("no");
    expect(screen.getByTestId("can-research")).toHaveTextContent("no");
    expect(screen.getByTestId("can-upload")).toHaveTextContent("no");
    expect(screen.getByTestId("can-cypher")).toHaveTextContent("no");
    expect(screen.getByTestId("can-delete")).toHaveTextContent("no");
    expect(screen.getByTestId("can-approve")).toHaveTextContent("no");
  });

  it("handles login with credentials and updates auth profile", async () => {
    const loginTokenResp: TokenResponse = {
      access_token: "jwt-login-token",
      token_type: "bearer",
      expires_in: 86400,
      role: "analyst",
      user_id: "usr-analyst-01",
      email: "analyst@novaenterprise.io",
      username: "analyst",
    };

    const analystProfile: UserProfileResponse = {
      id: "usr-analyst-01",
      username: "analyst",
      email: "analyst@novaenterprise.io",
      role: "analyst",
      is_active: true,
      created_at: "2026-11-27T10:00:00Z",
    };

    vi.spyOn(apiClient.auth, "login").mockResolvedValue(loginTokenResp);
    vi.spyOn(apiClient.auth, "me").mockResolvedValue(analystProfile);

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId("auth-loading")).toHaveTextContent("ready");
    });

    act(() => {
      screen.getByTestId("btn-login").click();
    });

    await waitFor(() => {
      expect(screen.getByTestId("auth-username")).toHaveTextContent("analyst");
    });

    expect(screen.getByTestId("auth-status")).toHaveTextContent("authenticated");
    expect(screen.getByTestId("auth-token")).toHaveTextContent("jwt-login-token");
    expect(localStorage.getItem("nova_access_token")).toBe("jwt-login-token");
  });

  it("clears state and storage on logout", async () => {
    localStorage.setItem("nova_access_token", "existing-token");

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId("auth-loading")).toHaveTextContent("ready");
    });

    act(() => {
      screen.getByTestId("btn-logout").click();
    });

    expect(screen.getByTestId("auth-token")).toHaveTextContent("no-token");
    expect(screen.getByTestId("auth-status")).toHaveTextContent("unauthenticated");
    expect(localStorage.getItem("nova_access_token")).toBeNull();
  });
});
