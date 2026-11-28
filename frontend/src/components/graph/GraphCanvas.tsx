"use client";

import React, { useState, useMemo, useRef } from "react";
import {
  ZoomIn,
  ZoomOut,
  RotateCcw,
  Search,
  Filter,
  Maximize2,
  Share2,
  Sparkles,
  Layers,
} from "lucide-react";
import type { GraphNode, GraphEdge } from "@/types/api";

export interface GraphCanvasProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  selectedNodeId?: string | null;
  onSelectNode?: (node: GraphNode | null) => void;
  onExpandNode?: (nodeId: string) => void;
  isExpanding?: boolean;
}

const ENTITY_CONFIGS: Record<
  string,
  { bg: string; border: string; text: string; fill: string; stroke: string }
> = {
  Service: {
    bg: "bg-blue-950/60",
    border: "border-blue-600",
    text: "text-blue-300",
    fill: "#1e3a8a",
    stroke: "#3b82f6",
  },
  Customer: {
    bg: "bg-emerald-950/60",
    border: "border-emerald-600",
    text: "text-emerald-300",
    fill: "#064e3b",
    stroke: "#10b981",
  },
  Incident: {
    bg: "bg-rose-950/60",
    border: "border-rose-600",
    text: "text-rose-300",
    fill: "#881337",
    stroke: "#f43f5e",
  },
  Team: {
    bg: "bg-purple-950/60",
    border: "border-purple-600",
    text: "text-purple-300",
    fill: "#581c87",
    stroke: "#a855f7",
  },
  ADR: {
    bg: "bg-indigo-950/60",
    border: "border-indigo-600",
    text: "text-indigo-300",
    fill: "#312e81",
    stroke: "#6366f1",
  },
  Document: {
    bg: "bg-cyan-950/60",
    border: "border-cyan-600",
    text: "text-cyan-300",
    fill: "#164e63",
    stroke: "#06b6d4",
  },
};

const DEFAULT_CONFIG = {
  bg: "bg-gray-800",
  border: "border-gray-600",
  text: "text-gray-300",
  fill: "#1f2937",
  stroke: "#6b7280",
};

