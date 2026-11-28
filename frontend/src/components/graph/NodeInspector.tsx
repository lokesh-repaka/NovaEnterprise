"use client";

import React from "react";
import {
  X,
  Share2,
  ExternalLink,
  Loader2,
  Database,
  ArrowRight,
  ArrowLeft,
  Copy,
  Info,
} from "lucide-react";
import type { GraphNode, GraphEdge } from "@/types/api";

export interface NodeInspectorProps {
  node: GraphNode | null;
  edges: GraphEdge[];
  allNodes: GraphNode[];
  onClose: () => void;
  onExpand: (nodeId: string) => void;
  isExpanding?: boolean;
  onSelectNode: (node: GraphNode) => void;
}

export function NodeInspector({
  node,
  edges,
  allNodes,
  onClose,
  onExpand,
  isExpanding,
  onSelectNode,
}: NodeInspectorProps) {
  if (!node) return null;

  // Find connected incoming and outgoing edges
  const connectedEdges = edges.filter(
    (e) => e.source === node.id || e.target === node.id
  );

  const nodeMap = new Map<string, GraphNode>();
  allNodes.forEach((n) => nodeMap.set(n.id, n));

  const displayName =
    (node.properties.name as string) ||
    (node.properties.incident_id as string) ||
    (node.properties.title as string) ||
    node.id;

  return (
    <div
      data-testid="node-inspector"
      className="flex flex-col h-full rounded-xl border border-gray-800 bg-[#0d121f] overflow-hidden"
    >
      {/* Inspector Header */}
      <div className="flex items-center justify-between p-4 border-b border-gray-800 bg-[#0e1526]">
        <div className="flex items-center space-x-2">
          <span className="px-2 py-0.5 rounded text-[11px] font-mono font-bold bg-blue-950/80 text-blue-300 border border-blue-800/60 uppercase">
            {node.label}
          </span>
          <h3 className="text-sm font-bold text-white tracking-tight truncate max-w-[180px]">
            {displayName}
          </h3>
        </div>

        <button
          type="button"
          onClick={onClose}
          className="p-1 rounded-md text-gray-400 hover:text-white hover:bg-gray-800 transition-colors"
          title="Close inspector"
        >
          <X size={16} />
        </button>
      </div>

      {/* Inspector Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-5">
        {/* Actions Bar */}
        <div className="space-y-2">
          <button
            type="button"
            onClick={() => onExpand(node.id)}
            disabled={isExpanding}
            className="w-full py-2 px-3 rounded-lg text-xs font-mono font-medium bg-blue-600 hover:bg-blue-500 text-white flex items-center justify-center space-x-2 transition-colors disabled:opacity-50"
          >
            {isExpanding ? (
              <Loader2 size={13} className="animate-spin" />
            ) : (
              <Share2 size={13} />
            )}
            <span>Expand Neighbors (1-Hop)</span>
          </button>
        </div>

        {/* Node Identifiers */}
        <div className="p-3 rounded-lg border border-gray-800 bg-gray-950/60 space-y-1.5 font-mono text-xs">
          <div className="text-gray-400 text-[10px] uppercase">Node Identifier</div>
          <p className="text-white break-all text-[11px] select-all font-semibold">{node.id}</p>
        </div>

        {/* Entity Properties */}
        <div className="space-y-2">
          <h4 className="text-xs font-mono font-semibold uppercase text-gray-400 flex items-center gap-1.5">
            <Info size={12} className="text-blue-400" />
            Properties
          </h4>

          <div className="rounded-lg border border-gray-800 bg-gray-950/40 overflow-hidden divide-y divide-gray-800/80 font-mono text-xs">
            {Object.keys(node.properties).length === 0 ? (
              <p className="p-3 text-gray-500 italic text-[11px]">No properties recorded.</p>
            ) : (
              Object.entries(node.properties).map(([key, value]) => (
                <div key={key} className="p-2.5 flex items-start justify-between gap-2">
                  <span className="text-gray-400 text-[11px] shrink-0">{key}:</span>
                  <span className="text-gray-200 text-right text-[11px] font-medium break-all select-all">
                    {typeof value === "object" ? JSON.stringify(value) : String(value)}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Connected Graph Relationships */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <h4 className="text-xs font-mono font-semibold uppercase text-gray-400 flex items-center gap-1.5">
              <Database size={12} className="text-purple-400" />
              Connected Edges ({connectedEdges.length})
            </h4>
          </div>

          <div className="space-y-1.5 max-h-56 overflow-y-auto">
            {connectedEdges.length === 0 ? (
              <p className="text-xs text-gray-500 font-mono italic p-2">
                No connected edges loaded in current subgraph.
              </p>
            ) : (
              connectedEdges.map((edge) => {
                const isOutgoing = edge.source === node.id;
                const otherNodeId = isOutgoing ? edge.target : edge.source;
                const otherNode = nodeMap.get(otherNodeId);

                return (
                  <button
                    key={edge.id || `${edge.source}-${edge.type}-${edge.target}`}
                    type="button"
                    onClick={() => otherNode && onSelectNode(otherNode)}
                    className="w-full p-2.5 rounded-lg border border-gray-800/80 bg-gray-950/50 hover:bg-gray-800/50 hover:border-gray-700 text-left transition-all font-mono text-xs flex items-center justify-between group"
                  >
                    <div className="flex items-center space-x-2 truncate">
                      {isOutgoing ? (
                        <ArrowRight size={12} className="text-blue-400 shrink-0" />
                      ) : (
                        <ArrowLeft size={12} className="text-emerald-400 shrink-0" />
                      )}
                      <span className="text-purple-300 font-semibold text-[11px]">
                        [:{edge.type}]
                      </span>
                      <span className="text-gray-300 truncate text-[11px]">
                        {otherNode
                          ? (otherNode.properties.name as string) ||
                            (otherNode.properties.incident_id as string) ||
                            otherNode.id
                          : otherNodeId}
                      </span>
                    </div>

                    <span className="text-[10px] text-gray-500 group-hover:text-gray-300 shrink-0">
                      Select →
                    </span>
                  </button>
                );
              })
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
