"use client";

import React, { useState, useEffect, useCallback, useMemo } from "react";
import {
  Network,
  Database,
  Layers,
  AlertTriangle,
  RefreshCw,
  Share2,
  Users,
  Server,
  AlertCircle,
  FileCode,
} from "lucide-react";
import { apiClient } from "@/api/client";
import { GraphCanvas } from "@/components/graph/GraphCanvas";
import { NodeInspector } from "@/components/graph/NodeInspector";
import { CypherTerminal } from "@/components/graph/CypherTerminal";
import type { GraphNode, GraphEdge } from "@/types/api";

export default function KnowledgeGraphPage() {
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [edges, setEdges] = useState<GraphEdge[]>([]);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isExpanding, setIsExpanding] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const fetchInitialGraph = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const data = await apiClient.graph.getGraph({ limit: 100 });
      setNodes(data.nodes || []);
      setEdges(data.edges || []);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load knowledge graph";
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchInitialGraph();
  }, [fetchInitialGraph]);

  // Expand node's 1-hop neighborhood (F14)
  const handleExpandNode = async (nodeId: string) => {
    try {
      setIsExpanding(true);
      const res = await apiClient.graph.expand(nodeId, 1);

      // Support both GraphDataResponse format and GraphExpandResponse format
      const incomingNodes = res.nodes || (res.center_node ? [res.center_node, ...(res.neighbors || [])] : []);
      const incomingEdges = res.edges || [];

      // Merge nodes without duplicate IDs
      setNodes((prev) => {
        const map = new Map<string, GraphNode>();
        prev.forEach((n) => map.set(n.id, n));
        incomingNodes.forEach((n) => map.set(n.id, n));
        return Array.from(map.values());
      });

      // Merge edges without duplicate IDs
      setEdges((prev) => {
        const edgeKeys = new Set(prev.map((e) => e.id || `${e.source}-${e.type}-${e.target}`));
        const merged = [...prev];
        incomingEdges.forEach((e) => {
          const key = e.id || `${e.source}-${e.type}-${e.target}`;
          if (!edgeKeys.has(key)) {
            edgeKeys.add(key);
            merged.push(e);
          }
        });
        return merged;
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to expand node neighborhood";
      setError(msg);
    } finally {
      setIsExpanding(false);
    }
  };

  const handleCypherResultsLoaded = (newNodes: GraphNode[], newEdges: GraphEdge[]) => {
    if (newNodes.length > 0) {
      setNodes((prev) => {
        const map = new Map<string, GraphNode>();
        prev.forEach((n) => map.set(n.id, n));
        newNodes.forEach((n) => map.set(n.id, n));
        return Array.from(map.values());
      });
    }
    if (newEdges.length > 0) {
      setEdges((prev) => {
        const edgeKeys = new Set(prev.map((e) => e.id || `${e.source}-${e.type}-${e.target}`));
        const merged = [...prev];
        newEdges.forEach((e) => {
          const key = e.id || `${e.source}-${e.type}-${e.target}`;
          if (!edgeKeys.has(key)) {
            edgeKeys.add(key);
            merged.push(e);
          }
        });
        return merged;
      });
    }
  };

  // Compute entity counts by label
  const labelCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    nodes.forEach((n) => {
      counts[n.label] = (counts[n.label] || 0) + 1;
    });
    return counts;
  }, [nodes]);

  return (
    <div className="space-y-6">
      {/* Header & Overall Entity Counters */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-gray-800/80 pb-4">
        <div>
          <div className="flex items-center space-x-2.5">
            <h2 className="text-xl font-bold text-white tracking-tight">
              Knowledge Graph Explorer
            </h2>
            <span className="text-xs font-mono px-2 py-0.5 rounded bg-blue-950/60 text-blue-300 border border-blue-800/40">
              Typed Traversals (F14)
            </span>
          </div>
          <p className="text-xs text-gray-400 mt-1">
            Traverse enterprise topology (Services, Teams, Customers, Incidents) or run governed read-only Cypher queries.
          </p>
        </div>

        {/* Global Topology Summary Pills */}
        <div className="flex flex-wrap items-center gap-2">
          <span className="px-2.5 py-1 rounded-md text-xs font-mono font-medium bg-gray-900 text-white border border-gray-800">
            {nodes.length} Nodes
          </span>
          <span className="px-2.5 py-1 rounded-md text-xs font-mono font-medium bg-gray-900 text-gray-300 border border-gray-800">
            {edges.length} Edges
          </span>

          {labelCounts["Service"] && (
            <span className="px-2.5 py-1 rounded-md text-xs font-mono font-medium bg-blue-950/40 text-blue-300 border border-blue-800/40">
              {labelCounts["Service"]} Services
            </span>
          )}
          {labelCounts["Incident"] && (
            <span className="px-2.5 py-1 rounded-md text-xs font-mono font-medium bg-rose-950/40 text-rose-300 border border-rose-800/40">
              {labelCounts["Incident"]} Incidents
            </span>
          )}
          {labelCounts["Customer"] && (
            <span className="px-2.5 py-1 rounded-md text-xs font-mono font-medium bg-emerald-950/40 text-emerald-300 border border-emerald-800/40">
              {labelCounts["Customer"]} Customers
            </span>
          )}
          {labelCounts["Team"] && (
            <span className="px-2.5 py-1 rounded-md text-xs font-mono font-medium bg-purple-950/40 text-purple-300 border border-purple-800/40">
              {labelCounts["Team"]} Teams
            </span>
          )}

          <button
            type="button"
            onClick={fetchInitialGraph}
            disabled={isLoading}
            className="p-1.5 rounded-md border border-gray-800 bg-gray-900 hover:bg-gray-800 text-gray-300 hover:text-white transition-colors"
            title="Reload initial graph"
          >
            <RefreshCw size={13} className={isLoading ? "animate-spin" : ""} />
          </button>
        </div>
      </div>

      {/* Global Error Alert */}
      {error && (
        <div className="p-3.5 rounded-xl border border-rose-800/60 bg-rose-950/30 text-rose-300 flex items-start space-x-2 text-xs font-mono">
          <AlertTriangle size={16} className="text-rose-400 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <h4 className="font-semibold text-rose-200">Graph Operation Error</h4>
            <p className="text-rose-300">{error}</p>
          </div>
        </div>
      )}

      {/* Main Canvas & Inspector Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 min-h-[500px]">
        {/* Left Column (3 or 4 cols): Canvas Viewport */}
        <div className={selectedNode ? "lg:col-span-3" : "lg:col-span-4"}>
          <GraphCanvas
            nodes={nodes}
            edges={edges}
            selectedNodeId={selectedNode?.id}
            onSelectNode={setSelectedNode}
            onExpandNode={handleExpandNode}
            isExpanding={isExpanding}
          />
        </div>

        {/* Right Column: Node Properties & Relationships Inspector */}
        {selectedNode && (
          <div className="lg:col-span-1 min-h-[500px]">
            <NodeInspector
              node={selectedNode}
              edges={edges}
              allNodes={nodes}
              onClose={() => setSelectedNode(null)}
              onExpand={handleExpandNode}
              isExpanding={isExpanding}
              onSelectNode={setSelectedNode}
            />
          </div>
        )}
      </div>

      {/* Read-Only Cypher Terminal Console */}
      <CypherTerminal onResultsLoaded={handleCypherResultsLoaded} />
    </div>
  );
}
