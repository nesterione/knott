"""File value parsing and resolution (spec 0008).

A file value is a path, for a file in the vault, or a URI, for a file kept
elsewhere. ``resolve_file`` runs the spec's steps in order and stops at the first
that fails. Reference resolution (``links.py``) is separate and unchanged.
"""

from __future__ import annotations

import difflib
import os
import posixpath
from collections.abc import Collection
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote

from knott.vault.discovery import CONNECTORS_DIR
from knott.vault.links import _MARKDOWN_LINK, _URL_SCHEME, LinkError, ListDir, list_dir_entries

INVALID_VALUE = "file-invalid-value"
UNKNOWN_CONNECTOR = "file-unknown-connector"
OUTSIDE_VAULT = "file-outside-vault"
NOT_FOUND = "file-not-found"
EXTENSION_MISMATCH = "file-extension-mismatch"

FILE_LINK_EXAMPLE = '"[label](relative/path.pdf)"'
_KID_SCHEME = "kid"


@dataclass(frozen=True)
class ResolvedFile:
    value: str
    """The path as written (Markdown link: decoded destination), or the whole URI."""
    connector: str | None
    """The connector a URI names; None for a file in the vault."""
    target: str | None
    """Vault-relative POSIX path of the existing file; None for a URI."""


def resolve_file(
    vault_root: Path,
    source: str,
    value: str,
    connectors: Collection[str] = (),
    accept: tuple[str, ...] = (),
    list_dir: ListDir | None = None,
) -> ResolvedFile:
    """Resolve one file value found in the file ``source`` (vault-relative).

    ``connectors`` are the declared connector names. Raises ``LinkError`` with a
    ``file-*`` issue code at the first step that fails.
    """
    text = value.strip()
    if text.startswith("[["):
        raise LinkError(
            INVALID_VALUE,
            f"wikilinks are not supported: `{value}`; use a Markdown link such as "
            f"{FILE_LINK_EXAMPLE}",
        )
    match = _MARKDOWN_LINK.match(text)
    if match is not None:
        path = _link_path(match.group("dest").strip())
    elif text.startswith("["):
        raise LinkError(
            INVALID_VALUE,
            f"`{value}` is not a valid Markdown link; expected {FILE_LINK_EXAMPLE}",
        )
    elif _URL_SCHEME.match(text):
        return _resolve_uri(text, connectors)
    else:
        path = text
    return _resolve_path(vault_root, source, path, accept, list_dir or list_dir_entries)


def _link_path(destination: str) -> str:
    """The path a Markdown link's destination names. A link never holds a URI."""
    if destination.startswith("<") and destination.endswith(">"):
        destination = destination[1:-1]
    elif any(ch.isspace() for ch in destination):
        raise LinkError(
            INVALID_VALUE,
            f"link destination `{destination}` contains spaces; "
            "wrap it in <…> or encode spaces as %20",
        )
    if _URL_SCHEME.match(destination):
        raise LinkError(
            INVALID_VALUE,
            f"a URI cannot be a Markdown link; write `{destination}` on its own",
        )
    # Decoding never turns a path into a URI: `a%3Ab.json` is the file `a:b.json`.
    return unquote(destination)


def _resolve_uri(uri: str, connectors: Collection[str]) -> ResolvedFile:
    scheme, _, rest = uri.partition(":")
    name = scheme.lower()
    if name == _KID_SCHEME:
        raise LinkError(
            INVALID_VALUE,
            f"`{uri}` names an entity; `kid:` belongs in a `reference` property, not a file",
        )
    if not rest.strip():
        raise LinkError(INVALID_VALUE, f"`{uri}` has nothing after the scheme `{scheme}:`")
    if name not in connectors:
        raise LinkError(UNKNOWN_CONNECTOR, _unknown_connector(uri, name, connectors))
    return ResolvedFile(value=uri, connector=name, target=None)


def _unknown_connector(uri: str, name: str, connectors: Collection[str]) -> str:
    known = ", ".join(f"`{c}`" for c in sorted(connectors)) or "none"
    message = (
        f"`{uri}` uses the scheme `{name}`, which no connector file in "
        f"`{CONNECTORS_DIR}/` defines (known connectors: {known})"
    )
    close = difflib.get_close_matches(name, sorted(connectors), n=1)
    if close:
        return message + f"; did you mean `{close[0]}`?"
    return (
        message + f"\nfor a file in the vault write a relative path (`./{uri}` if the name "
        f"has a colon); for a file kept elsewhere add `{CONNECTORS_DIR}/{name}.md` "
        f"with `name: {name}`"
    )


def _resolve_path(
    vault_root: Path, source: str, path: str, accept: tuple[str, ...], list_dir: ListDir
) -> ResolvedFile:
    if not path:
        raise LinkError(INVALID_VALUE, "the value has an empty path")
    if "\0" in path:
        raise LinkError(INVALID_VALUE, "the path contains a null character")
    if "#" in path:
        raise LinkError(INVALID_VALUE, f"`{path}` contains a #fragment; name the whole file")
    if path.startswith(("/", "\\")):
        raise LinkError(
            INVALID_VALUE,
            f"`{path}` is an absolute path; use a path relative to this file",
        )
    target = posixpath.normpath(posixpath.join(posixpath.dirname(source), path))
    if target == ".." or target.startswith("../"):
        raise LinkError(OUTSIDE_VAULT, f"`{path}` resolves to a path outside the vault root")
    real = Path(os.path.realpath(vault_root / target))
    if not real.is_relative_to(vault_root.resolve()):
        raise LinkError(
            OUTSIDE_VAULT,
            f"`{path}` resolves through a symlink to a path outside the vault root",
        )
    _check_exists(vault_root, path, target, list_dir)
    if accept:
        extension = file_extension(posixpath.basename(target))
        if extension not in accept:
            expected = " or ".join(f"`.{e}`" for e in accept)
            actual = f"is `.{extension}`" if extension else "has no extension"
            raise LinkError(EXTENSION_MISMATCH, f"expects {expected}, but `{path}` {actual}")
    return ResolvedFile(value=path, connector=None, target=target)


def _check_exists(vault_root: Path, path: str, target: str, list_dir: ListDir) -> None:
    """Every component of ``target`` must match case exactly, and it must be a regular file.

    Each component is looked up in its parent's listing, never through the file
    system's own (possibly case-insensitive) name lookup."""
    current = vault_root
    if target != ".":
        for part in target.split("/"):
            entries = list_dir(current)
            if entries is None or part not in entries:
                raise LinkError(NOT_FOUND, f"`{path}` does not exist (resolved to `{target}`)")
            current = current / part
    if current.is_dir():
        raise LinkError(NOT_FOUND, f"`{path}` is a folder, not a file (resolved to `{target}`)")
    if not current.is_file():
        raise LinkError(NOT_FOUND, f"`{path}` does not exist (resolved to `{target}`)")


def file_extension(name: str) -> str:
    """The text after the last ``.`` of a file name, lowercased.

    A name with no dot, or only a leading one (``.env``), has no extension."""
    stem, dot, extension = name.rpartition(".")
    return extension.lower() if dot and stem else ""
