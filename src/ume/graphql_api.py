from __future__ import annotations
# mypy: ignore-errors

import inspect
from typing import Any

import graphene
from graphene.types.generic import GenericScalar

from fastapi import HTTPException
from graphql import GraphQLError

from . import api_deps as deps
from .permissions_adapter import PermissionsGraphAdapter


async def _maybe_call(obj: Any, name: str, *args: Any) -> Any:
    method = getattr(obj, name)
    if inspect.iscoroutinefunction(method):
        return await method(*args)
    result = method(*args)
    if inspect.isawaitable(result):
        return await result
    return result


def _get_permissions_graph(info: graphene.ResolveInfo) -> PermissionsGraphAdapter | None:
    context = info.context
    if "permissions_graph" in context:
        return context["permissions_graph"]

    app = context["app"]
    graph = getattr(app.state, "graph", None)
    if graph is None:
        context["permissions_graph"] = None
        return None

    user_id = context.get("user_id")
    group_id = context.get("group_id")
    try:
        perm_graph = deps.get_permissions_graph(
            graph=graph,
            user_id=user_id,
            group_id=group_id,
        )
    except HTTPException as exc:  # pragma: no cover - converted to GraphQL error
        raise GraphQLError(exc.detail) from exc

    context["permissions_graph"] = perm_graph
    return perm_graph


class NodeType(graphene.ObjectType):
    """Graph node representation."""

    id = graphene.String(required=True)
    attributes = GenericScalar()
    edges = graphene.List(
        lambda: EdgeType,
        label=graphene.String(),
        description="Edges originating from this node",
    )

    async def resolve_edges(
        self, info: graphene.ResolveInfo, label: str | None = None
    ) -> list["EdgeType"]:
        perm_graph = _get_permissions_graph(info)
        if perm_graph is None:
            return []
        all_edges = await _maybe_call(perm_graph, "get_all_edges")
        result = []
        for src, tgt, lbl, _ in all_edges:
            if src == self.id and (label is None or lbl == label):
                result.append(EdgeType(source=src, target=tgt, label=lbl))
        return result


class EdgeType(graphene.ObjectType):
    """Graph edge representation."""

    source = graphene.String(required=True)
    target = graphene.String(required=True)
    label = graphene.String(required=True)


class Query(graphene.ObjectType):
    node = graphene.Field(NodeType, id=graphene.String(required=True))
    nodes = graphene.List(NodeType)
    edges = graphene.List(EdgeType)
    path = graphene.List(
        graphene.String,
        source=graphene.String(required=True),
        target=graphene.String(required=True),
        max_depth=graphene.Int(),
        edge_label=graphene.String(),
        since_timestamp=graphene.Int(),
        description="Find a path between two nodes",
    )
    documents_by_topic = graphene.List(
        NodeType,
        topic=graphene.String(required=True),
        entity=graphene.String(),
        description=(
            "Return document nodes connected to the given topic. "
            "If `entity` is provided only documents linked to that entity are returned."
        ),
    )

    async def resolve_node(self, info: graphene.ResolveInfo, id: str) -> NodeType | None:
        perm_graph = _get_permissions_graph(info)
        if perm_graph is None:
            return None
        data = await _maybe_call(perm_graph, "get_node", id)
        if data is None:
            return None
        return NodeType(id=id, attributes=data)

    async def resolve_nodes(self, info: graphene.ResolveInfo) -> list[NodeType]:
        perm_graph = _get_permissions_graph(info)
        if perm_graph is None:
            return []
        ids = await _maybe_call(perm_graph, "get_all_node_ids")
        result = []
        for nid in ids:
            data = await _maybe_call(perm_graph, "get_node", nid)
            result.append(NodeType(id=nid, attributes=data or {}))
        return result

    async def resolve_edges(self, info: graphene.ResolveInfo) -> list[EdgeType]:
        perm_graph = _get_permissions_graph(info)
        if perm_graph is None:
            return []
        edges = await _maybe_call(perm_graph, "get_all_edges")
        return [EdgeType(source=s, target=t, label=lbl) for s, t, lbl, _ in edges]

    async def resolve_path(
        self,
        info: graphene.ResolveInfo,
        source: str,
        target: str,
        max_depth: int | None = None,
        edge_label: str | None = None,
        since_timestamp: int | None = None,
    ) -> list[str]:
        perm_graph = _get_permissions_graph(info)
        if perm_graph is None:
            return []
        return await _maybe_call(
            perm_graph,
            "constrained_path",
            source,
            target,
            max_depth,
            edge_label,
            since_timestamp,
        )

    async def resolve_documents_by_topic(
        self,
        info: graphene.ResolveInfo,
        topic: str,
        entity: str | None = None,
    ) -> list[NodeType]:
        perm_graph = _get_permissions_graph(info)
        if perm_graph is None:
            return []
        try:
            doc_ids = await _maybe_call(perm_graph, "find_connected_nodes", topic)
        except Exception:
            return []
        results: list[NodeType] = []
        for doc_id in doc_ids:
            data = await _maybe_call(perm_graph, "get_node", doc_id)
            if data is None:
                continue
            if entity is not None:
                try:
                    ents = await _maybe_call(perm_graph, "find_connected_nodes", doc_id)
                except Exception:
                    continue
                if entity not in ents:
                    continue
            results.append(NodeType(id=doc_id, attributes=data))
        return results


class CreateNode(graphene.Mutation):
    class Arguments:
        id = graphene.String(required=True)
        attributes = GenericScalar()

    ok = graphene.Boolean()
    node = graphene.Field(NodeType)

    async def mutate(self, info: graphene.ResolveInfo, id: str, attributes: dict[str, Any] | None = None) -> "CreateNode":
        perm_graph = _get_permissions_graph(info)
        if perm_graph is None:
            raise GraphQLError("Graph not configured")
        await _maybe_call(perm_graph, "add_node", id, attributes or {})
        return CreateNode(ok=True, node=NodeType(id=id, attributes=attributes or {}))


class CreateEdge(graphene.Mutation):
    class Arguments:
        source = graphene.String(required=True)
        target = graphene.String(required=True)
        label = graphene.String(required=True)

    ok = graphene.Boolean()

    async def mutate(self, info: graphene.ResolveInfo, source: str, target: str, label: str) -> "CreateEdge":
        perm_graph = _get_permissions_graph(info)
        if perm_graph is None:
            raise GraphQLError("Graph not configured")
        await _maybe_call(perm_graph, "add_edge", source, target, label)
        return CreateEdge(ok=True)


class Mutation(graphene.ObjectType):
    create_node = CreateNode.Field()
    create_edge = CreateEdge.Field()


schema = graphene.Schema(query=Query, mutation=Mutation)
