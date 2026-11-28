/**
 * NovaEnterprise Typed API Client
 * Authoritative client implementation mirroring docs/API_CONTRACT.md (P12-2, Claude.md §11, §12).
 */

import type {
  DemoUser,
  TokenResponse,
  LoginRequest,
  UserProfileResponse,
  CustomerResponse,
  IncidentResponse,
  ServiceResponse,
  TeamResponse,
  DecisionResponse,
  ProjectResponse,
  TicketResponse,
  ResearchCreateRequest,
  ResearchCreateResponse,
  ResearchSessionSummary,
  ResearchSessionResponse,
  WorkflowEventResponse,
  GraphDataResponse,
  GraphExpandResponse,
  CypherQueryRequest,
  CypherQueryResponse,
  DocumentResponse,
  DocumentDetailResponse,
  DocumentUploadResponse,
  DocumentDeleteResponse,
  ApprovalRequestResponse,
  ApprovalDecisionRequest,
  ApprovalDecisionResponse,
  HealthResponse,
  ReadinessResponse,
  PaginationParams,
  CustomerFilterParams,
  IncidentFilterParams,
  ApprovalFilterParams,
  UserRole,
} from "../types/api";

export class ApiClientError extends Error {
  public readonly statusCode: number;
  public readonly url: string;
  public readonly detail: unknown;
  public readonly requestId?: string;
  public readonly rateLimitReset?: number;
  public readonly rawHeaders: Headers;

  constructor(
    message: string,
    statusCode: number,
    url: string,
    detail: unknown,
    headers: Headers
  ) {
    super(message);
    this.name = "ApiClientError";
    this.statusCode = statusCode;
    this.url = url;
    this.detail = detail;
    this.rawHeaders = headers;

    const reqId = headers.get("X-Request-ID");
    if (reqId) {
      this.requestId = reqId;
    }

    const reset = headers.get("X-RateLimit-Reset");
    if (reset) {
      this.rateLimitReset = parseInt(reset, 10);
    }
  }
}

export interface ApiClientConfig {
  baseUrl?: string;
  token?: string | null;
  headers?: Record<string, string>;
}

function generateRequestId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `req-${Math.random().toString(36).substring(2, 10)}-${Date.now()}`;
}

function buildQueryString(params?: Record<string, unknown>): string {
  if (!params) return "";
  const query = new URLSearchParams();
  for (const [key, val] of Object.entries(params)) {
    if (val !== undefined && val !== null && val !== "") {
      query.set(key, String(val));
    }
  }
  const str = query.toString();
  return str ? `?${str}` : "";
}

export class ApiClient {
  private baseUrl: string;
  private token: string | null = null;
  private defaultHeaders: Record<string, string>;

  constructor(config: ApiClientConfig = {}) {
    this.baseUrl = (config.baseUrl || "http://localhost:8001/api/v1").replace(
      /\/$/,
      ""
    );
    this.token = config.token || null;
    this.defaultHeaders = config.headers || {};
  }

  public setToken(token: string | null): void {
    this.token = token;
  }

  public clearToken(): void {
    this.token = null;
  }

  public getToken(): string | null {
    return this.token;
  }

  public getBaseUrl(): string {
    return this.baseUrl;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {},
    isUnprefixed: boolean = false
  ): Promise<T> {
    const url = isUnprefixed
      ? `${this.baseUrl.replace(/\/api\/v1$/, "")}${endpoint}`
      : `${this.baseUrl}${endpoint}`;

    const headers: Record<string, string> = {
      Accept: "application/json",
      "X-Request-ID": generateRequestId(),
      ...this.defaultHeaders,
    };

    if (this.token) {
      headers["Authorization"] = `Bearer ${this.token}`;
    }

    if (
      !(options.body instanceof FormData) &&
      !headers["Content-Type"] &&
      options.method &&
      options.method !== "GET"
    ) {
      headers["Content-Type"] = "application/json";
    }

    // Merge options.headers if passed
    if (options.headers) {
      if (options.headers instanceof Headers) {
        options.headers.forEach((v, k) => {
          headers[k] = v;
        });
      } else if (Array.isArray(options.headers)) {
        for (const [k, v] of options.headers) {
          headers[k] = v;
        }
      } else {
        Object.assign(headers, options.headers);
      }
    }

    const response = await fetch(url, {
      ...options,
      headers,
    });

    if (!response.ok) {
      let errorDetail: unknown = null;
      try {
        const errorJson = await response.json();
        errorDetail = errorJson.detail || errorJson;
      } catch {
        errorDetail = await response.text();
      }

      const detailMsg =
        typeof errorDetail === "string"
          ? errorDetail
          : JSON.stringify(errorDetail);

      throw new ApiClientError(
        `API error [${response.status}] on ${options.method || "GET"} ${url}: ${detailMsg}`,
        response.status,
        url,
        errorDetail,
        response.headers
      );
    }

    if (response.status === 204) {
      return {} as T;
    }

    return (await response.json()) as T;
  }

