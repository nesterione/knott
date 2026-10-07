"""Render the vault's ontology as one self-contained static HTML page."""

from __future__ import annotations

import json
import re
from importlib.resources import files

from knott.models import Ontology

PLACEHOLDER = "/*__DATA__*/"
_SURROGATE = re.compile("[\ud800-\udfff]")


def _template() -> str:
    return files("knott").joinpath("_view", "ontology.html").read_text(encoding="utf-8")


def render_ontology(ontology: Ontology) -> str:
    """Return the ontology viewer page with `ontology` embedded as JSON."""
    template = _template()
    if PLACEHOLDER not in template:
        raise RuntimeError(f"ontology template must contain {PLACEHOLDER}")
    data = json.dumps(ontology.model_dump(), ensure_ascii=False)
    # Lone surrogates (a YAML "\ud800" escape, an undecodable file name) cannot be
    # written as UTF-8; keep them as JSON escapes so the page always encodes.
    data = _SURROGATE.sub(lambda m: f"\\u{ord(m[0]):04x}", data)
    # Keep schema text from closing the <script> or switching the HTML parser into
    # its escaped script states; both replacements are still valid JSON.
    data = data.replace("</", "<\\/").replace("<!--", "<\\u0021--")
    return template.replace(PLACEHOLDER, data, 1)
