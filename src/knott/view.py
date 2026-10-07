"""Render the vault's ontology as one self-contained static HTML page."""

from __future__ import annotations

import json
from importlib.resources import files

from knott.models import Ontology

PLACEHOLDER = "/*__DATA__*/"


def _template() -> str:
    return files("knott").joinpath("_view", "ontology.html").read_text(encoding="utf-8")


def render_ontology(ontology: Ontology) -> str:
    """Return the ontology viewer page with `ontology` embedded as JSON."""
    template = _template()
    if template.count(PLACEHOLDER) != 1:
        raise RuntimeError(f"ontology template must contain {PLACEHOLDER} exactly once")
    data = json.dumps(ontology.model_dump(), ensure_ascii=False)
    # Keep schema text from closing the <script> or switching the HTML parser into
    # its escaped script states; both replacements are still valid JSON.
    data = data.replace("</", "<\\/").replace("<!--", "<\\u0021--")
    return template.replace(PLACEHOLDER, data, 1)
