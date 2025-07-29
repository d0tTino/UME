from __future__ import annotations
# mypy: ignore-errors

import inspect
from typing import Any

import graphene
from graphene.types.generic import GenericScalar


async def _maybe_call(obj: Any, name: str, *args: Any) -> Any:
    method = getattr(obj, name)
    if inspect.iscoroutinefunction(method):
        return await method(*args)
    result = method(*args)
    if inspect.isawaitable(result):
        return await result
    return result


class NodeType(graphene.ObjectType):
    """Graph node representation."""

    id = graphene.String(required=True)
    attributes = GenericScalar()


class EdgeType(graphene.ObjectType):
    """Graph edge representation."""

    source = graphene.String(required=True)
    target = graphene.String(required=True)
    label = graphene.String(required=True)


class Query(graphene.ObjectType):
    node = graphene.Field(NodeType, id=graphene.String(required=True))
    nodes = graphene.List(NodeType)
    edges = graphene.List(EdgeType)

    async def resolve_node(self, info: graphene.ResolveInfo, id: str) -> NodeType | None:
        graph = info.context["app"].state.graph
        if graph is None:
            return None
        data = await _maybe_call(graph, "get_node", id)
        if data is None:
            return None
        return NodeType(id=id, attributes=data)

    async def resolve_nodes(self, info: graphene.ResolveInfo) -> list[NodeType]:
        graph = info.context["app"].state.graph
        if graph is None:
            return []
        ids = await _maybe_call(graph, "get_all_node_ids")
        result = []
        for nid in ids:
            data = await _maybe_call(graph, "get_node", nid)
            result.append(NodeType(id=nid, attributes=data or {}))
        return result

    async def resolve_edges(self, info: graphene.ResolveInfo) -> list[EdgeType]:
        graph = info.context["app"].state.graph
        if graph is None:
            return []
        edges = await _maybe_call(graph, "get_all_edges")
        return [EdgeType(source=s, target=t, label=lbl) for s, t, lbl in edges]


class CreateNode(graphene.Mutation):
    class Arguments:
        id = graphene.String(required=True)
        attributes = GenericScalar()

    ok = graphene.Boolean()
    node = graphene.Field(NodeType)

    async def mutate(self, info: graphene.ResolveInfo, id: str, attributes: dict[str, Any] | None = None) -> "CreateNode":
        graph = info.context["app"].state.graph
        await _maybe_call(graph, "add_node", id, attributes or {})
        return CreateNode(ok=True, node=NodeType(id=id, attributes=attributes or {}))


class CreateEdge(graphene.Mutation):
    class Arguments:
        source = graphene.String(required=True)
        target = graphene.String(required=True)
        label = graphene.String(required=True)

    ok = graphene.Boolean()

    async def mutate(self, info: graphene.ResolveInfo, source: str, target: str, label: str) -> "CreateEdge":
        graph = info.context["app"].state.graph
        await _maybe_call(graph, "add_edge", source, target, label)
        return CreateEdge(ok=True)


class Mutation(graphene.ObjectType):
    create_node = CreateNode.Field()
    create_edge = CreateEdge.Field()


schema = graphene.Schema(query=Query, mutation=Mutation)
