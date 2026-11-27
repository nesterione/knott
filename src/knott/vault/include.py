"""The `include` key of `.knott/config.yaml`: the folders knott reads Markdown from (spec 0019).

Two tests are kept apart. A path is *inside the included folders* when it is below
one of them: a test on the path alone, used wherever one file is named. The
*scanned set* is what discovery finds there (``iter_markdown``), used wherever
Markdown is enumerated.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from knott import _yaml
from knott.errors import ConfigError
from knott.vault.links import list_dir_entries

ROOT = "."
INCLUDE_KEY = "include"
CONFIG_PATH = ".knott/config.yaml"


@dataclass(frozen=True)
class Included:
    """The included folders of a vault."""

    folders: tuple[str, ...] = (ROOT,)
    """Vault-relative POSIX paths, in the order written, duplicates removed."""

    @property
    def whole_vault(self) -> bool:
        return ROOT in self.folders

    def contains(self, rel_path: str) -> bool:
        """True when ``rel_path`` (vault-relative, POSIX) is below an included folder."""
        if self.whole_vault:
            return True
        return any(rel_path.startswith(folder + "/") for folder in self.folders)

    def scan_roots(self) -> list[str]:
        """The folders to walk: no folder that is below another one."""
        if self.whole_vault:
            return [ROOT]
        return [
            folder
            for folder in self.folders
            if not any(folder.startswith(other + "/") for other in self.folders)
        ]

    def outside_reason(self) -> str:
        """Why a file that is not inside the included folders is not an entity."""
        listed = ", ".join(f"`{folder}`" for folder in self.folders)
        return (
            f"it is outside the included folders ({listed}); "
            f"add its folder to `{INCLUDE_KEY}` in {CONFIG_PATH}"
        )


WHOLE_VAULT = Included()


def parse_include(root: Path, document: _yaml.YamlDocument) -> Included:
    """The included folders ``document`` (a parsed ``config.yaml``) declares.

    Raises ``ConfigError`` for a value or a folder spec 0019 refuses.
    """
    data = document.data
    if not isinstance(data, dict) or INCLUDE_KEY not in data:
        return WHOLE_VAULT
    value: Any = data[INCLUDE_KEY]
    key_line = _line(document, (INCLUDE_KEY,))
    if isinstance(value, str):
        entries: list[tuple[_yaml.KeyPath, Any]] = [((INCLUDE_KEY,), value)]
    elif type(value) is list and value:
        entries = [((INCLUDE_KEY, index), item) for index, item in enumerate(value)]
    else:
        raise _error(
            key_line,
            "expected a folder or a non-empty list of folders; "
            "write `.` for the whole vault, or remove the key",
        )
    folders: list[str] = []
    for at, entry in entries:
        line = _line(document, at) or key_line
        if not isinstance(entry, str):
            raise _error(line, "each folder must be a string")
        folder = _folder(root, entry, line)
        if folder not in folders:
            folders.append(folder)
    return Included(tuple(folders))


def _line(document: _yaml.YamlDocument, at: _yaml.KeyPath) -> int | None:
    loc = document.locs.get(at)
    return None if loc is None else loc.line + 1


def _error(line: int | None, message: str) -> ConfigError:
    where = f":{line}" if line is not None else ""
    return ConfigError(f"invalid `{INCLUDE_KEY}` in {CONFIG_PATH}{where}: {message}")


def _folder(root: Path, entry: str, line: int | None) -> str:
    """``entry`` as a checked, normalised folder."""
    if entry in (ROOT, ROOT + "/"):
        return ROOT
    shown = f"`{entry}`"
    if not entry:
        raise _error(line, "a folder is empty; write `.` for the vault root")
    if entry.startswith("/"):
        raise _error(line, f"folder {shown} must be relative to the vault root, without `/` first")
    if "\\" in entry:
        raise _error(line, f"folder {shown} has a `\\`; write folders with `/`")
    if "*" in entry:
        raise _error(line, f"folder {shown} has a `*`; folders are literal, not patterns")
    parts = entry.removesuffix("/").split("/")
    if "" in parts:
        raise _error(line, f"folder {shown} has an empty segment")
    if "." in parts or ".." in parts:
        raise _error(
            line, f"folder {shown} has a `.` or `..` segment; a vault reads only below its root"
        )
    if any(part.startswith(".") for part in parts):
        raise _error(line, f"folder {shown} is hidden; hidden folders are never scanned")
    current = root
    for part in parts:
        names = list_dir_entries(current)
        if names is None or part not in names:
            raise _error(line, f"folder {shown} does not exist")
        current = current / part
        if current.is_symlink():
            raise _error(
                line,
                f"folder {shown} is a symbolic link or is reached through one, "
                "which knott does not follow",
            )
        if not current.is_dir():
            raise _error(line, f"{shown} is not a folder")
    return "/".join(parts)
