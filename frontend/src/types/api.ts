// ==========================================
// NovaEnterprise Client TypeScript Types
// Mirror of docs/API_CONTRACT.md (P12-2, Claude.md §12)
// ==========================================

export type UserRole = "viewer" | "analyst" | "admin";

export interface DemoUser {
  id: string;
  username: string;
  email: string;
  role: UserRole;
  name: string;
  description: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  role: UserRole;
  user_id: string;
  email: string;
  username: string;
}

export interface LoginRequest {
  username_or_email: string;
  password?: string;
  username?: string;
}

export interface UserProfileResponse {
  id: string;
  username: string;
  email: string;
  role: UserRole;
  is_active: boolean;
  created_at: string | null;
}

// ------------------------------------------
// Domain Browse Entities
// ------------------------------------------

export interface CustomerResponse {
  id: string;
  name: string;
  tier: "enterprise" | "mid-market" | "standard" | "smb";
  contract_value: number;
  industry: string | null;
  created_at: string;
}

export interface IncidentResponse {
  id: string;
  title: string;
  severity: "SEV1" | "SEV2" | "SEV3" | "SEV4";
  status: "investigating" | "mitigated" | "resolved";
  root_cause: string | null;
  impacted_service_id: string | null;
  occurred_at: string | null;
  resolved_at: string | null;
  created_at: string;
}

export interface ServiceResponse {
  id: string;
  name: string;
  tier: string;
  port: number | null;
  repo_url: string | null;
  owner_team_id: string | null;
  created_at: string;
}

export interface TeamResponse {
  id: string;
  name: string;
  lead: string | null;
  slack_channel: string | null;
  description: string | null;
  created_at: string;
}

export interface DecisionResponse {
  id: string;
  title: string;
  status: "proposed" | "accepted" | "superseded" | "rejected";
  context: string | null;
  decision: string | null;
  consequences: string | null;
  incident_id: string | null;
  decided_at: string | null;
  created_at: string;
}

export interface ProjectResponse {
  id: string;
  name: string;
  description: string | null;
  owner_team_id: string | null;
  status: "active" | "completed" | "archived";
  created_at: string;
}

export interface TicketResponse {
  id: string;
  title: string;
  status: "open" | "in_progress" | "resolved" | "closed";
  priority: "P0" | "P1" | "P2" | "P3";
  project_id: string | null;
  assignee_id: string | null;
  created_at: string;
}

// ------------------------------------------
// Canonical Evidence & Citations
// ------------------------------------------

export type EvidenceSourceType = "document" | "sql" | "graph";

export interface EvidenceItem {
  id: string;
  sub_question_id: string;
  source_type: EvidenceSourceType;
  locator: string;
  content: string;
  score: number;
  metadata: Record<string, unknown>;
}

export interface CitationItem {
  citation_id: number;
  evidence_id: string;
  source_type: EvidenceSourceType;
  locator: string;
  snippet: string;
}

export interface SubQuestionItem {
  id: string;
  question: string;
  strategy: string;
  status: "pending" | "answered" | "failed";
}

// ------------------------------------------
// Research Session & Observability
// ------------------------------------------

export type ResearchStatus = "running" | "completed" | "failed";
export type QueryComplexity = "simple" | "moderate" | "complex";

export interface ResearchCreateRequest {
  question: string;
  user_id?: string;
}

export interface ResearchCreateResponse {
  session_id: string;
  status: "running";
  question: string;
  created_at: string;
}

export interface ResearchSessionSummary {
  session_id: string;
  question: string;
  status: ResearchStatus;
  complexity: QueryComplexity | null;
  created_at: string;
  updated_at: string;
}

export interface ResearchSessionResponse {
  session_id: string;
  status: ResearchStatus;
  question: string;
  complexity: QueryComplexity | null;
  strategies_used: string[];
  corrective_rounds: number;
  verification_ratio: number;
  answer: string | null;
  citations: CitationItem[];
  evidence: EvidenceItem[];
  sub_questions: SubQuestionItem[];
  execution_time_seconds: number | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface WorkflowEventResponse {
  event_id: number;
  session_id: string;
  node_name: string;
  event_type: string;
  payload: Record<string, unknown>;
  latency_ms: number | null;
  timestamp: string;
}

// ------------------------------------------
// Knowledge Graph Explorer
// ------------------------------------------

export interface GraphNode {
  id: string;
  label: string;
  properties: Record<string, unknown>;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: string;
  properties: Record<string, unknown>;
}

export interface GraphDataResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface CypherQueryRequest {
  query: string;
  parameters?: Record<string, unknown>;
}

export interface CypherQueryResponse {
  results: Record<string, unknown>[];
  execution_time_ms: number;
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface GraphExpandResponse {
  center_node: GraphNode;
  neighbors: GraphNode[];
  edges: GraphEdge[];
}

// ------------------------------------------
// Document & Approval Governance (F17)
// ------------------------------------------

export interface DocumentResponse {
  id: string;
  filename: string;
  content_hash: string;
  chunk_count: number;
  flagged_injection: boolean;
  status: "indexed" | "pending" | "flagged";
  created_at: string;
}

export interface DocumentChunkResponse {
  id: string;
  chunk_index: number;
  text: string;
  embedding_id: string | null;
}

export interface DocumentDetailResponse extends DocumentResponse {
  chunks: DocumentChunkResponse[];
}

export interface DocumentUploadResponse extends DocumentResponse {
  message?: string;
}

export interface DocumentDeletePendingResponse {
  status: "pending_approval";
  approval_request_id: string;
  message: string;
}

export interface DocumentDeleteExecutedResponse {
  status: "deleted";
  deleted_chunks_count: number;
}

export type DocumentDeleteResponse =
  | DocumentDeletePendingResponse
  | DocumentDeleteExecutedResponse;

export interface ApprovalRequestResponse {
  id: string;
  requester_id: string;
  action: string;
  resource_type: string;
  resource_id: string;
  payload?: Record<string, unknown>;
  status: "pending" | "approved" | "rejected";
  decided_by: string | null;
  decision_notes?: string | null;
  created_at: string;
  decided_at?: string | null;
}

export interface ApprovalDecisionRequest {
  status: "approved" | "rejected";
  decision_notes?: string;
}

export interface ApprovalDecisionResponse {
  id: string;
  status: "approved" | "rejected";
  decided_by: string;
  decided_at: string;
  message?: string;
  execution_result?: Record<string, unknown>;
}

// ------------------------------------------
// Health Probes & Common Error Types
// ------------------------------------------

export interface HealthResponse {
  status: string;
}

export interface ReadinessResponse {
  status: "ready" | "degraded" | "unhealthy";
  stores: Record<string, unknown>;
}

export interface ApiErrorResponse {
  detail: string | unknown[];
}

// ------------------------------------------
// Filter & Pagination Query Parameters
// ------------------------------------------

export interface PaginationParams {
  skip?: number;
  limit?: number;
}

export interface CustomerFilterParams extends PaginationParams {
  tier?: string;
}

export interface IncidentFilterParams extends PaginationParams {
  severity?: string;
  status?: string;
}

export interface ApprovalFilterParams extends PaginationParams {
  status?: "pending" | "approved" | "rejected";
}
