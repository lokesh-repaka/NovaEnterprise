import React from "react";
import Link from "next/link";
import {
  Search,
  Network,
  Files,
  Database,
  ShieldCheck,
  Sparkles,
  ArrowRight,
  Layers,
  Cpu,
  CheckCircle2,
  GitBranch,
  FileCheck,
  ShieldAlert,
  Terminal,
} from "lucide-react";

export default function DashboardPage() {
  const canonicalQuery =
    "Which customers were impacted by the Payments API last quarter, what incidents occurred, which teams own those services, and what decisions were taken to prevent recurrence?";

  return (
    <div className="space-y-8 pb-10">
      {/* Hero Welcome Card */}
      <div className="relative overflow-hidden rounded-2xl border border-gray-800 bg-gradient-to-r from-blue-950/40 via-gray-900 to-[#0e1629] p-8 shadow-2xl">
        <div className="relative z-10 max-w-3xl space-y-4">
          <div className="inline-flex items-center space-x-2 rounded-full border border-blue-500/30 bg-blue-500/10 px-3 py-1 text-xs font-mono font-medium text-blue-400">
            <Sparkles size={14} />
            <span>Multi-Hop Multi-Store Intelligence</span>
          </div>
          <h2 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">
            Enterprise Decision & Knowledge Intelligence
          </h2>
          <p className="text-sm leading-relaxed text-gray-300">
            NovaEnterprise unifies structured database records, high-dimensional document vectors,
            and knowledge graph relationships into an open, auditable 13-node LangGraph research engine.
            Built on the core principle: <strong className="text-cyan-400">Retrieval strategy is a routing decision, not a library choice.</strong>
          </p>

          <div className="flex flex-wrap items-center gap-3 pt-2">
            <Link
              href="/search"
              className="inline-flex items-center space-x-2 rounded-lg bg-blue-600 px-5 py-2.5 text-xs font-semibold text-white shadow-lg shadow-blue-600/30 transition-all hover:bg-blue-500 hover:shadow-blue-500/40"
            >
              <Search size={16} />
              <span>Launch Research Workspace</span>
              <ArrowRight size={14} />
            </Link>
            <Link
              href="/knowledge-graph"
              className="inline-flex items-center space-x-2 rounded-lg border border-gray-700 bg-gray-800/80 px-4 py-2.5 text-xs font-semibold text-gray-200 transition-colors hover:bg-gray-700"
            >
              <Network size={16} />
              <span>Browse Knowledge Graph</span>
            </Link>
            <a
              href="https://github.com/lokesh-repaka/NovaEnterprise"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center space-x-2 rounded-lg border border-gray-800 bg-gray-900/60 px-4 py-2.5 text-xs font-semibold text-gray-300 transition-colors hover:bg-gray-800"
            >
              <GitBranch size={16} className="text-gray-400" />
              <span>GitHub Repository</span>
            </a>
          </div>
        </div>

        {/* Background gradient decorative flare */}
        <div className="absolute -right-16 -top-16 h-64 w-64 rounded-full bg-blue-600/10 blur-3xl pointer-events-none" />
      </div>

      {/* Architectural KPI Metrics Banner */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4">
          <div className="text-[10px] font-mono uppercase text-gray-400">Canonical Latency</div>
          <div className="text-2xl font-bold text-cyan-400">&lt; 10s</div>
          <div className="text-[11px] text-gray-400">&lt; 500ms initial HTTP 202 intake</div>
        </div>

        <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4">
          <div className="text-[10px] font-mono uppercase text-gray-400">Citation Grounding</div>
          <div className="text-2xl font-bold text-emerald-400">100%</div>
          <div className="text-[11px] text-gray-400">Zero unverified citations admitted</div>
        </div>

        <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4">
          <div className="text-[10px] font-mono uppercase text-gray-400">Offline Test Harness</div>
          <div className="text-2xl font-bold text-blue-400">475 / 475</div>
          <div className="text-[11px] text-gray-400">100% passing without external APIs</div>
        </div>

        <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4">
          <div className="text-[10px] font-mono uppercase text-gray-400">AST SQL Security</div>
          <div className="text-2xl font-bold text-purple-400">0 Leaks</div>
          <div className="text-[11px] text-gray-400">AST parser enforces SELECT allowlist</div>
        </div>
      </div>

      {/* The Canonical Enterprise Query Interactive Showcase */}
      <div className="rounded-2xl border border-cyan-500/30 bg-gradient-to-b from-[#0a1528] to-[#070d18] p-6 shadow-xl space-y-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="inline-flex items-center space-x-2 text-xs font-mono font-semibold uppercase text-cyan-400 tracking-wider">
              <Terminal size={14} />
              <span>The Canonical Enterprise Benchmark Query</span>
            </div>
            <h3 className="text-lg font-bold text-white mt-1">
              Cross-Store Multi-Hop Resolution in Action
            </h3>
          </div>
          <Link
            href={`/search?q=${encodeURIComponent(canonicalQuery)}`}
            className="inline-flex items-center space-x-2 rounded-lg bg-cyan-500 px-4 py-2 text-xs font-bold text-slate-950 shadow-md shadow-cyan-500/20 transition-all hover:bg-cyan-400 hover:shadow-cyan-400/30 self-start sm:self-auto"
          >
            <span>Run Canonical Query</span>
            <ArrowRight size={14} />
          </Link>
        </div>

        <div className="rounded-xl border border-gray-800 bg-gray-950/80 p-4 font-mono text-xs text-cyan-200">
          &ldquo;{canonicalQuery}&rdquo;
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4 text-xs">
          <div className="rounded-lg border border-gray-800 bg-gray-900/60 p-3 space-y-1">
            <div className="flex items-center justify-between text-[10px] font-mono text-emerald-400 font-bold">
              <span>Sub-Q 1: Impacted Customers</span>
              <span>Graph</span>
            </div>
            <p className="text-gray-300 font-medium">Which customers were impacted?</p>
            <p className="text-[10px] text-gray-500 font-mono">
              (Service)&lt;-[:AFFECTED]-(Incident)-[:IMPACTED]-&gt;(Customer)
            </p>
          </div>

          <div className="rounded-lg border border-gray-800 bg-gray-900/60 p-3 space-y-1">
            <div className="flex items-center justify-between text-[10px] font-mono text-purple-400 font-bold">
              <span>Sub-Q 2: Incidents Occurred</span>
              <span>SQL</span>
            </div>
            <p className="text-gray-300 font-medium">What incidents occurred last quarter?</p>
            <p className="text-[10px] text-gray-500 font-mono">
              SELECT * FROM incidents WHERE created_at BETWEEN :start AND :end
            </p>
          </div>

          <div className="rounded-lg border border-gray-800 bg-gray-900/60 p-3 space-y-1">
            <div className="flex items-center justify-between text-[10px] font-mono text-emerald-400 font-bold">
              <span>Sub-Q 3: Service Ownership</span>
              <span>Graph</span>
            </div>
            <p className="text-gray-300 font-medium">Which teams own those services?</p>
            <p className="text-[10px] text-gray-500 font-mono">
              (Service)-[:OWNED_BY]-&gt;(Team)
            </p>
          </div>

          <div className="rounded-lg border border-gray-800 bg-gray-900/60 p-3 space-y-1">
            <div className="flex items-center justify-between text-[10px] font-mono text-cyan-400 font-bold">
              <span>Sub-Q 4: Prevention Decisions</span>
              <span>Hybrid RAG</span>
            </div>
            <p className="text-gray-300 font-medium">What decisions prevent recurrence?</p>
            <p className="text-[10px] text-gray-500 font-mono">
              Qdrant Dense Cosine + BM25 Lexical + RRF
            </p>
          </div>
        </div>
      </div>

      {/* Triad & Multi-Store Architecture Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-xl border border-gray-800 bg-gray-900/60 p-5 shadow-sm space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono uppercase text-gray-400">Path 1: Dense Vector</span>
            <Database size={16} className="text-blue-400" />
          </div>
          <p className="text-lg font-bold text-white">Hybrid Vector RAG</p>
          <p className="text-xs text-gray-400">
            Dense embeddings + BM25 keyword search combined via Reciprocal Rank Fusion (RRF).
          </p>
        </div>

        <div className="rounded-xl border border-gray-800 bg-gray-900/60 p-5 shadow-sm space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono uppercase text-gray-400">Path 2: Graph Store</span>
            <Network size={16} className="text-emerald-400" />
          </div>
          <p className="text-lg font-bold text-white">Knowledge Graph RAG</p>
          <p className="text-xs text-gray-400">
            Typed domain traversals & read-only Cypher queries across Services, Teams, and Incidents.
          </p>
        </div>

        <div className="rounded-xl border border-gray-800 bg-gray-900/60 p-5 shadow-sm space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono uppercase text-gray-400">Path 3: Relational</span>
            <Layers size={16} className="text-purple-400" />
          </div>
          <p className="text-lg font-bold text-white">Governed SQL</p>
          <p className="text-xs text-gray-400">
            AST-validated read-only queries with allowlisted tables and parameterized constraints.
          </p>
        </div>

        <div className="rounded-xl border border-gray-800 bg-gray-900/60 p-5 shadow-sm space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono uppercase text-gray-400">Multi-Agent</span>
            <Cpu size={16} className="text-amber-400" />
          </div>
          <p className="text-lg font-bold text-white">LangGraph Engine</p>
          <p className="text-xs text-gray-400">
            13 distinct workflow nodes with bounded corrective retrieval and citation verification.
          </p>
        </div>
      </div>

      {/* 13-Node LangGraph Flow Visualizer */}
      <div className="rounded-2xl border border-gray-800 bg-gray-900/40 p-6 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Cpu size={16} className="text-amber-400" />
            <h3 className="text-sm font-bold text-white uppercase tracking-wider font-mono">
              13-Node LangGraph Execution Topology
            </h3>
          </div>
          <span className="text-xs font-mono text-gray-400">
            StateGraph(ResearchState)
          </span>
        </div>

        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-7 text-[11px] font-mono">
          <div className="rounded-lg border border-gray-800 bg-gray-950/70 p-2.5 space-y-1">
            <span className="text-cyan-400 font-bold text-[10px]">01. Recall</span>
            <p className="text-gray-300 font-semibold truncate">recall_memory</p>
            <p className="text-[10px] text-gray-500">4-Tier Context</p>
          </div>

          <div className="rounded-lg border border-gray-800 bg-gray-950/70 p-2.5 space-y-1">
            <span className="text-cyan-400 font-bold text-[10px]">02. Analyze</span>
            <p className="text-gray-300 font-semibold truncate">analyze_query</p>
            <p className="text-[10px] text-gray-500">Intent & Dates</p>
          </div>

          <div className="rounded-lg border border-gray-800 bg-gray-950/70 p-2.5 space-y-1">
            <span className="text-cyan-400 font-bold text-[10px]">03. Assess</span>
            <p className="text-gray-300 font-semibold truncate">assess_complexity</p>
            <p className="text-[10px] text-gray-500">Routing Floor</p>
          </div>

          <div className="rounded-lg border border-gray-800 bg-gray-950/70 p-2.5 space-y-1">
            <span className="text-cyan-400 font-bold text-[10px]">04. Decompose</span>
            <p className="text-gray-300 font-semibold truncate">decompose</p>
            <p className="text-[10px] text-gray-500">Sub-Questions</p>
          </div>

          <div className="rounded-lg border border-blue-500/30 bg-blue-950/30 p-2.5 space-y-1">
            <span className="text-blue-400 font-bold text-[10px]">05. Route</span>
            <p className="text-blue-200 font-semibold truncate">route_retrieval</p>
            <p className="text-[10px] text-blue-400/70">Store Dispatch</p>
          </div>

          <div className="rounded-lg border border-blue-500/30 bg-blue-950/30 p-2.5 space-y-1">
            <span className="text-blue-400 font-bold text-[10px]">06. Execute</span>
            <p className="text-blue-200 font-semibold truncate">execute_retrieval</p>
            <p className="text-[10px] text-blue-400/70">Parallel Lookups</p>
          </div>

          <div className="rounded-lg border border-gray-800 bg-gray-950/70 p-2.5 space-y-1">
            <span className="text-emerald-400 font-bold text-[10px]">07. Collect</span>
            <p className="text-gray-300 font-semibold truncate">collect_evidence</p>
            <p className="text-[10px] text-gray-500">Evidence Models</p>
          </div>

          <div className="rounded-lg border border-amber-500/30 bg-amber-950/30 p-2.5 space-y-1">
            <span className="text-amber-400 font-bold text-[10px]">08. Coverage</span>
            <p className="text-amber-200 font-semibold truncate">check_missing</p>
            <p className="text-[10px] text-amber-400/70">Gap Detection</p>
          </div>

          <div className="rounded-lg border border-amber-500/30 bg-amber-950/30 p-2.5 space-y-1">
            <span className="text-amber-400 font-bold text-[10px]">09. CRAG</span>
            <p className="text-amber-200 font-semibold truncate">corrective_retrieval</p>
            <p className="text-[10px] text-amber-400/70">&le; 2 Retries</p>
          </div>

          <div className="rounded-lg border border-purple-500/30 bg-purple-950/30 p-2.5 space-y-1">
            <span className="text-purple-400 font-bold text-[10px]">10. Verify Ev.</span>
            <p className="text-purple-200 font-semibold truncate">verify_evidence</p>
            <p className="text-[10px] text-purple-400/70">Claim Check</p>
          </div>

          <div className="rounded-lg border border-purple-500/30 bg-purple-950/30 p-2.5 space-y-1">
            <span className="text-purple-400 font-bold text-[10px]">11. Synthesize</span>
            <p className="text-purple-200 font-semibold truncate">synthesize_answer</p>
            <p className="text-[10px] text-purple-400/70">Cited Narration</p>
          </div>

          <div className="rounded-lg border border-emerald-500/30 bg-emerald-950/30 p-2.5 space-y-1">
            <span className="text-emerald-400 font-bold text-[10px]">12. Verify Cit.</span>
            <p className="text-emerald-200 font-semibold truncate">verify_citations</p>
            <p className="text-[10px] text-emerald-400/70">100% Attested</p>
          </div>

          <div className="rounded-lg border border-cyan-500/30 bg-cyan-950/30 p-2.5 space-y-1 sm:col-span-2 lg:col-span-2">
            <span className="text-cyan-400 font-bold text-[10px]">13. Memory Commit</span>
            <p className="text-cyan-200 font-semibold truncate">update_memory &rarr; END</p>
            <p className="text-[10px] text-cyan-400/70">Long-term Semantic Retention</p>
          </div>
        </div>
      </div>

      {/* Quick Navigation Panels */}
      <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
        <Link
          href="/search"
          className="group rounded-xl border border-gray-800 bg-[#0e1526]/80 p-6 transition-all hover:border-blue-500/50 hover:bg-gray-800/50"
        >
          <div className="flex items-center justify-between mb-3">
            <div className="p-2.5 rounded-lg bg-blue-500/10 text-blue-400 border border-blue-500/20">
              <Search size={20} />
            </div>
            <ArrowRight size={16} className="text-gray-500 group-hover:text-blue-400 group-hover:translate-x-1 transition-all" />
          </div>
          <h3 className="text-base font-semibold text-white group-hover:text-blue-400 transition-colors">
            Research Workspace
          </h3>
          <p className="text-xs text-gray-400 mt-1">
            Submit complex enterprise questions, inspect query decomposition, and monitor live node telemetry.
          </p>
        </Link>

        <Link
          href="/knowledge-graph"
          className="group rounded-xl border border-gray-800 bg-[#0e1526]/80 p-6 transition-all hover:border-emerald-500/50 hover:bg-gray-800/50"
        >
          <div className="flex items-center justify-between mb-3">
            <div className="p-2.5 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <Network size={20} />
            </div>
            <ArrowRight size={16} className="text-gray-500 group-hover:text-emerald-400 group-hover:translate-x-1 transition-all" />
          </div>
          <h3 className="text-base font-semibold text-white group-hover:text-emerald-400 transition-colors">
            Knowledge Graph
          </h3>
          <p className="text-xs text-gray-400 mt-1">
            Traverse entity dependencies, blast radius, and execute read-only OpenCypher queries.
          </p>
        </Link>

        <Link
          href="/documents"
          className="group rounded-xl border border-gray-800 bg-[#0e1526]/80 p-6 transition-all hover:border-purple-500/50 hover:bg-gray-800/50"
        >
          <div className="flex items-center justify-between mb-3">
            <div className="p-2.5 rounded-lg bg-purple-500/10 text-purple-400 border border-purple-500/20">
              <Files size={20} />
            </div>
            <ArrowRight size={16} className="text-gray-500 group-hover:text-purple-400 group-hover:translate-x-1 transition-all" />
          </div>
          <h3 className="text-base font-semibold text-white group-hover:text-purple-400 transition-colors">
            Documents & Approvals
          </h3>
          <p className="text-xs text-gray-400 mt-1">
            Upload postmortems and ADRs with automated prompt-injection screening and HITL deletion gates.
          </p>
        </Link>
      </div>
    </div>
  );
}