export function GraphCanvas({
  nodes,
  edges,
  selectedNodeId,
  onSelectNode,
  onExpandNode,
  isExpanding,
}: GraphCanvasProps) {
  const [activeLabelFilter, setActiveLabelFilter] = useState<string>("All");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [zoomLevel, setZoomLevel] = useState<number>(1);
  const [panOffset, setPanOffset] = useState<{ x: number; y: number }>({ x: 0, y: 0 });

  // Extract distinct node labels
  const uniqueLabels = useMemo(() => {
    const labels = new Set<string>();
    nodes.forEach((n) => labels.add(n.label));
    return ["All", ...Array.from(labels)];
  }, [nodes]);

  // Filter nodes based on label and search query
  const filteredNodes = useMemo(() => {
    return nodes.filter((node) => {
      if (activeLabelFilter !== "All" && node.label !== activeLabelFilter) {
        return false;
      }
      if (!searchQuery.trim()) return true;

      const q = searchQuery.toLowerCase();
      const name = String(node.properties.name || node.properties.incident_id || node.id).toLowerCase();
      const label = node.label.toLowerCase();
      return name.includes(q) || label.includes(q);
    });
  }, [nodes, activeLabelFilter, searchQuery]);

  const visibleNodeIds = useMemo(() => {
    return new Set(filteredNodes.map((n) => n.id));
  }, [filteredNodes]);

  // Only show edges where both endpoints are in visible nodes
  const visibleEdges = useMemo(() => {
    return edges.filter(
      (e) => visibleNodeIds.has(e.source) && visibleNodeIds.has(e.target)
    );
  }, [edges, visibleNodeIds]);

  // Compute node 2D positions (deterministic constellation layout)
  const nodePositions = useMemo(() => {
    const positions = new Map<string, { x: number; y: number }>();
    const count = filteredNodes.length;
    if (count === 0) return positions;

    const width = 800;
    const height = 500;
    const centerX = width / 2;
    const centerY = height / 2;

    if (count === 1) {
      positions.set(filteredNodes[0].id, { x: centerX, y: centerY });
      return positions;
    }

    // Multi-ring concentric layout
    const radius = Math.min(centerX, centerY) * 0.7;
    const step = (2 * Math.PI) / count;

    filteredNodes.forEach((node, i) => {
      // If there's an inner ring for selected or first node
      const angle = i * step;
      // Stagger radius slightly for organic constellation feel
      const r = count > 8 && i % 2 === 1 ? radius * 0.55 : radius;
      const x = centerX + r * Math.cos(angle);
      const y = centerY + r * Math.sin(angle);
      positions.set(node.id, { x, y });
    });

    return positions;
  }, [filteredNodes]);

  const handleZoom = (delta: number) => {
    setZoomLevel((prev) => Math.max(0.5, Math.min(2.5, prev + delta)));
  };

  const handleReset = () => {
    setZoomLevel(1);
    setPanOffset({ x: 0, y: 0 });
    setActiveLabelFilter("All");
    setSearchQuery("");
  };

  const getNodeDisplayName = (node: GraphNode) => {
    return (
      (node.properties.name as string) ||
      (node.properties.incident_id as string) ||
      (node.properties.title as string) ||
      node.id
    );
  };

  return (
    <div
      data-testid="graph-canvas"
      className="flex flex-col h-full rounded-xl border border-gray-800 bg-[#070b14] overflow-hidden"
    >
      {/* Top Controls Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-3.5 border-b border-gray-800 bg-[#0d121f]">
        {/* Label Filter Pills */}
        <div className="flex items-center space-x-1.5 overflow-x-auto pb-1 sm:pb-0">
          <span className="text-xs font-mono text-gray-500 flex items-center gap-1 pr-1">
            <Filter size={12} />
            Filter:
          </span>
          {uniqueLabels.map((lbl) => {
            const isActive = activeLabelFilter === lbl;
            return (
              <button
                key={lbl}
                type="button"
                onClick={() => setActiveLabelFilter(lbl)}
                className={`px-2.5 py-1 rounded-md text-xs font-mono transition-colors ${
                  isActive
                    ? "bg-blue-600 text-white shadow-sm font-semibold"
                    : "bg-gray-900 text-gray-400 hover:text-white hover:bg-gray-800 border border-gray-800"
                }`}
              >
                {lbl}
              </button>
            );
          })}
        </div>

        {/* Search & Zoom Controls */}
        <div className="flex items-center space-x-2">
          {/* Search Input */}
          <div className="relative">
            <Search
              size={13}
              className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400"
            />
            <input
              type="text"
              placeholder="Search nodes..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-8 pr-3 py-1 text-xs rounded-lg border border-gray-800 bg-gray-950 text-white placeholder-gray-500 focus:outline-none focus:border-blue-500 w-36 sm:w-48 font-mono"
            />
          </div>

          {/* Zoom controls */}
          <div className="flex items-center space-x-1 border-l border-gray-800 pl-2">
            <button
              type="button"
              onClick={() => handleZoom(0.2)}
              title="Zoom In"
              className="p-1.5 rounded-md border border-gray-800 bg-gray-900 hover:bg-gray-800 text-gray-300 hover:text-white transition-colors"
            >
              <ZoomIn size={14} />
            </button>
            <button
              type="button"
              onClick={() => handleZoom(-0.2)}
              title="Zoom Out"
              className="p-1.5 rounded-md border border-gray-800 bg-gray-900 hover:bg-gray-800 text-gray-300 hover:text-white transition-colors"
            >
              <ZoomOut size={14} />
            </button>
            <button
              type="button"
              onClick={handleReset}
              title="Reset View"
              className="p-1.5 rounded-md border border-gray-800 bg-gray-900 hover:bg-gray-800 text-gray-300 hover:text-white transition-colors"
            >
              <RotateCcw size={14} />
            </button>
          </div>
        </div>
      </div>

      {/* Main Interactive Graph Viewport */}
      <div className="relative flex-1 min-h-[460px] bg-radial-grid overflow-hidden select-none">
        {filteredNodes.length === 0 ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center space-y-2 text-center p-6">
            <Layers size={36} className="text-gray-600" />
            <p className="text-sm text-gray-400 font-medium">No Graph Entities Match Filter</p>
            <p className="text-xs text-gray-600 font-mono">
              Reset filter or query to explore other subgraphs
            </p>
          </div>
        ) : (
          <svg
            viewBox="0 0 800 500"
            className="w-full h-full cursor-grab active:cursor-grabbing"
            style={{
              transform: `scale(${zoomLevel}) translate(${panOffset.x}px, ${panOffset.y}px)`,
              transformOrigin: "center center",
              transition: "transform 0.15s ease-out",
            }}
          >
            <defs>
              {/* Arrowhead marker for directed relationships */}
              <marker
                id="arrow"
                viewBox="0 0 10 10"
                refX="22"
                refY="5"
                markerWidth="6"
                markerHeight="6"
                orient="auto-start-reverse"
              >
                <path d="M 0 0 L 10 5 L 0 10 z" fill="#4b5563" />
              </marker>
              <marker
                id="arrow-selected"
                viewBox="0 0 10 10"
                refX="22"
                refY="5"
                markerWidth="6"
                markerHeight="6"
                orient="auto-start-reverse"
              >
                <path d="M 0 0 L 10 5 L 0 10 z" fill="#3b82f6" />
              </marker>
            </defs>

            {/* Connecting Edges */}
            <g className="edges">
              {visibleEdges.map((edge) => {
                const src = nodePositions.get(edge.source);
                const tgt = nodePositions.get(edge.target);
                if (!src || !tgt) return null;

                const isConnectedToSelected =
                  selectedNodeId &&
                  (edge.source === selectedNodeId || edge.target === selectedNodeId);

                const midX = (src.x + tgt.x) / 2;
                const midY = (src.y + tgt.y) / 2;

                return (
                  <g key={edge.id || `${edge.source}-${edge.type}-${edge.target}`}>
                    <line
                      x1={src.x}
                      y1={src.y}
                      x2={tgt.x}
                      y2={tgt.y}
                      stroke={isConnectedToSelected ? "#3b82f6" : "#374151"}
                      strokeWidth={isConnectedToSelected ? 2 : 1.2}
                      strokeDasharray={isConnectedToSelected ? undefined : "3,3"}
                      markerEnd={isConnectedToSelected ? "url(#arrow-selected)" : "url(#arrow)"}
                    />
                    <text
                      x={midX}
                      y={midY - 4}
                      fill={isConnectedToSelected ? "#93c5fd" : "#6b7280"}
                      fontSize="9"
                      fontFamily="monospace"
                      textAnchor="middle"
                      className="select-none pointer-events-none"
                    >
                      [:{edge.type}]
                    </text>
                  </g>
                );
              })}
            </g>

            {/* Graph Entity Nodes */}
            <g className="nodes">
              {filteredNodes.map((node) => {
                const pos = nodePositions.get(node.id);
                if (!pos) return null;

                const isSelected = selectedNodeId === node.id;
                const config = ENTITY_CONFIGS[node.label] || DEFAULT_CONFIG;
                const displayName = getNodeDisplayName(node);

                return (
                  <g
                    key={node.id}
                    transform={`translate(${pos.x}, ${pos.y})`}
                    onClick={() => onSelectNode?.(node)}
                    className="cursor-pointer group"
                  >
                    {/* Pulsing selection aura */}
                    {isSelected && (
                      <circle
                        r="28"
                        fill="none"
                        stroke="#3b82f6"
                        strokeWidth="2"
                        className="animate-ping opacity-50"
                      />
                    )}

                    {/* Node base circle */}
                    <circle
                      r="20"
                      fill={config.fill}
                      stroke={isSelected ? "#60a5fa" : config.stroke}
                      strokeWidth={isSelected ? 3 : 1.5}
                      className="transition-all duration-200 group-hover:scale-110"
                    />

                    {/* Inner initial or icon indicator */}
                    <text
                      textAnchor="middle"
                      dy="4"
                      fill="#ffffff"
                      fontSize="11"
                      fontWeight="bold"
                      fontFamily="sans-serif"
                      className="pointer-events-none"
                    >
                      {node.label.charAt(0)}
                    </text>

                    {/* Node Display Name Tag */}
                    <text
                      textAnchor="middle"
                      dy="34"
                      fill={isSelected ? "#93c5fd" : "#e2e8f0"}
                      fontSize="10"
                      fontFamily="monospace"
                      fontWeight={isSelected ? "bold" : "normal"}
                      className="pointer-events-none"
                    >
                      {displayName}
                    </text>

                    {/* Subtitle / Entity Type */}
                    <text
                      textAnchor="middle"
                      dy="46"
                      fill="#94a3b8"
                      fontSize="8"
                      fontFamily="monospace"
                      className="pointer-events-none uppercase"
                    >
                      {node.label}
                    </text>
                  </g>
                );
              })}
            </g>
          </svg>
        )}

        {/* Floating Canvas Footer Telemetry */}
        <div className="absolute bottom-3 left-3 flex items-center space-x-2 text-[11px] font-mono bg-gray-950/80 border border-gray-800 px-3 py-1.5 rounded-lg text-gray-400">
          <span>{filteredNodes.length} visible nodes</span>
          <span>•</span>
          <span>{visibleEdges.length} visible edges</span>
          {selectedNodeId && (
            <>
              <span>•</span>
              <span className="text-blue-400">Selected: {selectedNodeId}</span>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
