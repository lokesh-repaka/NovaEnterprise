"""Knowledge Graph Explorer and read-only Cypher query API router (P11-1, F14, Claude.md §8, §18.1).

Implements:
- GET  /api/v1/graph: Browse knowledge graph subgraph with label and limit filtering [viewer+]
- GET  /api/v1/graph/expand/{id}: 1-hop neighbor expansion with direction and type filters [viewer+]
- POST /api/v1/graph/query: Execute arbitrary read-only Cypher queries [analyst+]
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from backend.app.core.logging import get_logger
from backend.app.core.security import AuthenticatedUser, Role, require_role
from backend.app.schemas.graph import (
    CypherQueryRequest,
    CypherQueryResponse,
    GraphDataResponse,
)
from backend.app.services.graph_service import (
    GraphService,
    get_graph_service,
)

logger = get_logger("api.graph")

router = APIRouter(prefix="/graph", tags=["Knowledge Graph Explorer"])


def _get_service() -> GraphService:
    """Dependency provider yielding GraphService singleton."""
    return get_graph_service()


@router.get(
    "",
    response_model=GraphDataResponse,
    summary="Browse knowledge graph subgraph",
    description="Retrieve a bounded knowledge graph subgraph matching optional classification label criteria (F14).",
)
def get_subgraph(
    limit: int = Query(
        100, ge=1, le=500, description="Maximum number of nodes and edges to return"
    ),
    node_label: str | None = Query(
        None,
        description="Filter nodes by classification label (e.g. Service, Incident, Customer, Team)",
    ),
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_role(Role.VIEWER, Role.ANALYST, Role.ADMIN)),
    ] = None,  # type: ignore[assignment]
    service: Annotated[GraphService, Depends(_get_service)] = None,  # type: ignore[assignment]
) -> GraphDataResponse:
    """Browse knowledge graph nodes and connecting edges."""
    return service.get_subgraph(limit=limit, node_label=node_label)


@router.get(
    "/expand/{id}",
    response_model=GraphDataResponse,
    summary="Expand knowledge graph node",
    description="Expand a single node by retrieving all 1-hop neighbor nodes and connecting relationships (F14).",
)
def expand_node(
    id: str = Path(..., description="Target node identifier to expand"),
    direction: str = Query(
        "both",
        pattern="^(in|out|both)$",
        description="Relationship traversal direction: in, out, or both",
    ),
    relationship_type: str | None = Query(
        None,
        description="Filter by specific relationship type (e.g. AFFECTED, IMPACTED, OWNS, MEMBER_OF)",
    ),
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_role(Role.VIEWER, Role.ANALYST, Role.ADMIN)),
    ] = None,  # type: ignore[assignment]
    service: Annotated[GraphService, Depends(_get_service)] = None,  # type: ignore[assignment]
) -> GraphDataResponse:
    """Expand a node to its 1-hop neighborhood."""
    result = service.expand_node(
        node_id=id,
        direction=direction,
        relationship_type=relationship_type,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Node '{id}' not found in knowledge graph",
        )
    return result


@router.post(
    "/query",
    response_model=CypherQueryResponse,
    summary="Execute read-only Cypher query",
    description="Execute an arbitrary read-only Cypher query with strict AST mutation guards (F14, Claude.md §18.1).",
)
def execute_cypher_query(
    request: CypherQueryRequest,
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_role(Role.ANALYST, Role.ADMIN)),
    ],
    service: Annotated[GraphService, Depends(_get_service)],
) -> CypherQueryResponse:
    """Execute a validated read-only Cypher query."""
    try:
        return service.execute_cypher(
            query=request.query,
            parameters=request.parameters,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
