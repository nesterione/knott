"""`relation-cycle`: cycles of an acyclic relation (spec 0006).

One graph per acyclic relation, built from the vault's reference index: nodes are
entities, edges are references at properties naming the relation that pass the
target-type check. Each strongly connected component with more than one entity, or
an entity that references itself, is one issue.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Collection, Iterable

from knott.models import Issue
from knott.schema.models import RelationDef, Schema, iter_references
from knott.vault.index import IndexedReference, ReferenceIndex


def checked_relations(schemas: dict[str, Schema], relations: dict[str, RelationDef]) -> list[str]:
    """Names of the acyclic relations some property names, sorted.

    A symmetric relation is skipped: `acyclic` with `symmetric` is already
    `relation-symmetric-mismatch`, and a symmetric link stored on both sides is valid.
    """
    named = {
        shape.relation
        for schema in schemas.values()
        for _, shape in iter_references(schema)
        if shape.relation is not None
    }
    return sorted(
        name
        for name in named
        if (relation := relations.get(name)) is not None
        and relation.acyclic
        and not relation.symmetric
    )


def cycle_issues(
    index: ReferenceIndex, relation: str, in_scope: Collection[str] | None = None
) -> list[Issue]:
    """One `relation-cycle` issue per strongly connected component of ``relation``.

    The issue names the shortest cycle from the component's smallest path and is
    reported at the first entity on it, in path order, that is in scope. In a scoped
    run where no entity on that cycle is in scope but another of the component's
    entities is, the cycle is taken from the smallest in-scope entity instead.
    Without ``in_scope``, everything is in scope.
    """
    edges: dict[str, dict[str, IndexedReference]] = {}
    for ref in index.with_relation(relation):
        if ref.type_ok:
            # The first reference to a target, in schema order, stands for the edge.
            edges.setdefault(ref.source, {}).setdefault(ref.target, ref)

    issues: list[Issue] = []
    for component in _components(edges):
        start = min(component)
        if len(component) == 1 and start not in edges.get(start, {}):
            continue
        scoped = sorted(p for p in component if in_scope is None or p in in_scope)
        if not scoped:
            continue
        loop = _loop(edges, component, start)
        reported = next((p for p in sorted(loop) if p in scoped), None)
        if reported is None:
            start = reported = scoped[0]
            loop = _loop(edges, component, start)
        after = loop[(loop.index(reported) + 1) % len(loop)]
        ref = edges[reported][after]
        chain = " → ".join([*loop, start])
        issues.append(
            Issue(
                code="relation-cycle",
                path=reported,
                line=ref.line,
                field=ref.field,
                message=(
                    f"`{relation}` must not form a cycle: {chain}\n"
                    f"remove one of these `{relation}` references"
                ),
            )
        )
    return issues


def _loop(
    edges: dict[str, dict[str, IndexedReference]], component: set[str], start: str
) -> list[str]:
    """The shortest loop from ``start`` back to itself inside ``component``.

    Returns the entities on it in order, ``start`` first, without repeating it.
    Successors are visited in path order, so the loop is deterministic."""
    parent: dict[str, str] = {}
    queue: deque[str] = deque([start])
    seen = {start}
    while queue:
        node = queue.popleft()
        for succ in sorted(edges.get(node, {})):
            if succ == start:
                path = [node]
                while path[-1] != start:
                    path.append(parent[path[-1]])
                return path[::-1]
            if succ in component and succ not in seen:
                seen.add(succ)
                parent[succ] = node
                queue.append(succ)
    raise AssertionError("a strongly connected component always has a loop")


def _components(edges: dict[str, dict[str, IndexedReference]]) -> Iterable[set[str]]:
    """Strongly connected components (iterative Tarjan), sources in path order."""
    index_of: dict[str, int] = {}
    low: dict[str, int] = {}
    on_stack: set[str] = set()
    stack: list[str] = []
    counter = 0
    for root in sorted(edges):
        if root in index_of:
            continue
        work: list[tuple[str, list[str]]] = [(root, sorted(edges.get(root, {})))]
        index_of[root] = low[root] = counter
        counter += 1
        stack.append(root)
        on_stack.add(root)
        while work:
            node, successors = work[-1]
            if successors:
                succ = successors.pop(0)
                if succ not in index_of:
                    index_of[succ] = low[succ] = counter
                    counter += 1
                    stack.append(succ)
                    on_stack.add(succ)
                    work.append((succ, sorted(edges.get(succ, {}))))
                elif succ in on_stack:
                    low[node] = min(low[node], index_of[succ])
                continue
            work.pop()
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[node])
            if low[node] == index_of[node]:
                component: set[str] = set()
                while True:
                    member = stack.pop()
                    on_stack.discard(member)
                    component.add(member)
                    if member == node:
                        break
                yield component
