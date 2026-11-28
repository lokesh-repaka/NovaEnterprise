"use client";

import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  useMemo,
} from "react";
import { apiClient } from "@/api/client";
import type {
  UserRole,
  DemoUser,
  LoginRequest,
  TokenResponse,
  UserProfileResponse,
} from "@/types/api";

const TOKEN_STORAGE_KEY = "nova_access_token";

export type RoleAction =
  | "research"
  | "upload"
  | "cypher"
  | "delete"
  | "reindex"
  | "approve";

export const ROLE_HIERARCHY: Record<UserRole, number> = {
  viewer: 1,
  analyst: 2,
  admin: 3,
};

// Authoritative permissions mapping matching Claude.md §2 & line 380
const ACTION_PERMISSIONS: Record<RoleAction, UserRole> = {
  research: "analyst",
  upload: "analyst",
  cypher: "analyst",
  delete: "admin",
  reindex: "admin",
  approve: "admin",
};

export const FALLBACK_DEMO_USERS: DemoUser[] = [
  {
    id: "usr-admin-01",
    username: "admin",
    email: "admin@novaenterprise.io",
    role: "admin",
    name: "Alex Vance (Admin)",
    description: "Full access: approval workflow, reindex, delete",
  },
  {
    id: "usr-analyst-01",
    username: "analyst",
    email: "analyst@novaenterprise.io",
    role: "analyst",
    name: "Morgan Reed (Analyst)",
    description: "Research execution, document upload, Cypher explorer",
  },
  {
    id: "usr-viewer-01",
    username: "viewer",
    email: "viewer@novaenterprise.io",
    role: "viewer",
    name: "Taylor Swift (Viewer)",
    description: "Read-only access to dashboards, browse entities, citations",
  },
];

export interface AuthContextType {
  user: UserProfileResponse | null;
  token: string | null;
  role: UserRole;
  demoUsers: DemoUser[];
  isLoading: boolean;
  isAuthenticated: boolean;
  error: string | null;
  login: (credentials: LoginRequest) => Promise<void>;
  switchDemoRole: (role: UserRole) => Promise<void>;
  logout: () => void;
  hasRole: (requiredRole: UserRole) => boolean;
  canPerform: (action: RoleAction) => boolean;
  refreshProfile: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserProfileResponse | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [role, setRole] = useState<UserRole>("analyst");
  const [demoUsers, setDemoUsers] = useState<DemoUser[]>(FALLBACK_DEMO_USERS);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Check if role level is sufficient for required role
  const hasRole = useCallback(
    (requiredRole: UserRole): boolean => {
      return (ROLE_HIERARCHY[role] ?? 0) >= (ROLE_HIERARCHY[requiredRole] ?? 0);
    },
    [role]
  );

  // Check if current role has permission for specific action
  const canPerform = useCallback(
    (action: RoleAction): boolean => {
      const requiredRole = ACTION_PERMISSIONS[action];
      if (!requiredRole) return false;
      return hasRole(requiredRole);
    },
    [hasRole]
  );

  // Refresh user profile from backend
  const refreshProfile = useCallback(async () => {
    try {
      const profile = await apiClient.auth.me();
      setUser(profile);
      setRole(profile.role);
      setError(null);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to fetch user profile";
      setError(message);
    }
  }, []);

  // Login with credentials
  const login = useCallback(
    async (credentials: LoginRequest) => {
      setIsLoading(true);
      setError(null);
      try {
        const resp: TokenResponse = await apiClient.auth.login(credentials);
        setToken(resp.access_token);
        setRole(resp.role);
        apiClient.setToken(resp.access_token);

        if (typeof window !== "undefined") {
          localStorage.setItem(TOKEN_STORAGE_KEY, resp.access_token);
        }

        // Fetch complete profile or populate from token
        try {
          const profile = await apiClient.auth.me();
          setUser(profile);
        } catch {
          setUser({
            id: resp.user_id,
            username: resp.username,
            email: resp.email,
            role: resp.role,
            is_active: true,
            created_at: new Date().toISOString(),
          });
        }
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : "Login failed";
        setError(message);
        throw err;
      } finally {
        setIsLoading(false);
      }
    },
    []
  );

  // Switch demo persona
  const switchDemoRole = useCallback(
    async (newRole: UserRole) => {
      setIsLoading(true);
      setError(null);
      try {
        const resp: TokenResponse = await apiClient.auth.getDemoToken(newRole);
        setToken(resp.access_token);
        setRole(resp.role);
        apiClient.setToken(resp.access_token);

        if (typeof window !== "undefined") {
          localStorage.setItem(TOKEN_STORAGE_KEY, resp.access_token);
        }

        // Try getting profile or use demo user info
        const matchingDemo = demoUsers.find((u) => u.role === newRole);
        setUser({
          id: resp.user_id || matchingDemo?.id || `usr-${newRole}-01`,
          username: resp.username || matchingDemo?.username || newRole,
          email: resp.email || matchingDemo?.email || `${newRole}@novaenterprise.io`,
          role: resp.role,
          is_active: true,
          created_at: new Date().toISOString(),
        });
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : "Failed to switch demo role";
        setError(message);
        throw err;
      } finally {
        setIsLoading(false);
      }
    },
    [demoUsers]
  );

  // Logout
  const logout = useCallback(() => {
    apiClient.clearToken();
    if (typeof window !== "undefined") {
      localStorage.removeItem(TOKEN_STORAGE_KEY);
    }
    setToken(null);
    setUser(null);
    setRole("viewer");
    setError(null);
  }, []);

  // Initialize Auth state & load demo users on mount
  useEffect(() => {
    let isMounted = true;

    async function initAuth() {
      try {
        // Load demo users
        try {
          const users = await apiClient.auth.getDemoUsers();
          if (isMounted && users && users.length > 0) {
            setDemoUsers(users);
          }
        } catch {
          // Fall back gracefully to static demo users
        }

        // Check for stored token
        const savedToken =
          typeof window !== "undefined"
            ? localStorage.getItem(TOKEN_STORAGE_KEY)
            : null;

        if (savedToken) {
          apiClient.setToken(savedToken);
          setToken(savedToken);

          try {
            const profile = await apiClient.auth.me();
            if (isMounted) {
              setUser(profile);
              setRole(profile.role);
            }
          } catch {
            // Token expired or invalid
            apiClient.clearToken();
            if (typeof window !== "undefined") {
              localStorage.removeItem(TOKEN_STORAGE_KEY);
            }
            if (isMounted) {
              setToken(null);
              setUser(null);
              setRole("analyst");
            }
          }
        } else {
          if (isMounted) {
            setRole("analyst");
          }
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    initAuth();

    return () => {
      isMounted = false;
    };
  }, []);

  const value = useMemo<AuthContextType>(
    () => ({
      user,
      token,
      role,
      demoUsers,
      isLoading,
      isAuthenticated: Boolean(token),
      error,
      login,
      switchDemoRole,
      logout,
      hasRole,
      canPerform,
      refreshProfile,
    }),
    [
      user,
      token,
      role,
      demoUsers,
      isLoading,
      error,
      login,
      switchDemoRole,
      logout,
      hasRole,
      canPerform,
      refreshProfile,
    ]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}

export function useOptionalAuth(): AuthContextType | null {
  try {
    return useAuth();
  } catch {
    return null;
  }
}
