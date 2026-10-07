"""Relation reference parsing and resolution.

All path-based resolution lives behind ``resolve_reference`` so that a later
``id``-based scheme can replace it in one place.
"""

from __future__ import annotations

import os
import posixpath
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote

_MARKDOWN_LINK = re.compile(r"^\[(?P<label>[^\]]*)\]\((?P<dest>.*)\)$", re.DOTALL)
_URL_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")

INVALID_VALUE = "relation-invalid-value"
OUTSIDE_VAULT = "relation-target-outside-vault"
NOT_FOUND = "relation-target-not-found"

LINK_EXAMPLE = '"[label](relative/path.md)"'


@dataclass(frozen=True)
class ResolvedReference:
    destination: str
    """The path as written (Markdown link: decoded destination)."""
    target: str
    """Vault-relative POSIX path of the existing target file."""


class LinkError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def resolve_reference(vault_root: Path, source: str, reference: str) -> ResolvedReference:
    """Resolve one reference string found in the file ``source`` (vault-relative).

    Raises ``LinkError`` with an issue code when any check fails.
    """
    destination = parse_reference(reference)
    joined = posixpath.join(posixpath.dirname(source), destination)
    target = posixpath.normpath(joined)
    if target == ".." or target.startswith("../"):
        raise LinkError(OUTSIDE_VAULT, f"`{destination}` resolves to a path outside the vault root")
    # Discovery never follows symlinked directories, so a target that only exists
    # through a symlink pointing out of the vault is not in the vault either.
    real = Path(os.path.realpath(vault_root / target))
    if not real.is_relative_to(vault_root.resolve()):
        raise LinkError(
            OUTSIDE_VAULT,
            f"`{destination}` resolves through a symlink to a path outside the vault root",
        )
    if not _exists_exact_case(vault_root, target):
        raise LinkError(NOT_FOUND, f"`{destination}` does not exist (resolved to `{target}`)")
    return ResolvedReference(destination=destination, target=target)


def parse_reference(reference: str) -> str:
    """Return the relative destination path of a plain path or Markdown link."""
    text = reference.strip()
    if text.startswith("[["):
        raise LinkError(
            INVALID_VALUE,
            f"wikilinks are not supported: `{reference}`; use a Markdown link such as "
            f"{LINK_EXAMPLE}",
        )
    match = _MARKDOWN_LINK.match(text)
    if match is not None:
        destination = match.group("dest").strip()
        if destination.startswith("<") and destination.endswith(">"):
            destination = destination[1:-1]
        elif any(ch.isspace() for ch in destination):
            raise LinkError(
                INVALID_VALUE,
                f"link destination `{destination}` contains spaces; "
                "wrap it in <…> or encode spaces as %20",
            )
        destination = unquote(destination)
    elif text.startswith("["):
        raise LinkError(
            INVALID_VALUE,
            f"`{reference}` is not a valid Markdown link; expected {LINK_EXAMPLE}",
        )
    else:
        destination = text
    if not destination:
        raise LinkError(INVALID_VALUE, f"`{reference}` has an empty path")
    if _URL_SCHEME.match(destination):
        raise LinkError(
            INVALID_VALUE, f"`{destination}` is a URL; relations must be relative file paths"
        )
    if "#" in destination:
        raise LinkError(
            INVALID_VALUE, f"`{destination}` contains a #fragment; link to the whole file"
        )
    if destination.startswith(("/", "\\")):
        raise LinkError(
            INVALID_VALUE,
            f"`{destination}` is an absolute path; use a path relative to this file",
        )
    if not destination.endswith(".md"):
        raise LinkError(INVALID_VALUE, f"`{destination}` does not point to a `.md` file")
    return destination


def _exists_exact_case(root: Path, rel_path: str) -> bool:
    """True if ``rel_path`` names a regular file whose every component matches case exactly."""
    current = root
    for part in rel_path.split("/"):
        try:
            if part not in os.listdir(current):
                return False
        except OSError:
            return False
        current = current / part
    return current.is_file()
