"""Relation reference parsing and resolution.

All resolution lives behind ``resolve_reference``: relative paths (plain or as a
Markdown link) and ``kid:<uuid>`` references to the knott-managed identity.
"""

from __future__ import annotations

import os
import posixpath
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote

from knott.vault.kid import KidIndex, format_claims, is_canonical, kid_problem

ListDir = Callable[[Path], frozenset[str] | None]
"""Lists a directory's entry names, or ``None`` when it can't be listed."""

_MARKDOWN_LINK = re.compile(r"^\[(?P<label>[^\]]*)\]\((?P<dest>.*)\)$", re.DOTALL)
_URL_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")

INVALID_VALUE = "relation-invalid-value"
OUTSIDE_VAULT = "relation-target-outside-vault"
NOT_FOUND = "relation-target-not-found"
AMBIGUOUS = "relation-target-ambiguous"

KID_PREFIX = "kid:"

LINK_EXAMPLE = '"[label](relative/path.md)"'


@dataclass(frozen=True)
class ResolvedReference:
    destination: str
    """The path as written (Markdown link: decoded destination)."""
    target: str
    """Vault-relative POSIX path of the existing target file."""

    @property
    def label(self) -> str:
        """How messages name the target: as written, plus the path for a `kid:` reference."""
        if self.destination.startswith(KID_PREFIX):
            return f"`{self.destination}` (`{self.target}`)"
        return f"`{self.destination}`"


class LinkError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def resolve_reference(
    vault_root: Path,
    source: str,
    reference: str,
    kids: Callable[[], KidIndex] = dict,
    list_dir: ListDir | None = None,
) -> ResolvedReference:
    """Resolve one reference string found in the file ``source`` (vault-relative).

    ``kids`` returns the vault's `kid` index; it is called only for a `kid:` reference.
    ``list_dir`` lists a directory for the exact-case check (default: ``list_dir_entries``,
    uncached); a session passes a cached one so a run lists each directory once.
    Raises ``LinkError`` with an issue code when any check fails.
    """
    text = reference.strip()
    if text.startswith(KID_PREFIX):
        return _resolve_kid(text, kids)
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
    if not _exists_exact_case(vault_root, target, list_dir or list_dir_entries):
        raise LinkError(NOT_FOUND, f"`{destination}` does not exist (resolved to `{target}`)")
    return ResolvedReference(destination=destination, target=target)


def _resolve_kid(text: str, kids: Callable[[], KidIndex]) -> ResolvedReference:
    value = text.removeprefix(KID_PREFIX).strip()
    if not is_canonical(value):
        raise LinkError(INVALID_VALUE, f"`{text}`: the `kid` {kid_problem(value)}")
    claims = kids().get(value, [])
    if not claims:
        raise LinkError(NOT_FOUND, f"no entity has `kid` {value}")
    if len(claims) > 1:
        raise LinkError(
            AMBIGUOUS,
            f"`kid` {value} is claimed by {len(claims)} entities ({format_claims(claims)}); "
            "fix the `kid-duplicate` first",
        )
    return ResolvedReference(destination=f"{KID_PREFIX}{value}", target=claims[0].path)


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
    if match is not None and destination.startswith(KID_PREFIX):
        raise LinkError(
            INVALID_VALUE,
            f"a `kid:` reference cannot be a Markdown link; write `{destination}` on its own",
        )
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


def list_dir_entries(directory: Path) -> frozenset[str] | None:
    """The entry names of ``directory``, or ``None`` when it can't be listed."""
    try:
        return frozenset(os.listdir(directory))
    except OSError:
        return None


def _exists_exact_case(root: Path, rel_path: str, list_dir: ListDir) -> bool:
    """True if ``rel_path`` names a regular file whose every component matches case exactly.

    Each component is looked up in its parent's listing, never through the file
    system's own (possibly case-insensitive) name lookup."""
    current = root
    for part in rel_path.split("/"):
        entries = list_dir(current)
        if entries is None or part not in entries:
            return False
        current = current / part
    return current.is_file()
