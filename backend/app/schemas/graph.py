"""Pydantic v2 schemas for Knowledge Graph Explorer and Cypher queries (P11-1, F14).

Defines API contract models for:
- GET  /api/v1/graph (GraphDataResponse)
- GET  /api/v1/graph/expand/{id} (GraphDataResponse)
- POST /api/v1/graph/query (CypherQueryRequest, CypherQueryResponse)
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class GraphNodeResponse(BaseModel):
    """Property graph node entity representation."""

    id: str = Field(..., description="Unique node identifier")
    label: str = Field(
        ...,
        description="Entity classification label (e.g. Service, Incident, Customer, Team)",
    )
    properties: dict[str, Any] = Field(
        default_factory=dict, description="Arbitrary entity attributes and metadata"
    )

    model_config = ConfigDict(from_attributes=True)


class GraphEdgeResponse(BaseModel):
    """Property graph directed edge relationship representation."""

    id: str | None = Field(default=None, description="Optional unique edge identifier")
    source: str = Field(..., description="Source node identifier")
    target: str = Field(..., description="Target node identifier")
    type: str = Field(
        ...,
        description="Relationship verb/label (e.g. AFFECTED, IMPACTED, OWNS, MEMBER_OF)",
    )
    properties: dict[str, Any] = Field(
        default_factory=dict, description="Relationship metadata"
    )

    model_config = ConfigDict(from_attributes=True)


class GraphDataResponse(BaseModel):
    """Knowledge graph subgraph container for browsing and node expansion (F14)."""

    nodes: list[GraphNodeResponse] = Field(
        default_factory=list, description="List of graph nodes in the subgraph"
    )
    edges: list[GraphEdgeResponse] = Field(
        default_factory=list, description="List of connecting graph edges"
    )
    root: GraphNodeResponse | None = Field(
        default=None, description="Optional focal root node for expansion queries"
    )

    model_config = ConfigDict(from_attributes=True)


class CypherQueryRequest(BaseModel):
    """Request payload for executing read-only Cypher queries (F14, Claude.md §18.1)."""

    query: str = Field(
        ...,
        description="Single read-only Cypher MATCH...RETURN statement",
        examples=[
            "MATCH (s:Service)<-[:AFFECTED]-(i:Incident) RETURN s.name AS service, count(i) AS incidents"
        ],
    )
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional parameter bindings referenced in Cypher statement ($param)",
    )


class CypherQueryResponse(BaseModel):
    """Response payload for read-only Cypher query execution."""

    results: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Tabular projection records returned by the query",
    )
    execution_time_ms: float = Field(
        ..., description="Execution duration in milliseconds"
    )
    nodes: list[GraphNodeResponse] = Field(
        default_factory=list,
        description="Extracted node entities present in the query results",
    )
    edges: list[GraphEdgeResponse] = Field(
        default_factory=list,
        description="Extracted edge relationships present in the query results",
    )

    model_config = ConfigDict(from_attributes=True)
