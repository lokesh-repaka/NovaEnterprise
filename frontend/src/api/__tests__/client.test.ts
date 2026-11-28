import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { ApiClient, ApiClientError } from "../client";
import type {
  ResearchSessionResponse,
  CustomerResponse,
  IncidentResponse,
  GraphDataResponse,
  TokenResponse,
  ApprovalDecisionResponse,
} from "../../types/api";

describe("Typed API Client (P12-2, docs/API_CONTRACT.md)", () => {
  let client: ApiClient;
  const mockFetch = vi.fn();

  beforeEach(() => {
    vi.stubGlobal("fetch", mockFetch);
    client = new ApiClient({
      baseUrl: "http://localhost:8001/api/v1",
      token: "test-analyst-token",
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe("Global Headers & Traceability (N5)", () => {
    it("injects Authorization and X-Request-ID headers on outgoing requests", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ "X-Request-ID": "req-123" }),
        json: async () => ({ id: "cust-1", name: "Acme Corp" }),
      });

      await client.customers.get("cust-1");

      expect(mockFetch).toHaveBeenCalledTimes(1);
      const [url, options] = mockFetch.mock.calls[0];
      expect(url).toBe("http://localhost:8001/api/v1/customers/cust-1");
      expect(options.headers["Authorization"]).toBe("Bearer test-analyst-token");
      expect(options.headers["X-Request-ID"]).toBeDefined();
    });

    it("allows updating the authorization token dynamically", async () => {
      client.setToken("admin-jwt-token");
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers(),
        json: async () => ({ id: "admin-1", role: "admin" }),
      });

      await client.auth.me();
      const [, options] = mockFetch.mock.calls[0];
      expect(options.headers["Authorization"]).toBe("Bearer admin-jwt-token");
    });
  });

  describe("Health & Readiness Probes", () => {
    it("fetches /health and /health/ready without prefix", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers(),
        json: async () => ({ status: "ok" }),
      });

      const health = await client.health.check();
      expect(health.status).toBe("ok");
      expect(mockFetch.mock.calls[0][0]).toBe("http://localhost:8001/health");

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers(),
        json: async () => ({ status: "ready", stores: { database: "sqlite" } }),
      });

      const ready = await client.health.ready();
      expect(ready.status).toBe("ready");
      expect(mockFetch.mock.calls[1][0]).toBe("http://localhost:8001/health/ready");
    });
  });

  describe("Authentication & Demo Users", () => {
    it("fetches demo users and issues demo tokens", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers(),
        json: async () => [
          { username: "analyst", role: "analyst", email: "analyst@novaenterprise.io" },
        ],
      });

      const users = await client.auth.getDemoUsers();
      expect(users).toHaveLength(1);
      expect(users[0].role).toBe("analyst");

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers(),
        json: async () => ({
          access_token: "mock-jwt-token",
          token_type: "bearer",
          role: "analyst",
          user_id: "usr-analyst",
        }),
      });

      const tokenResp = await client.auth.getDemoToken("analyst");
      expect(tokenResp.access_token).toBe("mock-jwt-token");
      expect(tokenResp.role).toBe("analyst");
    });
  });

  describe("Research Workflow Lifecycle (F1, F16)", () => {
    it("creates research session returning 202 Accepted", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 202,
        headers: new Headers({ "X-Request-ID": "req-res-1" }),
        json: async () => ({
          session_id: "sess-abc-123",
          status: "running",
          question: "Which customers were impacted by Payments API?",
          created_at: "2026-11-28T09:00:00Z",
        }),
      });

      const res = await client.research.create({
        question: "Which customers were impacted by Payments API?",
      });

      expect(res.session_id).toBe("sess-abc-123");
      expect(res.status).toBe("running");
      const [url, options] = mockFetch.mock.calls[0];
      expect(url).toBe("http://localhost:8001/api/v1/research");
      expect(options.method).toBe("POST");
    });

    it("polls research session state and telemetry events", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers(),
        json: async () => ({
          session_id: "sess-abc-123",
          status: "completed",
          question: "What caused outage?",
          complexity: "complex",
          strategies_used: ["graph", "sql", "vector"],
          corrective_rounds: 0,
          verification_ratio: 1.0,
          answer: "Downstream timeouts occurred [1].",
          citations: [{ citation_id: 1, locator: "doc:pm-1" }],
        }),
      });

      const session = await client.research.get("sess-abc-123");
      expect(session.status).toBe("completed");
      expect(session.answer).toContain("[1]");

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers(),
        json: async () => [
          { event_id: 1, node_name: "analyze_query", event_type: "node_complete" },
        ],
      });

      const events = await client.research.getEvents("sess-abc-123");
      expect(events).toHaveLength(1);
      expect(events[0].node_name).toBe("analyze_query");
    });
  });

  describe("Knowledge Graph API", () => {
    it("fetches topology, node expansions, and executes Cypher queries", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers(),
        json: async () => ({
          nodes: [{ id: "svc-payments", label: "Service", properties: { name: "Payments API" } }],
          edges: [],
        }),
      });

      const graphData = await client.graph.getGraph({ limit: 50 });
      expect(graphData.nodes).toHaveLength(1);

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers(),
        json: async () => ({
          results: [{ service: "Payments API" }],
          execution_time_ms: 12,
          nodes: [],
          edges: [],
        }),
      });

      const cypherRes = await client.graph.queryCypher({
        query: "MATCH (s:Service) RETURN s.name as service",
      });
      expect(cypherRes.results[0].service).toBe("Payments API");
    });
  });

  describe("Documents & Governance Approvals (F17)", () => {
    it("handles document upload via multipart form-data", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 201,
        headers: new Headers(),
        json: async () => ({
          id: "doc-uuid-1",
          filename: "postmortem.md",
          chunk_count: 3,
          flagged_injection: false,
          status: "indexed",
        }),
      });

      const blob = new Blob(["# Postmortem"], { type: "text/markdown" });
      const file = new File([blob], "postmortem.md", { type: "text/markdown" });

      const uploaded = await client.documents.upload(file);
      expect(uploaded.id).toBe("doc-uuid-1");
      expect(uploaded.chunk_count).toBe(3);
    });

    it("handles analyst document delete returning 202 pending approval", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 202,
        headers: new Headers(),
        json: async () => ({
          status: "pending_approval",
          approval_request_id: "appr-req-123",
          message: "Deletion request submitted for admin approval.",
        }),
      });

      const deleteResp = await client.documents.delete("doc-uuid-1");
      expect(deleteResp.status).toBe("pending_approval");
      if ("approval_request_id" in deleteResp) {
        expect(deleteResp.approval_request_id).toBe("appr-req-123");
      }
    });

    it("handles admin approval decision execution", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers(),
        json: async () => ({
          id: "appr-req-123",
          status: "approved",
          decided_by: "admin",
          decided_at: "2026-11-28T09:15:00Z",
          message: "Approval request approved.",
        }),
      });

      const decision = await client.approvals.decide("appr-req-123", {
        status: "approved",
        decision_notes: "Approved after audit.",
      });

      expect(decision.status).toBe("approved");
      expect(decision.decided_by).toBe("admin");
    });
  });

  describe("Error Handling & Status Codes", () => {
    it("throws ApiClientError on 401 Unauthorized", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 401,
        headers: new Headers({ "X-Request-ID": "err-trace-401" }),
        json: async () => ({ detail: "Not authenticated" }),
      });

      await expect(client.auth.me()).rejects.toThrow(ApiClientError);
    });

    it("captures rate-limit headers on 429 Too Many Requests", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 429,
        headers: new Headers({
          "X-Request-ID": "err-trace-429",
          "X-RateLimit-Reset": "1732788000",
        }),
        json: async () => ({ detail: "Rate limit exceeded" }),
      });

      try {
        await client.research.create({ question: "spam question" });
        expect.fail("Should have thrown ApiClientError");
      } catch (err) {
        expect(err).toBeInstanceOf(ApiClientError);
        const apiErr = err as ApiClientError;
        expect(apiErr.statusCode).toBe(429);
        expect(apiErr.rateLimitReset).toBe(1732788000);
      }
    });
  });
});
