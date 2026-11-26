"""Render the vault's ontology as one self-contained static HTML page."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from importlib.resources import files
from typing import Any

from knott.models import (
    LoopReport,
    Ontology,
    OntologyAttribute,
    OntologyType,
    iter_reference_paths,
)
from knott.vault.refs import GroupKey, group_key, group_order

PLACEHOLDER = "/*__DATA__*/"
_SURROGATE = re.compile("[\ud800-\udfff]")


def _template() -> str:
    return files("knott").joinpath("_view", "ontology.html").read_text(encoding="utf-8")


def _own(t: OntologyType) -> list[OntologyAttribute]:
    """The properties ``t`` declares itself: an inherited reference is drawn and listed
    once, at the type that declares it (spec 0013)."""
    return [a for a in t.properties if a.inherited_from is None]


def inheritance(ontology: Ontology) -> list[dict[str, str]]:
    """One ``{child, parent}`` per type that extends another, by child."""
    return [{"child": t.type, "parent": t.extends} for t in ontology.types if t.extends]


def ontology_edges(ontology: Ontology) -> list[dict[str, Any]]:
    """One edge per known target of every reference, with its property path and the
    relation it names (the page labels an edge with the relation, else the path).

    A reference is an edge once, from the type that declares it to each declared
    target. Targets no concept defines get no edge; the side panel still shows them.
    """
    return [
        {
            "source": t.type,
            "target": target,
            "path": path,
            "relation": node.relation,
            "required": required,
        }
        for t in ontology.types
        for path, node, required in iter_reference_paths(_own(t))
        for target in node.targets
    ]


def referenced_by(ontology: Ontology) -> list[dict[str, Any]]:
    """Per type, the reference properties whose known targets include it, grouped and
    labelled as `knott refs` groups an entity's references (spec 0006).

    One ``{type, groups}`` per type something references, sorted by type (a list, so
    type names never become object keys in the page). Each group has ``label``,
    ``kind``, ``relation`` and ``references``: one ``{type, path, required, via}`` per
    property, by source type, then schema order. A property that targets an ancestor of
    the type also reaches the type; ``via`` is that ancestor, None for a declared target.
    """
    relations = {r.name: r for r in ontology.relations}
    below: dict[str, list[str]] = {}
    for t in ontology.types:
        for ancestor in t.ancestors:
            below.setdefault(ancestor, []).append(t.type)
    per_type: dict[str, dict[GroupKey, list[dict[str, Any]]]] = {}
    for t in ontology.types:
        for path, node, required in iter_reference_paths(_own(t)):
            key = group_key(relations, node.relation, t.type, path)
            reached: dict[str, str | None] = {}
            for target in node.targets:
                reached[target] = None
            for target in node.targets:
                for subtype in below.get(target, []):
                    reached.setdefault(subtype, target)
            for target, via in reached.items():
                groups = per_type.setdefault(target, {})
                groups.setdefault(key, []).append(
                    {"type": t.type, "path": path, "required": required, "via": via}
                )
    return [
        {
            "type": target,
            "groups": [
                {"label": key[1], "kind": key[0], "relation": key[2], "references": groups[key]}
                for key in sorted(groups, key=group_order)
            ],
        }
        for target, groups in sorted(per_type.items())
    ]


def reference_properties(ontology: Ontology) -> list[dict[str, Any]]:
    """Every reference property, by type, then schema order (spec 0007).

    One entry per property, whatever its targets. ``relation`` is the relation file it
    names; None marks an inline relation: a property that names no relation, or a
    name no file defines.
    """
    return [
        {
            "type": t.type,
            "path": path,
            "relation": node.relation,
            "targets": list(node.targets),
            "unknown_targets": list(node.unknown_targets),
            "open": node.open,
            "required": required,
        }
        for t in ontology.types
        for path, node, required in iter_reference_paths(_own(t))
    ]


def render_ontology(ontology: Ontology, loops: Sequence[LoopReport] = ()) -> str:
    """Return the ontology viewer page with `ontology` embedded as JSON.

    ``loops`` are the vault's loop reports (spec 0010): the page shows each as a board,
    so it embeds the title and path of every entity whose type has a loop.
    """
    template = _template()
    if PLACEHOLDER not in template:
        raise RuntimeError(f"ontology template must contain {PLACEHOLDER}")
    payload = ontology.model_dump()
    counts = {t.type: t.count for t in ontology.types}
    for dumped, t in zip(payload["types"], ontology.types, strict=True):
        dumped["count_with_subtypes"] = t.count + sum(
            counts[other.type] for other in ontology.types if t.type in other.ancestors
        )
    payload = {
        **payload,
        "edges": ontology_edges(ontology),
        "inheritance": inheritance(ontology),
        "referenced_by": referenced_by(ontology),
        "reference_properties": reference_properties(ontology),
        "loop_reports": [report.model_dump() for report in loops],
    }
    data = json.dumps(payload, ensure_ascii=False)
    # Lone surrogates (a YAML "\ud800" escape, an undecodable file name) cannot be
    # written as UTF-8; keep them as JSON escapes so the page always encodes.
    data = _SURROGATE.sub(lambda m: f"\\u{ord(m[0]):04x}", data)
    # Keep schema text from closing the <script> or switching the HTML parser into
    # its escaped script states; both replacements are still valid JSON.
    data = data.replace("</", "<\\/").replace("<!--", "<\\u0021--")
    return template.replace(PLACEHOLDER, data, 1)
