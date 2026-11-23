"""Render the vault's ontology as one self-contained static HTML page."""

from __future__ import annotations

import json
import re
from importlib.resources import files
from typing import Any

from knott.models import Ontology, iter_reference_paths
from knott.vault.refs import GroupKey, group_key, group_order

PLACEHOLDER = "/*__DATA__*/"
_SURROGATE = re.compile("[\ud800-\udfff]")


def _template() -> str:
    return files("knott").joinpath("_view", "ontology.html").read_text(encoding="utf-8")


def ontology_edges(ontology: Ontology) -> list[dict[str, Any]]:
    """One edge per known target of every reference, with its property path and the
    relation it names (the page labels an edge with the relation, else the path).

    Targets no concept defines get no edge; the side panel still shows them.
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
        for path, node, required in iter_reference_paths(t.properties)
        for target in node.targets
    ]


def referenced_by(ontology: Ontology) -> list[dict[str, Any]]:
    """Per type, the reference properties whose known targets include it, grouped and
    labelled as `knott refs` groups an entity's references (spec 0006).

    One ``{type, groups}`` per type something references, sorted by type (a list, so
    type names never become object keys in the page). Each group has ``label``,
    ``kind``, ``relation`` and ``references``: one ``{type, path, required}`` per
    property, by source type, then schema order.
    """
    relations = {r.name: r for r in ontology.relations}
    per_type: dict[str, dict[GroupKey, list[dict[str, Any]]]] = {}
    for t in ontology.types:
        for path, node, required in iter_reference_paths(t.properties):
            key = group_key(relations, node.relation, t.type, path)
            for target in node.targets:
                groups = per_type.setdefault(target, {})
                groups.setdefault(key, []).append(
                    {"type": t.type, "path": path, "required": required}
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


def render_ontology(ontology: Ontology) -> str:
    """Return the ontology viewer page with `ontology` embedded as JSON."""
    template = _template()
    if PLACEHOLDER not in template:
        raise RuntimeError(f"ontology template must contain {PLACEHOLDER}")
    payload = {
        **ontology.model_dump(),
        "edges": ontology_edges(ontology),
        "referenced_by": referenced_by(ontology),
    }
    data = json.dumps(payload, ensure_ascii=False)
    # Lone surrogates (a YAML "\ud800" escape, an undecodable file name) cannot be
    # written as UTF-8; keep them as JSON escapes so the page always encodes.
    data = _SURROGATE.sub(lambda m: f"\\u{ord(m[0]):04x}", data)
    # Keep schema text from closing the <script> or switching the HTML parser into
    # its escaped script states; both replacements are still valid JSON.
    data = data.replace("</", "<\\/").replace("<!--", "<\\u0021--")
    return template.replace(PLACEHOLDER, data, 1)
