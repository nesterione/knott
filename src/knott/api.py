"""The Knott API. The CLI is a thin adapter over this module."""

from __future__ import annotations

import os
from collections.abc import Sequence
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _dist_version
from pathlib import Path

from knott import _yaml
from knott.errors import ConfigError, PathNotFoundError, PathOutsideVaultError
from knott.models import InitResult, Issue, SchemaInfo, Stats, ValidationResult
from knott.schema.loader import SCHEMAS_DIR, load_schemas
from knott.schema.validator import validate_entity
from knott.vault.discovery import KNOTT_DIR, find_vault_root, iter_markdown
from knott.vault.entity import MarkdownFile, read_markdown
from knott.vault.links import ResolvedReference, resolve_reference

CONFIG_FILE = Path(KNOTT_DIR) / "config.yaml"


def version() -> str:
    """The installed Knott version."""
    try:
        return _dist_version("knott")
    except PackageNotFoundError:  # running from a source tree without install
        return "0.0.0"


class Knott:
    """A Knott vault on disk."""

    def __init__(self, root: Path) -> None:
        self.root = root

    @classmethod
    def open(cls, path: str | Path = ".") -> Knott:
        """Open the vault containing ``path``, walking up to the nearest ``.knott/``.

        Raises ``VaultNotFoundError``, ``PathNotFoundError`` or ``ConfigError``.
        """
        start = Path(path)
        if not start.exists():
            raise PathNotFoundError(f"path does not exist: {path}")
        vault = cls(find_vault_root(start))
        vault._check_config()
        return vault

    @staticmethod
    def init(path: str | Path = ".") -> InitResult:
        """Create ``.knott/schemas/`` and ``.knott/config.yaml`` in ``path``.

        Changes nothing if ``.knott/`` already exists.
        """
        root = Path(path)
        if not root.is_dir():
            raise PathNotFoundError(f"directory does not exist: {path}")
        knott_dir = root / KNOTT_DIR
        if knott_dir.exists():
            return InitResult(root=str(root.resolve()), created=False)
        (root / SCHEMAS_DIR).mkdir(parents=True)
        (root / CONFIG_FILE).write_text(f"knott_version: {version()}\n", encoding="utf-8")
        return InitResult(root=str(root.resolve()), created=True)

    def types(self) -> list[str]:
        """Discovered type names, sorted. Schemas with errors may be missing."""
        return [info.type for info in self.schemas()]

    def schemas(self) -> list[SchemaInfo]:
        """Discovered types with their description and schema file, sorted by type."""
        registry, _ = load_schemas(self.root)
        return [
            SchemaInfo(type=s.type, description=s.description, path=s.path)
            for _, s in sorted(registry.items())
        ]

    def schema_issues(self) -> list[Issue]:
        """Problems found while loading schemas, sorted."""
        _, issues = load_schemas(self.root)
        return _sorted(issues)

    def validate(self, paths: Sequence[str | Path] | None = None) -> ValidationResult:
        """Validate all schemas, and entities (all, or those within ``paths``).

        Relative ``paths`` are resolved against the vault root. Validation problems
        are returned as data; only usage errors raise.
        """
        schemas, issues = load_schemas(self.root)
        files: dict[str, MarkdownFile] = {}

        def lookup(rel_path: str) -> MarkdownFile:
            parsed = files.get(rel_path)
            if parsed is None:
                parsed = read_markdown(self.root / rel_path, rel_path)
                files[rel_path] = parsed
            return parsed

        def resolve(source: str, reference: str) -> ResolvedReference:
            return resolve_reference(self.root, source, reference)

        all_markdown = iter_markdown(self.root)
        if paths is None:
            in_scope = all_markdown
        else:
            in_scope, scope_issues = self._scope(paths, all_markdown)
            issues.extend(scope_issues)

        entities = 0
        relations = 0
        for rel_path in in_scope:
            parsed = lookup(rel_path)
            if parsed.error is not None:
                issues.append(
                    Issue(
                        code="entity-invalid-frontmatter",
                        path=rel_path,
                        line=parsed.error_line,
                        message=parsed.error,
                    )
                )
                continue
            if not parsed.is_entity:
                continue
            entities += 1
            report = validate_entity(parsed, schemas, resolve, lookup)
            issues.extend(report.issues)
            relations += report.relations

        stats = Stats(schemas=len(schemas), entities=entities, relations=relations)
        return ValidationResult(issues=_sorted(issues), stats=stats)

    def _scope(
        self,
        paths: Sequence[str | Path],
        all_markdown: list[str],
    ) -> tuple[list[str], list[Issue]]:
        selected: set[str] = set()
        issues: list[Issue] = []
        for given in paths:
            candidate = Path(given)
            if not candidate.is_absolute():
                candidate = self.root / candidate
            if not candidate.exists():
                raise PathNotFoundError(f"path does not exist: {given}")
            # Resolve symlinks in the parent only, so a symlinked file keeps its own path.
            absolute = Path(os.path.abspath(candidate))
            absolute = absolute.parent.resolve() / absolute.name
            try:
                rel = absolute.relative_to(self.root)
            except ValueError:
                raise PathOutsideVaultError(
                    f"path is outside the vault {self.root}: {given}"
                ) from None
            rel_posix = rel.as_posix()
            if absolute.is_dir():
                prefix = "" if rel_posix == "." else rel_posix + "/"
                selected.update(p for p in all_markdown if p.startswith(prefix))
                continue
            parsed = read_markdown(absolute, rel_posix) if rel_posix.endswith(".md") else None
            if parsed is not None and (parsed.is_entity or parsed.error is not None):
                selected.add(rel_posix)
            else:
                issues.append(
                    Issue(
                        code="not-an-entity",
                        path=rel_posix,
                        message=(
                            "not a Knott entity: expected a Markdown file whose YAML "
                            "frontmatter has a `type` key"
                        ),
                    )
                )
        return sorted(selected), issues

    def _check_config(self) -> None:
        config = self.root / CONFIG_FILE
        if not config.exists():
            return
        try:
            text = config.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise ConfigError(f"cannot read {CONFIG_FILE.as_posix()}: {exc}") from exc
        try:
            data = _yaml.load(text).data
        except _yaml.YamlParseError as exc:
            where = f":{exc.line + 1}" if exc.line is not None else ""
            raise ConfigError(f"malformed {CONFIG_FILE.as_posix()}{where}: {exc.message}") from exc
        if data is not None and not isinstance(data, dict):
            raise ConfigError(f"malformed {CONFIG_FILE.as_posix()}: expected a YAML mapping")


def _sorted(issues: list[Issue]) -> list[Issue]:
    return sorted(
        issues,
        key=lambda i: (i.path, i.line or 0, i.field or "", i.code, i.message),
    )
