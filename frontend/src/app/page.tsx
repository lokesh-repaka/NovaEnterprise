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
} from "lucide-react";

export default function DashboardPage() {
  return (
    <div className="space-y-8">
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
          </p>

          <div className="flex flex-wrap items-center gap-3 pt-2">
            <Link
              href="/search"
              className="inline-flex items-center space-x-2 rounded-lg bg-blue-600 px-5 py-2.5 text-xs font-semibold text-white shadow-lg shadow-blue-600/30 transition-all hover:bg-blue-500 hover:shadow-blue-500/40"
            >
              <Search size={16} />
              <span>Launch Research Query</span>
              <ArrowRight size={14} />
            </Link>
            <Link
              href="/knowledge-graph"
              className="inline-flex items-center space-x-2 rounded-lg border border-gray-700 bg-gray-800/80 px-4 py-2.5 text-xs font-semibold text-gray-200 transition-colors hover:bg-gray-700"
            >
              <Network size={16} />
              <span>Browse Knowledge Graph</span>
            </Link>
          </div>
        </div>

        {/* Background gradient decorative flare */}
        <div className="absolute -right-16 -top-16 h-64 w-64 rounded-full bg-blue-600/10 blur-3xl pointer-events-none" />
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
