-- ==============================================================================
-- NovaEnterprise Supabase Row-Level Security (RLS) Policies
-- ==============================================================================
-- Enforces multi-tenant security, role-based access control (RBAC), and append-only
-- audit constraints per Claude.md §9, §10 and docs/LLD.md §3.
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- 1. Enable Row-Level Security on All 16 Tables
-- ------------------------------------------------------------------------------
ALTER TABLE teams ENABLE ROW LEVEL SECURITY;
ALTER TABLE employees ENABLE ROW LEVEL SECURITY;
ALTER TABLE services ENABLE ROW LEVEL SECURITY;
ALTER TABLE customers ENABLE ROW LEVEL SECURITY;
ALTER TABLE incidents ENABLE ROW LEVEL SECURITY;
ALTER TABLE decisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE tickets ENABLE ROW LEVEL SECURITY;
ALTER TABLE research_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE citation_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE approval_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;

-- ------------------------------------------------------------------------------
-- 2. Service Role Bypass (Backend FastAPI Server-Side Operations)
-- ------------------------------------------------------------------------------
-- The backend uses the service-role key server-side only (Claude.md §9).
CREATE POLICY service_role_all_teams ON teams FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY service_role_all_employees ON employees FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY service_role_all_services ON services FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY service_role_all_customers ON customers FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY service_role_all_incidents ON incidents FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY service_role_all_decisions ON decisions FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY service_role_all_projects ON projects FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY service_role_all_tickets ON tickets FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY service_role_all_research_sessions ON research_sessions FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY service_role_all_workflow_events ON workflow_events FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY service_role_all_citation_records ON citation_records FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY service_role_all_documents ON documents FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY service_role_all_document_chunks ON document_chunks FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY service_role_all_approval_requests ON approval_requests FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY service_role_all_users ON users FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY service_role_insert_audit ON audit_logs FOR INSERT TO service_role WITH CHECK (true);
CREATE POLICY service_role_select_audit ON audit_logs FOR SELECT TO service_role USING (true);

-- ------------------------------------------------------------------------------
-- 3. Viewer Role Policies (Read-Only Access to Browse Entities - F14)
-- ------------------------------------------------------------------------------
CREATE POLICY viewer_select_teams ON teams FOR SELECT TO authenticated
    USING ((auth.jwt() ->> 'role') IN ('viewer', 'analyst', 'admin'));

CREATE POLICY viewer_select_employees ON employees FOR SELECT TO authenticated
    USING ((auth.jwt() ->> 'role') IN ('viewer', 'analyst', 'admin'));

CREATE POLICY viewer_select_services ON services FOR SELECT TO authenticated
    USING ((auth.jwt() ->> 'role') IN ('viewer', 'analyst', 'admin'));

CREATE POLICY viewer_select_customers ON customers FOR SELECT TO authenticated
    USING ((auth.jwt() ->> 'role') IN ('viewer', 'analyst', 'admin'));

CREATE POLICY viewer_select_incidents ON incidents FOR SELECT TO authenticated
    USING ((auth.jwt() ->> 'role') IN ('viewer', 'analyst', 'admin'));

CREATE POLICY viewer_select_decisions ON decisions FOR SELECT TO authenticated
    USING ((auth.jwt() ->> 'role') IN ('viewer', 'analyst', 'admin'));

CREATE POLICY viewer_select_projects ON projects FOR SELECT TO authenticated
    USING ((auth.jwt() ->> 'role') IN ('viewer', 'analyst', 'admin'));

CREATE POLICY viewer_select_tickets ON tickets FOR SELECT TO authenticated
    USING ((auth.jwt() ->> 'role') IN ('viewer', 'analyst', 'admin'));

-- ------------------------------------------------------------------------------
-- 4. Analyst Role Policies (Research Execution, Document Ingestion, Approvals)
-- ------------------------------------------------------------------------------
CREATE POLICY analyst_manage_research_sessions ON research_sessions FOR ALL TO authenticated
    USING ((auth.jwt() ->> 'role') IN ('analyst', 'admin'))
    WITH CHECK ((auth.jwt() ->> 'role') IN ('analyst', 'admin'));

CREATE POLICY analyst_select_events ON workflow_events FOR SELECT TO authenticated
    USING ((auth.jwt() ->> 'role') IN ('analyst', 'admin'));

CREATE POLICY analyst_select_citations ON citation_records FOR SELECT TO authenticated
    USING ((auth.jwt() ->> 'role') IN ('analyst', 'admin'));

CREATE POLICY analyst_select_documents ON documents FOR SELECT TO authenticated
    USING ((auth.jwt() ->> 'role') IN ('analyst', 'admin'));

CREATE POLICY analyst_insert_documents ON documents FOR INSERT TO authenticated
    WITH CHECK ((auth.jwt() ->> 'role') IN ('analyst', 'admin'));

CREATE POLICY analyst_select_chunks ON document_chunks FOR SELECT TO authenticated
    USING ((auth.jwt() ->> 'role') IN ('analyst', 'admin'));

CREATE POLICY analyst_request_approvals ON approval_requests FOR INSERT TO authenticated
    WITH CHECK ((auth.jwt() ->> 'role') IN ('analyst', 'admin'));

CREATE POLICY analyst_view_approvals ON approval_requests FOR SELECT TO authenticated
    USING ((auth.jwt() ->> 'role') IN ('analyst', 'admin'));

-- ------------------------------------------------------------------------------
-- 5. Admin Role Policies (Full Administrative Access & Governance)
-- ------------------------------------------------------------------------------
CREATE POLICY admin_all_approvals ON approval_requests FOR ALL TO authenticated
    USING ((auth.jwt() ->> 'role') = 'admin')
    WITH CHECK ((auth.jwt() ->> 'role') = 'admin');

CREATE POLICY admin_all_users ON users FOR ALL TO authenticated
    USING ((auth.jwt() ->> 'role') = 'admin')
    WITH CHECK ((auth.jwt() ->> 'role') = 'admin');

-- ------------------------------------------------------------------------------
-- 6. Append-Only Audit Log Invariant (Prohibit UPDATE and DELETE)
-- ------------------------------------------------------------------------------
-- Zero UPDATE or DELETE statements allowed on audit_logs (Claude.md §9, Roadmap.sh invariant)
CREATE POLICY admin_select_audit_logs ON audit_logs FOR SELECT TO authenticated
    USING ((auth.jwt() ->> 'role') = 'admin');

CREATE POLICY auth_insert_audit_logs ON audit_logs FOR INSERT TO authenticated
    WITH CHECK (true);

CREATE POLICY no_update_audit_logs ON audit_logs FOR UPDATE
    USING (false);

CREATE POLICY no_delete_audit_logs ON audit_logs FOR DELETE
    USING (false);