  // =========================================================================
  // Health & Readiness Probes (Unprefixed /health, /health/ready)
  // =========================================================================

  public readonly health = {
    check: async (): Promise<HealthResponse> => {
      return this.request<HealthResponse>("/health", { method: "GET" }, true);
    },
    ready: async (): Promise<ReadinessResponse> => {
      return this.request<ReadinessResponse>(
        "/health/ready",
        { method: "GET" },
        true
      );
    },
  };

  // =========================================================================
  // Authentication & Identity (/api/v1/auth)
  // =========================================================================

  public readonly auth = {
    getDemoUsers: async (): Promise<DemoUser[]> => {
      return this.request<DemoUser[]>("/auth/demo-users", { method: "GET" });
    },
    getDemoToken: async (role: UserRole = "analyst"): Promise<TokenResponse> => {
      return this.request<TokenResponse>("/auth/demo-token", {
        method: "POST",
        body: JSON.stringify({ role }),
      });
    },
    login: async (credentials: LoginRequest): Promise<TokenResponse> => {
      return this.request<TokenResponse>("/auth/login", {
        method: "POST",
        body: JSON.stringify(credentials),
      });
    },
    me: async (): Promise<UserProfileResponse> => {
      return this.request<UserProfileResponse>("/auth/me", { method: "GET" });
    },
  };

  // =========================================================================
  // Research Engine & Observability (/api/v1/research)
  // =========================================================================

  public readonly research = {
    create: async (
      req: ResearchCreateRequest
    ): Promise<ResearchCreateResponse> => {
      return this.request<ResearchCreateResponse>("/research", {
        method: "POST",
        body: JSON.stringify(req),
      });
    },
    list: async (
      params?: PaginationParams
    ): Promise<ResearchSessionSummary[]> => {
      const qs = buildQueryString(params as Record<string, unknown>);
      return this.request<ResearchSessionSummary[]>(`/research${qs}`, {
        method: "GET",
      });
    },
    get: async (sessionId: string): Promise<ResearchSessionResponse> => {
      return this.request<ResearchSessionResponse>(
        `/research/${encodeURIComponent(sessionId)}`,
        { method: "GET" }
      );
    },
    getEvents: async (
      sessionId: string,
      sinceEventId?: number
    ): Promise<WorkflowEventResponse[]> => {
      const qs = sinceEventId ? `?since_id=${sinceEventId}` : "";
      return this.request<WorkflowEventResponse[]>(
        `/research/${encodeURIComponent(sessionId)}/events${qs}`,
        { method: "GET" }
      );
    },
  };

  // =========================================================================
  // Domain Browse Entities (/api/v1/...)
  // =========================================================================

  public readonly customers = {
    list: async (
      params?: CustomerFilterParams
    ): Promise<CustomerResponse[]> => {
      const qs = buildQueryString(params as Record<string, unknown>);
      return this.request<CustomerResponse[]>(`/customers${qs}`, {
        method: "GET",
      });
    },
    get: async (id: string): Promise<CustomerResponse> => {
      return this.request<CustomerResponse>(
        `/customers/${encodeURIComponent(id)}`,
        { method: "GET" }
      );
    },
  };

  public readonly incidents = {
    list: async (
      params?: IncidentFilterParams
    ): Promise<IncidentResponse[]> => {
      const qs = buildQueryString(params as Record<string, unknown>);
      return this.request<IncidentResponse[]>(`/incidents${qs}`, {
        method: "GET",
      });
    },
    get: async (id: string): Promise<IncidentResponse> => {
      return this.request<IncidentResponse>(
        `/incidents/${encodeURIComponent(id)}`,
        { method: "GET" }
      );
    },
  };

  public readonly services = {
    list: async (params?: PaginationParams): Promise<ServiceResponse[]> => {
      const qs = buildQueryString(params as Record<string, unknown>);
      return this.request<ServiceResponse[]>(`/services${qs}`, {
        method: "GET",
      });
    },
    get: async (id: string): Promise<ServiceResponse> => {
      return this.request<ServiceResponse>(
        `/services/${encodeURIComponent(id)}`,
        { method: "GET" }
      );
    },
  };

  public readonly teams = {
    list: async (params?: PaginationParams): Promise<TeamResponse[]> => {
      const qs = buildQueryString(params as Record<string, unknown>);
      return this.request<TeamResponse[]>(`/teams${qs}`, { method: "GET" });
    },
    get: async (id: string): Promise<TeamResponse> => {
      return this.request<TeamResponse>(`/teams/${encodeURIComponent(id)}`, {
        method: "GET",
      });
    },
  };

  public readonly decisions = {
    list: async (params?: PaginationParams): Promise<DecisionResponse[]> => {
      const qs = buildQueryString(params as Record<string, unknown>);
      return this.request<DecisionResponse[]>(`/decisions${qs}`, {
        method: "GET",
      });
    },
    get: async (id: string): Promise<DecisionResponse> => {
      return this.request<DecisionResponse>(
        `/decisions/${encodeURIComponent(id)}`,
        { method: "GET" }
      );
    },
  };

  public readonly projects = {
    list: async (params?: PaginationParams): Promise<ProjectResponse[]> => {
      const qs = buildQueryString(params as Record<string, unknown>);
      return this.request<ProjectResponse[]>(`/projects${qs}`, {
        method: "GET",
      });
    },
    get: async (id: string): Promise<ProjectResponse> => {
      return this.request<ProjectResponse>(
        `/projects/${encodeURIComponent(id)}`,
        { method: "GET" }
      );
    },
  };

  public readonly tickets = {
    list: async (params?: PaginationParams): Promise<TicketResponse[]> => {
      const qs = buildQueryString(params as Record<string, unknown>);
      return this.request<TicketResponse[]>(`/tickets${qs}`, { method: "GET" });
    },
    get: async (id: string): Promise<TicketResponse> => {
      return this.request<TicketResponse>(
        `/tickets/${encodeURIComponent(id)}`,
        { method: "GET" }
      );
    },
  };

  // =========================================================================
  // Knowledge Graph Explorer (/api/v1/graph)
  // =========================================================================

  public readonly graph = {
    getGraph: async (params?: { limit?: number }): Promise<GraphDataResponse> => {
      const qs = buildQueryString(params);
      return this.request<GraphDataResponse>(`/graph${qs}`, { method: "GET" });
    },
    expand: async (
      nodeId: string,
      depth: number = 1
    ): Promise<GraphExpandResponse> => {
      return this.request<GraphExpandResponse>(
        `/graph/expand/${encodeURIComponent(nodeId)}?depth=${depth}`,
        { method: "GET" }
      );
    },
    queryCypher: async (
      req: CypherQueryRequest
    ): Promise<CypherQueryResponse> => {
      return this.request<CypherQueryResponse>("/graph/query", {
        method: "POST",
        body: JSON.stringify(req),
      });
    },
  };

  // =========================================================================
  // Document Ingestion & Management (/api/v1/documents)
  // =========================================================================

  public readonly documents = {
    upload: async (file: File): Promise<DocumentUploadResponse> => {
      const formData = new FormData();
      formData.append("file", file);
      return this.request<DocumentUploadResponse>("/documents/upload", {
        method: "POST",
        body: formData,
      });
    },
    list: async (params?: PaginationParams): Promise<DocumentResponse[]> => {
      const qs = buildQueryString(params as Record<string, unknown>);
      return this.request<DocumentResponse[]>(`/documents${qs}`, {
        method: "GET",
      });
    },
    get: async (id: string): Promise<DocumentDetailResponse> => {
      return this.request<DocumentDetailResponse>(
        `/documents/${encodeURIComponent(id)}`,
        { method: "GET" }
      );
    },
    delete: async (id: string): Promise<DocumentDeleteResponse> => {
      return this.request<DocumentDeleteResponse>(
        `/documents/${encodeURIComponent(id)}`,
        { method: "DELETE" }
      );
    },
  };

  // =========================================================================
  // Governance & Approvals (/api/v1/approvals)
  // =========================================================================

  public readonly approvals = {
    list: async (
      params?: ApprovalFilterParams
    ): Promise<ApprovalRequestResponse[]> => {
      const qs = buildQueryString(params as Record<string, unknown>);
      return this.request<ApprovalRequestResponse[]>(`/approvals${qs}`, {
        method: "GET",
      });
    },
    get: async (id: string): Promise<ApprovalRequestResponse> => {
      return this.request<ApprovalRequestResponse>(
        `/approvals/${encodeURIComponent(id)}`,
        { method: "GET" }
      );
    },
    decide: async (
      id: string,
      req: ApprovalDecisionRequest
    ): Promise<ApprovalDecisionResponse> => {
      const payload = {
        decision: req.decision || (req.status as string) || "approved",
        reason: req.reason || req.decision_notes || undefined,
      };
      return this.request<ApprovalDecisionResponse>(
        `/approvals/${encodeURIComponent(id)}/decide`,
        {
          method: "POST",
          body: JSON.stringify(payload),
        }
      );
    },
  };
}

// Global default singleton instance
let defaultApiClient: ApiClient | null = null;

export function getApiClient(config?: ApiClientConfig): ApiClient {
  if (config) {
    return new ApiClient(config);
  }
  if (!defaultApiClient) {
    const envBaseUrl =
      typeof process !== "undefined" && process.env?.NEXT_PUBLIC_API_URL
        ? process.env.NEXT_PUBLIC_API_URL
        : "/api/v1";
    defaultApiClient = new ApiClient({ baseUrl: envBaseUrl });
  }
  return defaultApiClient;
}

export const apiClient: ApiClient = getApiClient();

